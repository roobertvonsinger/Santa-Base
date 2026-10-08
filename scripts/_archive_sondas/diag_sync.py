"""Por que el sync se ralentiza: lee 100,000 y escribe 5.

Sospecha: falta indice sobre las columnas del WHERE, asi que cada lote hace un
full scan de 4.86M filas Y ademas vuelve a traer filas ya calculadas que
el filtro `(curp IS NULL OR TRIM(curp)='')` deberia haber excluido.

Se mide:
  1. indices actuales sobre santander_records
  2. cuantos-processedCURPs vs descartadas de verdad
  3. que tan rapido es el SELECT del lote
"""
import os
import sqlite3
import time

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

print("1) INDICES actuales:")
c.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='santander_records'")
idx = c.fetchall()
if not idx:
    print("   NINGUNO -- cada lote hace full scan de 4.86M filas")
for name, sql in idx:
    print("   %-30s %s" % (name, sql))

print()
print("2) El lote lee filas que ya estan calculadas (el filtro no las excluye):")
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND (curp IS NOT NULL AND TRIM(curp)!='')""")
ya = c.fetchone()[0]
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND (curp IS NULL OR TRIM(curp)='')""")
pend = c.fetchone()[0]
print("   con CURP ya escrita: %d" % ya)
print("   pendientes de calc : %d" % pend)
print("   -> de las 100,000 que lee el ultimo lote, %d ya estaban hechas" % ya)

print()
print("3) Velocidad del SELECT del lote (LIMIT 100000):")
t0 = time.time()
c.execute("""SELECT id, u6rfc, dmname, u6estado FROM santander_records
             WHERE (curp IS NULL OR TRIM(curp) = '')
               AND results IS NULL
               AND u6rfc IS NOT NULL AND LENGTH(TRIM(u6rfc)) = 13
             ORDER BY id LIMIT 100000""")
filas = c.fetchall()
dt = time.time() - t0
print("   traxo %d filas en %.2fs" % (len(filas), dt))

print()
print("4) Por que escribio solo 5? Muestra de esas filas:")
import sys
sys.path.insert(0, 'scripts')
import curp_calc as cc
from collections import Counter
st = Counter()
for id_, rfc, nom, est in filas[:5000]:
    calc, det = cc.calcular_curp(nom, rfc, est)
    st["ok" if calc else str(det).split(":")[0]] += 1
for k, v in st.most_common():
    print("   %-34s %6d  (%.1f%%)" % (k, v, 100.0 * v / 5000))

print()
print("5) Estas filas YA tienen curp no vacio? (muestra)")
c.execute("""SELECT id, u6rfc, curp FROM santander_records
             WHERE id IN (%s) LIMIT 5""" % ",".join(str(f[0]) for f in filas[:5]))
for r in c.fetchall():
    print("   id=%-9s rfc=%-16s curp_en_bd=%r" % r)
conn.close()