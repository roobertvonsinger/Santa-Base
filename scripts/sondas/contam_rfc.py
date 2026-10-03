"""Las filas con yy=00/01 (7,491 filas) huelen a fecha de relleno 010101.

Muestra los nombres, estados y patron de esas filas contra una muestra normal.
Si '01/01/01' es un DEFAULT de carga y no una fecha real, no son personas de
2001 y hay que descartarlas, no calcularles una CURP.
"""
import os
import sqlite3
from collections import Counter

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

print("Muestra de filas con fecha 01/01/01 (yy=00):")
c.execute("""SELECT id, u6rfc, dmname, u6estado FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND SUBSTR(u6rfc,5,6)='000101' LIMIT 12""")
for r in c.fetchall():
    print("   %s" % (r,))

print()
print("Que RFC/4 tienen esas filas? (NNNN = relleno)")
c.execute("""SELECT SUBSTR(u6rfc,1,4), COUNT(*) FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND SUBSTR(u6rfc,5,6)='000101'
             GROUP BY 1 ORDER BY 2 DESC LIMIT 10""")
for r in c.fetchall():
    print("   %s : %d" % r)

print()
print("Estructura de fecha: cuantas filas tienen fecha valida vs 01/01/01")
c.execute("""SELECT
               SUM(CASE WHEN SUBSTR(u6rfc,9,2)='01' AND SUBSTR(u6rfc,7,2)='01'
                         AND SUBSTR(u6rfc,5,2)='01' THEN 1 ELSE 0 END) AS relleno_010101,
               COUNT(*) AS total
             FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13""")
r = c.fetchone()
print("   fecha=010101: %d / %d = %.2f%%" % (r[0], r[1], 100.0*r[0]/r[1]))

print()
print("Los otros campos tambien son relleno? muestra de 010101:")
c.execute("""SELECT u6acct, dmcity, dmzip, u6tel1, dmaddr1 FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND SUBSTR(u6rfc,5,6)='000101' LIMIT 6""")
for r in c.fetchall():
    print("   acct=%-18s city=%-16s zip=%-8s tel=%-12s addr=%s" % r)

print()
print("Nombres mas comunes en 010101 (los mas repetidos = relleno de carga):")
c.execute("""SELECT dmname, COUNT(*) c FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND SUBSTR(u6rfc,5,6)='000101'
             GROUP BY 1 ORDER BY c DESC LIMIT 8""")
for r in c.fetchall():
    print("   %-40s %d" % (r[0], r[1]))

print()
print("Mismo top de nombres en una fecha NORMAL (1948) para comparar:")
c.execute("""SELECT dmname, COUNT(*) c FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND SUBSTR(u6rfc,5,6)='480415'
             GROUP BY 1 ORDER BY c DESC LIMIT 8""")
for r in c.fetchall():
    print("   %-40s %d" % (r[0], r[1]))

conn.close()