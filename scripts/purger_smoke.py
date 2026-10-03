"""El purger ya ve candidatos: smoke test de build_segment_query.

Antes de arrancar el servicio hay que confirmar que el SELECT que alimenta al
purger devuelve filas DESPUES del sync, con los segmentos que realmente se van
a usar. Antes del sync devolvia 0 (por eso la boveda estaba vacia).
"""
import os
import sqlite3
import sys

sys.path.insert(0, r'C:\Users\rober\Dropbox\TESTING DEV\repos\santa-base')
from santander_purger import build_segment_query  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')

SEGMENTOS = [
    ("estado", "NUEVO LEON", None, None),
    ("estado", "DISTRITO FEDERAL", None, None),
    ("estado", "JALISCO", None, None),
    ("estado", "MONTERREY", None, None),          # municipio -> debe resolver NL
    ("estado", None, None, "1970-01-01"),          # born_after
    ("estado", None, None, "1990-01-01"),
]

for nombre, estado, mc, ba in SEGMENTOS:
    sql, params = build_segment_query(estado=estado, born_after=ba)
    conn = sqlite3.connect(DB)
    try:
        conn.execute("PRAGMA busy_timeout=15000")
        total = conn.execute("SELECT COUNT(*) FROM (%s)" % sql, params).fetchone()[0]
        filas = conn.execute(
            "SELECT * FROM (%s) LIMIT 3" % sql, params).fetchall()
    finally:
        conn.close()
    print("=" * 74)
    print("SEGMENTO %-8s estado=%-22r born_after=%r" % (nombre, estado, ba))
    print("  filas que devuelve: %d" % total)
    for f in filas:
        print("   id=%-8s curp=%-20s rfc=%-16s %-34s est=%s"
              % (f[0], f[2], f[3], (f[4] or '')[:34], f[5]))