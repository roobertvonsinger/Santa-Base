"""¿El pool tiene colisiones de nombre? El grupo C mostró dos filas con
dmname='ALMA EVANGELINA SOTO RODRIGUEZ' pero iniciales RFC distintas
(SORA y MSOT). Si eso es sistematico, significa que el RFC de la fila no
corresponde al nombre de la fila y las iniciales no son de fiar.
"""
import os
import sqlite3
from collections import Counter

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

# 1. el caso concreto
c.execute("""SELECT id, u6rfc, dmname, u6acct, u6estado, dmcity, results
             FROM santander_records
             WHERE dmname='ALMA EVANGELINA SOTO RODRIGUEZ'""")
print("Filas con ese nombre:")
for r in c.fetchall():
    print("   id=%-8s rfc=%-16s acct=%-18s estado=%-16s city=%-12s results=%s"
          % (r[0], r[1], r[3], r[4] or '', r[5] or '', str(r[6])[:22]))

# 2. colision general: mismo nombre, iniciales RFC distintas
c.execute("""SELECT COUNT(*) FROM (
               SELECT dmname FROM santander_records
               WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
                 AND dmname IS NOT NULL AND TRIM(dmname)!=''
               GROUP BY dmname
               HAVING COUNT(DISTINCT SUBSTR(u6rfc,1,4)) > 1
             )""")
n_col = c.fetchone()[0]
c.execute("""SELECT COUNT(DISTINCT dmname) FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND dmname IS NOT NULL AND TRIM(dmname)!=''""")
n_nom = c.fetchone()[0]
print()
print("Nombres distintos en el pool: %d" % n_nom)
print("Nombres que aparecen con MAS DE UN juego de iniciales RFC: %d (%.2f%%)"
      % (n_col, 100.0 * n_col / max(1, n_nom)))

# 3. cuantas filas son de esos nombres duplicados
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND dmname IN (
                 SELECT dmname FROM santander_records
                 WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
                   AND dmname IS NOT NULL AND TRIM(dmname)!=''
                 GROUP BY dmname HAVING COUNT(DISTINCT SUBSTR(u6rfc,1,4)) > 1
               )""")
print("Filas afectadas por esa ambiguedad: %d" % c.fetchone()[0])

# 4. ejemplo grande de colision
print()
print("Ejemplos de nombres con iniciales RFC distintas:")
c.execute("""SELECT dmname, GROUP_CONCAT(DISTINCT SUBSTR(u6rfc,1,4)),
                    COUNT(*) n
             FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND dmname IS NOT NULL AND TRIM(dmname)!=''
             GROUP BY dmname
             HAVING COUNT(DISTINCT SUBSTR(u6rfc,1,4)) > 1
             ORDER BY n DESC LIMIT 12""")
for nom, inis, n in c.fetchall():
    print("   %-36s %-22s x%d" % (nom[:36], (inis or '')[:22], n))
conn.close()