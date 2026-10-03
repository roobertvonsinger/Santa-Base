"""Que queda sin codigo de estado y por que. 809 valores / 5,895 filas."""
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import codigo_estado, sin_acentos  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT u6estado, COUNT(*) n FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND u6estado IS NOT NULL AND TRIM(u6estado)!=''
             GROUP BY 1 ORDER BY n DESC""")
todos = c.fetchall()
conn.close()

des = [(e, n) for e, n in todos if not codigo_estado(e)]
print("SIN codigo: %d valores, %d filas" % (len(des), sum(n for _, n in des)))
print()

# clasifica por forma
formas = Counter()
for e, n in des:
    s = e.strip()
    if s.startswith('"') and s.endswith('"'):
        formas['entrecomillado'] += n
    elif "," in s or ";" in s:
        formas['compuesto sin sufijo conocido'] += n
    else:
        formas['municipio suelto'] += n
for k, v in formas.most_common():
    print("  %-32s %8d filas" % (k, v))
print()
print("Top 45 exactos:")
for e, n in des[:45]:
    print("  %-42s %6d" % (e[:42], n))
print()
print("Todos los compuestos (municipio,sufijo) que faltan:")
for e, n in des:
    if "," in e or ";" in e:
        print("  %-46s %6d" % (e[:46], n))