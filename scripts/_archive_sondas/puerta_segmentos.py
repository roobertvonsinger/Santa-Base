"""Comprueba que la boveda de hits ya recibe candidatos.

`build_segment_query` filtra `curp IS NOT NULL` (santander_purger.py:84), y por
eso la boveda salio vacia: solo 717 filas Tenian CURP. Ahora hay 985,899 y el
sync sigue corriendo. Esta es la PUERTA que tiene que verse en verde antes de
arrancar el purger -- si un segmento no devuelve candidatos, el purger se
queda sin comer y la culpa no es suya.
"""
import os
import sqlite3
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _RAIZ)
from santander_purger import build_segment_query  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

# puerta global: sin filtro de estado
sql, params = build_segment_query(limit=5)
n = c.execute("SELECT COUNT(*) FROM (%s)" % sql, params).fetchone()[0]
print("PUERTA global (sin filtro): %d filas" % n)
print()

c.execute("""SELECT u6estado, COUNT(*) FROM santander_records
             WHERE curp IS NOT NULL AND TRIM(curp)!=''
               AND results IS NULL AND u6estado IS NOT NULL
               AND TRIM(u6estado)!=''
             GROUP BY 1 ORDER BY 2 DESC LIMIT 8""")
print("Segmentos reales y su puerta:")
print("  %-30s %10s %10s" % ("u6estado", "en pool", "puerta"))
fallas = 0
for est, pool_n in c.fetchall():
    sql, params = build_segment_query(estado=est, limit=5)
    puerta = c.execute("SELECT COUNT(*) FROM (%s)" % sql, params).fetchone()[0]
    marca = "" if puerta > 0 else "   <-- VACIO"
    if puerta == 0:
        falhas += 1
    print("  %-30s %10d %10d%s" % (est[:30], pool_n, puerta, marca))

print()
# estados que pediran, incluyendo los que el pool usa con variantes
print("Estados con mayor cobertura:")
c.execute("""SELECT u6estado, COUNT(*) FROM santander_records
             WHERE curp IS NOT NULL AND TRIM(curp)!=''
               AND results IS NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")
for est, pool_n in c.fetchall():
    sql, params = build_segment_query(estado=est, limit=5)
    puerta = c.execute("SELECT COUNT(*) FROM (%s)" % sql, params).fetchone()[0]
    print("  %-30s %10d -> puerta %d" % (est[:30], pool_n, puerta))
conn.close()
print()
print("Segmentos vacios: %d" % fallas)
sys.exit(1 if n == 0 else 0)