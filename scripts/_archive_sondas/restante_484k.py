"""Cuanto falta del tramo que rinde (credito >= $484,000) y cuantos hits van.

El daemon se detiene solo cuando esto llegue a 0.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from umbral import born_after_sql, config_efectiva_purger  # noqa: E402

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

# ANTES contaba sin el filtro de nacimiento y por eso daba 491 clavado para
# siempre: el purger corre con --born-after 1963-01-01 y esas 491 son de
# 1948-1959, material que NO puede tomar. El conteo honesto lleva el filtro,
# y el filtro se importa de `umbral` para no volver a pegarlo a mano con un
# valor distinto al del purger (que es como se mentia en primer lugar).
print("corte de edad en vigor: %s" % config_efectiva_purger())
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND curp IS NOT NULL
               AND %s >= 484000 AND %s"""
          % (CRED, born_after_sql()))
resto = c.fetchone()[0]
print("RESTAN en el tramo >= $484k : %d" % resto)

c.execute("SELECT COUNT(*) FROM santander_hits")
print("BOVEDA (hits reales)        : %d" % c.fetchone()[0])

c.execute("SELECT COUNT(*) FROM santander_records WHERE results='HIT'")
print("marcados HIT en records     : %d" % c.fetchone()[0])

c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND curp IS NOT NULL AND %s < 484000"""
          % CRED)
print("fuera del tramo (no se toca): %d" % c.fetchone()[0])
conn.close()