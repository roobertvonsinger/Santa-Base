"""¿Está rindiendo el tramo $250k-484k, que es de donde viene todo ahora?

El tramo >= $484k se agotó (las 491 que quedaban eran de 1948-1959 y el purger
filtra born-after 1963). Todo lo que el daemon produce sale de la banda de
abajo. Si esa banda no rinde, hay que medir la siguiente ($100k-250k) ANTES de
gastar 4.5M de requests en material peor.

Solo lee: agrupa por banda de crédito y compara contra el mismo filtro de
nacimiento que usa el purger de verdad.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from umbral import born_after_sql, config_efectiva_purger  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
CRED = ("CAST(REPLACE(REPLACE(COALESCE(u6licrea,'0'),'$',''),',','') "
        "AS INTEGER)")

conn = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
c = conn.cursor()

BANDAS = [
    (250000, 484000, "$250k - 484k"),
    (100000, 250000, "$100k - 250k"),
    (50000, 100000, "$50k - 100k"),
    (0, 50000, "$0 - 50k"),
]


def etapa(res):
    res = res or ""
    if res == "HIT" or res.startswith("HIT"):
        return "HIT"
    if "tarjeta inactiva" in res:
        return "TARJETA"
    return "OFF"


print("corte de edad en vigor: %s" % config_efectiva_purger())
print()
print("%-16s %10s %10s %10s %8s %9s %9s"
      % ("banda", "en cola", "ya proc.", "OFF", "TARJETA", "HIT", "tasa HIT"))
print("-" * 82)
for lo, hi, etq in BANDAS:
    c.execute("""SELECT COUNT(*) FROM santander_records
                 WHERE results IS NULL AND curp IS NOT NULL
                   AND %s >= ? AND %s < ? AND %s"""
              % (CRED, CRED, born_after_sql()), (lo, hi))
    cola = c.fetchone()[0]
    c.execute("""SELECT results FROM santander_records
                 WHERE results IS NOT NULL AND %s >= ? AND %s < ?"""
              % (CRED, CRED), (lo, hi))
    filas = c.fetchall()
    n_off = sum(1 for (r,) in filas if etapa(r) == "OFF")
    n_tar = sum(1 for (r,) in filas if etapa(r) == "TARJETA")
    n_hit = sum(1 for (r,) in filas if etapa(r) == "HIT")
    tot = n_off + n_tar + n_hit
    tasa = (100.0 * n_hit / tot) if tot else 0.0
    print("%-16s %10d %10d %10d %8d %9d %8.2f%%"
          % (etq, cola, tot, n_off, n_tar, n_hit, tasa))

c.execute("SELECT COUNT(*) FROM santander_hits")
print()
print("boveda: %d" % c.fetchone()[0])
conn.close()