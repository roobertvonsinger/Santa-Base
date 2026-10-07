#!/usr/bin/env python3
"""
harvest_jalisco_hits.py — Cosechador Universal de Leads (<65 años, Tarjeta + CP).
Prioriza mayores límites de crédito primero, valida con Onboarding (Proxy) y Santander Web (Directo).
Inserta en santander_hits con card_verified=1 solo cuando ambos checks son exitosos.
Soporta pausa/reanudar desde la UI de Santa Base vía purger_pause.flag y telemetría purger_status.json.
"""

import sys
import os
import time
import json
import asyncio
import sqlite3
import argparse
from datetime import datetime
from typing import Optional, List

# Importar funciones de cálculo y validación
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from migrate_santander import (
    split_fullname,
    infer_gender,
    extract_birthdate_from_rfc,
    generarCurp,
    CANONICAL_STATES
)
from santander_runner import check_single_curp, check_card_existence

# Asegurar codificación UTF-8 en Windows para evitar caídas por charmap
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

DB_PATH = r"C:\Users\rober\Dropbox\TESTING DEV\data\santander.db"
STATUS_JSON_PATH = os.path.join(os.path.dirname(DB_PATH), "purger_status.json")
PAUSE_FLAG_PATH = os.path.join(os.path.dirname(DB_PATH), "purger_pause.flag")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def is_eligible_age(fnac_str: str) -> bool:
    """Verifica que la persona sea menor de 65 años (estrictamente nacida a partir de 1963) y mayor de 18 años."""
    if not fnac_str or len(fnac_str) < 4:
        return False
    try:
        birth_year = int(fnac_str[:4])
        # Hoy es 2026: nacidos entre 1963 y 2008 tienen entre 18 y 63 años (menores de 65)
        return 1963 <= birth_year <= 2008
    except Exception:
        return False

def parse_credit_limit(raw_val: str) -> int:
    """Extrae el valor numérico entero del límite de crédito (ej. '$150,000' -> 150000)."""
    if not raw_val:
        return 0
    clean = str(raw_val).replace("$", "").replace(",", "").strip()
    try:
        return int(float(clean))
    except Exception:
        return 0

def write_telemetry(stats: dict):
    """Escribe telemetría atómica a purger_status.json para la UI de Santa Base."""
    try:
        payload = dict(stats)
        payload["updated_at"] = time.time()
        payload["timestamp_str"] = time.strftime("%Y-%m-%d %H:%M:%S")
        temp_file = STATUS_JSON_PATH + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(temp_file, STATUS_JSON_PATH)
    except Exception:
        pass

def count_unworked_hits(conn) -> int:
    """Cuenta cuántos hits ACTIVE están pendientes de trabajar en la bóveda."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM santander_hits WHERE work_status = 'ACTIVE'")
        return cur.fetchone()[0]
    except Exception:
        return 0

async def harvest(
    target_hits: int = 100,
    max_checks: int = 5000,
    delay_sec: float = 0.6,
    min_credito: int = 50000,
    estados_filter: Optional[List[str]] = None,
    hits_pool_max: int = 15,
    hits_pool_resume: int = 10,
    daemon_mode: bool = False
):
    print("=" * 70)
    print(f"[*] SANTA BASE -- COSECHADOR UNIVERSAL DE HITS VIP")
    print("=" * 70)
    print(f"BD: {DB_PATH}")
    ed_str = ", ".join(estados_filter) if estados_filter else "NACIONAL (TODOS LOS ESTADOS)"
    print(f"Estados: {ed_str}")
    print(f"Filtro de Crédito: Límite >= ${min_credito:,} (Prioridad: Límite Más Alto)")
    print(f"Filtro de Edad: Nacidos de 1963 en adelante (< 65 años)")
    print(f"Cadencia: {delay_sec}s entre peticiones")
    print(f"Bóveda Pool Cap: Pausa en {hits_pool_max} hits ACTIVE, Reanuda en {hits_pool_resume}")
    print("-" * 70)

    start_time = time.time()
    stats = {
        "total_processed": 0,
        "hits": 0,
        "offs": 0,
        "retries": 0,
        "state": "BURST" if not os.path.exists(PAUSE_FLAG_PATH) else "PAUSED_MANUAL",
        "rate_per_min": 0.0,
        "active_workers": 1
    }
    write_telemetry(stats)

    conn = get_db()
    cur = conn.cursor()

    while True:
        # Construir consulta
        where_conds = [
            "LENGTH(TRIM(u6rfc)) = 13",
            "u6acct IS NOT NULL AND TRIM(u6acct) != ''",
            "dmzip IS NOT NULL AND TRIM(dmzip) != ''",
            "(results IS NULL OR results = '')",
            "(SUBSTR(u6rfc, 5, 2) >= '63' OR SUBSTR(u6rfc, 5, 2) <= '08')",
            "CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER) >= ?"
        ]
        params: List[any] = [min_credito]

        if estados_filter:
            placeholders = ",".join("?" for _ in estados_filter)
            where_conds.append(f"UPPER(u6estado) IN ({placeholders})")
            params.extend([e.upper() for e in estados_filter])

        sql = f"""
            SELECT id, u6acct, dmname, u6rfc, u6estado, dmcity, dmzip, u6tel1, dmaddr1, u6licrea, curp
            FROM santander_records
            WHERE {" AND ".join(where_conds)}
            ORDER BY CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER) DESC
            LIMIT 1000
        """

        cur.execute(sql, params)
        candidates = cur.fetchall()
        print(f"\n[+] Lote de {len(candidates)} candidatos precargados con límite >= ${min_credito:,}")

        if not candidates:
            print("[✓] No hay más candidatos pendientes en este segmento.")
            stats["state"] = "COMPLETED"
            write_telemetry(stats)
            if not daemon_mode:
                break
            await asyncio.sleep(60.0)
            continue

        for row in candidates:
            # 1. Chequeo de Pausa Manual desde UI (purger_pause.flag)
            while os.path.exists(PAUSE_FLAG_PATH):
                if stats["state"] != "PAUSED_MANUAL":
                    stats["state"] = "PAUSED_MANUAL"
                    stats["rate_per_min"] = 0.0
                    write_telemetry(stats)
                print("[⏸️] Pausado manualmente desde la UI. Esperando reanudación...", end="\r", flush=True)
                await asyncio.sleep(1.5)

            # 2. Chequeo de Pool Cap (no quemar proxy si la bóveda tiene suficientes leads activos)
            unworked = count_unworked_hits(conn)
            if unworked >= hits_pool_max:
                stats["state"] = "PAUSED_HITS_POOL"
                stats["rate_per_min"] = 0.0
                write_telemetry(stats)
                print(f"\n[⏸️] Pool de hits llegó a {unworked} (>= {hits_pool_max}). Pausando para no quemar proxy.", flush=True)
                while count_unworked_hits(conn) > hits_pool_resume:
                    if os.path.exists(PAUSE_FLAG_PATH):
                        stats["state"] = "PAUSED_MANUAL"
                        write_telemetry(stats)
                    await asyncio.sleep(8.0)
                print(f"[▶️] Pool de hits bajó a {count_unworked_hits(conn)} (<= {hits_pool_resume}). Reanudando cosechador.", flush=True)

            stats["state"] = "BURST"

            if not daemon_mode:
                if stats["hits"] >= target_hits or (max_checks and stats["total_processed"] >= max_checks):
                    break

            rid = row["id"]
            rfc = (row["u6rfc"] or "").strip().upper()
            name = (row["dmname"] or "").strip()
            acct = (row["u6acct"] or "").strip()
            cp = (row["dmzip"] or "").strip()
            city = (row["dmcity"] or "").strip()
            raw_estado = (row["u6estado"] or "").strip().upper()
            limit_raw = (row["u6licrea"] or "$0").strip()
            limit_num = parse_credit_limit(limit_raw)
            tel = (row["u6tel1"] or "").strip()
            addr = (row["dmaddr1"] or "").strip()

            if limit_num < min_credito:
                continue

            # Extraer y validar fecha de nacimiento estricta
            fnac = extract_birthdate_from_rfc(rfc)
            if fnac and not is_eligible_age(fnac):
                # Mayor de 65 años o menor de 18
                cur.execute("UPDATE santander_records SET results = 'OFF: edad no elegible (>65 o <18)' WHERE id = ?", (rid,))
                conn.commit()
                continue

            # Mapear estado canónico
            canon_entry = CANONICAL_STATES.get(raw_estado)
            estado_norm = canon_entry[0] if canon_entry else (raw_estado or "MEXICO")
            estado_code = canon_entry[1] if canon_entry else "NE"

            curp_val = (row["curp"] or "").strip().upper()
            gender = infer_gender(name)
            if not curp_val or len(curp_val) < 18:
                split = split_fullname(name)
                if split and split.get("ap1") and split.get("nombre") and gender and fnac and estado_code != "NE":
                    calc = generarCurp(split["ap1"], split["ap2"], split["nombre"], fnac, gender, estado_code)
                    if calc:
                        curp_val = calc
                        cur.execute(
                            "UPDATE santander_records SET curp = ?, fecha_nacimiento = ?, genero = ?, estado = ?, ciudad = ?, codigo_postal = ? WHERE id = ?",
                            (curp_val, fnac, gender, estado_norm, city, cp, rid)
                        )
                        conn.commit()

            if not curp_val or len(curp_val) < 18:
                continue

            stats["total_processed"] += 1
            t0 = time.time()
            card_tail = acct[-4:] if len(acct) >= 4 else acct
            print(f"[{stats['total_processed']}] ID:{rid} | {curp_val} | ${limit_num:,} | {estado_norm[:12]} | T:{card_tail}...", end=" ", flush=True)

            # --- CHECK 1: ONBOARDING SANTANDER (VÍA PROXY RESIDENCIAL) ---
            try:
                res = await check_single_curp(curp_val, state=estado_norm)
            except Exception as ex:
                res = {"status": "RETRY", "detail": str(ex)[:60]}

            status = res.get("status", "ERROR")
            detail = res.get("detail", "")
            dur = time.time() - t0

            # Guardar resultado en santander_records
            res_str = f"{status}: {detail}"
            cur.execute("UPDATE santander_records SET results = ? WHERE id = ?", (res_str, rid))
            conn.commit()

            if status == "ON":
                # --- CHECK 2: EXISTENCIA DE TARJETA EN LOGIN WEB SANTANDER ---
                card_digits = "".join(c for c in acct if c.isdigit())
                if len(card_digits) >= 16:
                    print(f"-> [ONBOARDING ON] Verificando tarjeta {card_digits[-4:]}...", end=" ", flush=True)
                    try:
                        card_res = await asyncio.to_thread(check_card_existence, card_digits[:16])
                    except Exception as cex:
                        card_res = {"status": "ERROR", "detail": str(cex)[:60]}

                    card_status = card_res.get("status", "ERROR")
                    card_detail = card_res.get("detail", "")

                    if card_status == "INACTIVE":
                        cur.execute("UPDATE santander_records SET results = ? WHERE id = ?", (f"OFF: tarjeta inactiva ({card_detail})", rid))
                        conn.commit()
                        stats["offs"] += 1
                        print(f"[CARD INACTIVE] ({card_detail})")
                        write_telemetry(stats)
                        await asyncio.sleep(delay_sec)
                        continue
                    elif card_status == "ERROR":
                        stats["retries"] += 1
                        print(f"[CARD ERROR] {card_detail} — lead preservado")
                        write_telemetry(stats)
                        await asyncio.sleep(delay_sec)
                        continue

                # AMBOS CHECKS EXITOSOS: GUARDAR HIT EN BÓVEDA
                stats["hits"] += 1
                try:
                    cur.execute("""
                        INSERT OR REPLACE INTO santander_hits (
                            id, u6acct, curp, u6rfc, dmname, estado, ciudad, codigo_postal,
                            u6licrea, fecha_nacimiento, genero, direccion, work_status, card_verified, checked_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 1, CURRENT_TIMESTAMP)
                    """, (rid, acct, curp_val, rfc, name, estado_norm, city, cp, limit_raw, fnac, gender, addr))
                    conn.commit()
                    print(f"[🟢 HIT #{stats['hits']}] Ambos checks OK! Guardado en bóveda ({dur:.1f}s)")
                except Exception as e:
                    print(f"[!] Error al persistir hit: {e}")
            elif status == "OFF":
                stats["offs"] += 1
                print(f"[🔴 OFF] {detail} ({dur:.1f}s)")
            else:
                stats["retries"] += 1
                print(f"[⚠️ {status}] {detail} ({dur:.1f}s)")

            elapsed_m = (time.time() - start_time) / 60.0
            if elapsed_m > 0.05:
                stats["rate_per_min"] = round(stats["total_processed"] / elapsed_m, 1)

            write_telemetry(stats)
            await asyncio.sleep(delay_sec)

        if not daemon_mode:
            if stats["hits"] >= target_hits or (max_checks and stats["total_processed"] >= max_checks):
                break

    stats["state"] = "STOPPED"
    write_telemetry(stats)
    conn.close()
    print("\n" + "=" * 70)
    print(f"🏁 COSECHA FINALIZADA | Total: {stats['total_processed']} | HITS: {stats['hits']} | OFF: {stats['offs']}")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SantaBase — Cosechador Universal")
    parser.add_argument("--target-hits", type=int, default=50)
    parser.add_argument("--max-checks", type=int, default=2000)
    parser.add_argument("--delay", type=float, default=0.6)
    parser.add_argument("--min-credito", type=int, default=50000)
    parser.add_argument("--estados", type=str, default=None, help="Estados separados por coma (o omitir para nacional)")
    parser.add_argument("--daemon", action="store_true", help="Modo continuo desatendido")
    args = parser.parse_args()

    ed_list = [e.strip() for e in args.estados.split(",") if e.strip()] if args.estados else None
    asyncio.run(harvest(
        target_hits=args.target_hits,
        max_checks=args.max_checks,
        delay_sec=args.delay,
        min_credito=args.min_credito,
        estados_filter=ed_list,
        daemon_mode=args.daemon
    ))
