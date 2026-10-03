"""Impacto del fix de homoclave: cuantas filas del pool caen en la banda rota 02-61.

Regla actual : 'A' si anio < 50  (o sea yy 00-49 -> "nacio 2000-2049")
Regla correg.: 'A' solo si yy <= 01 (nacio 2000-2001); todo lo demas es 19xx

Evidencia: las 717 CURPs reales solo tienen yy 00,01 (->A) y yy 62-86 (->0).
No hay ni un registro en 02-61, que es justo donde mi regla actual se equivoca.
"""
import os
import sqlite3
from collections import Counter

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT SUBSTR(u6rfc,5,2), COUNT(*)
             FROM santander_records
             WHERE results IS NULL AND u6rfc IS NOT NULL
               AND LENGTH(TRIM(u6rfc)) = 13
             GROUP BY 1 ORDER BY 1""")
bandas = dict(c.fetchall())
conn.close()

tot = sum(bandas.values())
print("Pool de 4.86M, distribucion del anio (u6rfc[4:6]):")
print("=" * 60)
rota = 0
for yy in sorted(bandas):
    n = bandas[yy]
    y = int(yy)
    if y > 1:
        marca = "  <-- mi regla pone 'A' (nacio 20%s), incorrecto" % yy if y < 50 else ""
    else:
        marca = "  <- 'A' correcto (nacio 20%s)" % yy
    if 1 < y < 50:
        rota += n
    print("  19%s/20%s : %8d%s" % (yy, yy, n, marca))

print()
print("  TOTAL filas afectadas por el fix: %d  (%.2f%% del pool)"
      % (rota, 100.0 * rota / max(1, tot)))
print()
print("  Con el fix, el pool queda con homoclave '0' en %d filas (%.2f%%)"
      % (tot - sum(bandas.get(str(y), 0) for y in (0, 1)),
         100.0 * (tot - sum(bandas.get(str(y), 0) for y in (0, 1))) / max(1, tot)))
print("  y 'A' en solo %d." % sum(bandas.get(str(y), 0) for y in (0, 1)))