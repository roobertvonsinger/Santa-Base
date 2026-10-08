"""Tamaño de la cola por banda de credito.

Pregunta que decide si el tramo que rinde (los que llegan a tarjeta, todos con
credito >= $484,000 segun medicion) ya se agoto o todavia queda material.
"""
import os
import sqlite3
import sys

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

# Pares (lo, hi) EXPLICITOS. La version anterior armaba `hi` con una cadena
# ternaria que devolvia hi == lo en tres bandas -> vacias por construccion.
BANDAS = [
    (0, 50000, "$0 - 50k"),
    (50000, 100000, "$50k - 100k"),
    (100000, 250000, "$100k - 250k"),
    (250000, 484000, "$250k - 484k"),
    (484000, 10 ** 9, "$484k + (donde llegan a tarjeta)"),
]

print("%-38s %12s" % ("banda de credito", "en cola"))
print("-" * 52)
total = 0
for lo, hi, etq in BANDAS:
    c.execute("""SELECT COUNT(*) FROM santander_records
                 WHERE results IS NULL AND curp IS NOT NULL
                   AND %s >= ? AND %s < ?""" % (CRED, CRED), (lo, hi))
    n = c.fetchone()[0]
    total += n
    print("%-38s %12d" % (etq, n))
print("-" * 52)
print("%-38s %12d" % ("TOTAL en cola", total))

c.execute("""SELECT COUNT(*), MIN(%s), MAX(%s) FROM santander_records
             WHERE results IS NULL AND curp IS NOT NULL""" % (CRED, CRED))
n, mn, mx = c.fetchone()
print()
print("cola completa: n=%d  credito min=%s  max=%s" % (n, mn, mx))

c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND curp IS NOT NULL AND %s >= 484000""" % CRED)
print("de los cuales con credito >= $484,000 (el tramo que rinde): %d"
      % c.fetchone()[0])
conn.close()