"""El bloque 1550k-1650k dio 0.0% calculable mientras los de al lado dan 93-95%.
Que tiene de especial? Si es basura estructural (rfc vacio, nombres rotos), el
sync no la va a poder calcular nunca y debe saltarsela, no releerla en cada
corrida.
"""
import os
import sqlite3

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

for lo, hi, etiqueta in ((1550000, 1650000, "malo 0.0%"),
                         (1650000, 1750000, "bueno 93.5%")):
    c.execute("SELECT COUNT(*) FROM santander_records WHERE id>=? AND id<?", (lo, hi))
    tot = c.fetchone()[0]
    c.execute("""SELECT COUNT(*) FROM santander_records
                 WHERE id>=? AND id<? AND results IS NOT NULL""", (lo, hi))
    res = c.fetchone()[0]
    c.execute("""SELECT COUNT(*) FROM santander_records
                 WHERE id>=? AND id<? AND LENGTH(TRIM(u6rfc))=13""", (lo, hi))
    rfc13 = c.fetchone()[0]
    c.execute("""SELECT COUNT(*) FROM santander_records
                 WHERE id>=? AND id<? AND curp IS NOT NULL AND TRIM(curp)!=''""", (lo, hi))
    curp = c.fetchone()[0]
    c.execute("""SELECT COUNT(*) FROM santander_records
                 WHERE id>=? AND id<? AND dmname IS NOT NULL AND TRIM(dmname)!=''""", (lo, hi))
    nombre = c.fetchone()[0]
    print("BLOQUE %s (id %d-%d)" % (etiqueta, lo, hi))
    print("   filas totales          : %d" % tot)
    print("   results NO nulo        : %d  (ya procesadas -> el sync las salta)" % res)
    print("   RFC de 13 chars        : %d" % rfc13)
    print("   con CURP ya calculada  : %d" % curp)
    print("   con dmname             : %d" % nombre)
    c.execute("""SELECT id, u6rfc, dmname, results, u6estado FROM santander_records
                 WHERE id>=? AND id<? AND results IS NULL
                 AND LENGTH(TRIM(u6rfc))=13 LIMIT 3""", (lo, hi))
    for r in c.fetchall():
        print("   ej: id=%s rfc=%r nombre=%r results=%r est=%r" % r)
    print()

c.execute("""SELECT LENGTH(TRIM(u6rfc)) L, COUNT(*) FROM santander_records
             WHERE id>=1550000 AND id<1650000 GROUP BY 1 ORDER BY 2 DESC LIMIT 6""")
print("bloque malo, por longitud de RFC:")
for L, n in c.fetchall():
    print("   %s chars: %d" % (L, n))
conn.close()