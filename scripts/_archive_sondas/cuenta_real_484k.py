"""¿Por qué 'RESTAN >= $484k' no baja aunque el purger produzca OFF?

Hipótesis: mi conteo y el purger NO filtered igual. El purger aplica ademas
`born_after` (SUBSTR(u6rfc,5,6) >= 'YYMMDD'), que la sonda no aplicaba. Si las
491 filas son justamente las que no pasan ese filtro, el daemon NUNCA las va a
tocar y mi numero esta mal, no el pool.

Compara las tres cifras:
  A) conteo crudo (lo que reportaba la sonda)
  B) con el filtro de nacimiento que usa el purger en verdad
  C) lo que el purger ya agarro de esa banda
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from umbral import BORN_AFTER, born_after_YYYYMMDD  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
CRED = ("CAST(REPLACE(REPLACE(COALESCE(u6licrea,'0'),'$',''),',','') "
        "AS INTEGER)")
BASE = ("FROM santander_records WHERE results IS NULL "
        "AND curp IS NOT NULL AND %s >= 484000" % CRED)
CORTE = born_after_YYYYMMDD()

conn = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
c = conn.cursor()

c.execute("SELECT COUNT(*) " + BASE)
a = c.fetchone()[0]
print("A) crudo, sin filtro de nacimiento      : %d" % a)

# El corte real viene de santander_purger.BORN_AFTER_DEFAULT, no de un '600101'
# pegado a mano: antes esta sonda usaba 1960 mientras el purger corria 1963, y
# por eso reportaba material que jamas iba a existir.
c.execute("SELECT COUNT(*) " + BASE + " AND SUBSTR(u6rfc, 5, 6) >= ?",
          (CORTE,))
b = c.fetchone()[0]
print("B) con born-after %s (el real)  : %d" % (BORN_AFTER, b))
print("   descartadas por nacimiento             : %d" % (a - b))

c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NOT NULL AND %s >= 484000""" % CRED)
print("C) ya procesadas en esa banda           : %d" % c.fetchone()[0])

c.execute("SELECT COUNT(*) FROM santander_hits")
print()
print("boveda                                  : %d" % c.fetchone()[0])

# Muestra de las que el purger NO puede tomar por el filtro de nacimiento
c.execute("SELECT id, u6rfc, dmname, u6licrea " + BASE +
          " AND SUBSTR(u6rfc, 5, 6) < ? LIMIT 4", (CORTE,))
print()
print("muestra de las que el purger NO agarra por edad:")
for r in c.fetchall():
    print("   id=%-9s rfc=%-14s nac=%s %s" % (r[0], r[1], r[1][4:10], (r[2] or "")[:30]))

print()
if a - b > 0:
    print("CONCLUSION: la sonda contara %d fila(s) que el purger nunca va a tocar"
          % (a - b))
    print("por el filtro de edad. El numero real de material aprovechable es %d."
          % b)
else:
    print("CONCLUSION: el filtro de edad no explica nada. Hay que medir otra cosa.")
conn.close()