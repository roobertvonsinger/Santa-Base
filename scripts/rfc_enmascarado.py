"""Cuantos RFCs del pool estan ENMASCARADOS con X y no son RFCs reales.

'XXXX000101XXX' pasa mi validacion actual (isalpha / isdigit) porque X y 0-9
son letras y digitos respectivamente. Hay que rechazarlos: una CURP que empieza
con XXXX no existe en RENAPO.

Ademas mide cuantas de las 717 filas de referencia son de ese tipo, porque si
no, el '98.19% de acierto' de la linea base esta contaminado.
"""
import os
import sqlite3

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND UPPER(u6rfc) LIKE '%X%'""")
pool = c.fetchone()[0]
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13""")
total = c.fetchone()[0]
print("Pool con RFC de 13 chars: %d" % total)
print("  de esos, con alguna X (enmascarados): %d  (%.3f%%)" % (pool, 100.0*pool/total))

c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND UPPER(u6rfc) LIKE '____%'""")
solo4 = c.fetchone()[0]
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND UPPER(SUBSTR(u6rfc,1,4))='XXXX'""")
xxxx = c.fetchone()[0]
print("  con los primeros 4 chars en blanco/guion : %d" % solo4)
print("  con prefijo exacto 'XXXX'               : %d" % xxxx)

print()
print("Referencia de las 717 (las que use para medir el 98.19%):")
c.execute("""SELECT COUNT(*),
                  SUM(CASE WHEN UPPER(u6rfc) LIKE '%X%' THEN 1 ELSE 0 END)
             FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18""")
n, x = c.fetchone()
print("  filas con CURP real: %d   de las cuales con RFC enmascarado: %d" % (n, x))
print("  linea base limpia: %d de %d" % (n - x, n))

print()
print("Formas concretas de RFC enmascarado:")
c.execute("""SELECT UPPER(u6rfc), COUNT(*) c FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND UPPER(u6rfc) LIKE '%X%'
             GROUP BY 1 ORDER BY c DESC LIMIT 12""")
for r in c.fetchall():
    print("   %-16s %d" % r)

print()
print("Y con la CURP ya calculada (cuantas quedaron escritas con RFC enmascarado):")
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE curp IS NOT NULL AND TRIM(curp)!='' AND results IS NULL
               AND UPPER(u6rfc) LIKE '%X%'""")
print("   %d" % c.fetchone()[0])

conn.close()