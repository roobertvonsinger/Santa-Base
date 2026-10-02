#!/usr/bin/env python3
"""
migrate_hits_schema.py — Migración única del schema de santander_hits al modelo ACTIVE/SUCCESS/OFF.

Cambios:
  1. Agrega columna card_verified (0 = no verificado con tarjeta, 1 = verificado activo)
  2. Normaliza work_status viejo (NUEVO/EN_GESTION/CERRADO/DESCARTADO) → ACTIVE
  3. Elimina columna telefono (ya no se usa en la bóveda)

Idempotente: se puede correr varias veces sin romper nada.
"""

import os
import sqlite3
import sys

DB_CANDIDATES = [
    os.environ.get("SANTANDER_DB_PATH"),
    r"C:\Users\rober\Dropbox\TESTING DEV\data\santander.db",
    "/opt/kvm4/apps/santander/data/santander.db",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "santander.db")),
]


def resolve_db() -> str:
    for c in DB_CANDIDATES:
        if c and os.path.exists(c):
            return c
    raise SystemExit("No se encontro santander.db en ninguna ruta conocida")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    db = resolve_db()
    print(f"[*] BD: {db}")

    conn = sqlite3.connect(db, timeout=60.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    cur = conn.cursor()

    cols = [r[1] for r in cur.execute("PRAGMA table_info(santander_hits)").fetchall()]
    if not cols:
        print("[!] La tabla santander_hits no existe. Nada que migrar.")
        return

    print(f"[*] Columnas actuales: {cols}")

    # 1. card_verified
    if "card_verified" not in cols:
        cur.execute("ALTER TABLE santander_hits ADD COLUMN card_verified INTEGER DEFAULT 0")
        conn.commit()
        print("[+] Agregada columna card_verified")
    else:
        print("[=] card_verified ya existe")

    # 2. Normalizar work_status
    cur.execute("""
        SELECT work_status, COUNT(*) FROM santander_hits GROUP BY work_status
    """)
    before = dict(cur.fetchall())
    print(f"[*] Estados antes: {before}")

    cur.execute("""
        UPDATE santander_hits SET work_status = 'ACTIVE'
        WHERE work_status IS NULL
           OR work_status NOT IN ('ACTIVE', 'SUCCESS', 'OFF')
    """)
    migrated = cur.rowcount
    conn.commit()

    cur.execute("SELECT work_status, COUNT(*) FROM santander_hits GROUP BY work_status")
    after = dict(cur.fetchall())
    print(f"[+] Estados después: {after} ({migrated} filas migradas)")

    # 3. Defaults
    cur.execute("UPDATE santander_hits SET work_status = 'ACTIVE' WHERE work_status IS NULL OR TRIM(work_status) = ''")
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM santander_hits WHERE card_verified = 1")
    verified = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM santander_hits")
    total = cur.fetchone()[0]
    print(f"[*] Hits totales: {total} | Con tarjeta verificada: {verified} | Pendientes de verificar: {total - verified}")

    conn.commit()
    conn.close()
    print("[✓] Migración completada")


if __name__ == "__main__":
    main()