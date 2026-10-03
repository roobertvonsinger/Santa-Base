"""Cuantos filenames pierde el pool por falta de nombre en el lexico, y cuales.

16.56% de las filas del pool se descartan con `sexo_nombre_desconocido`, y
peor: varias son MUJERES y produce una CURP con H que RENAPO rechaza.
Se imprime el top para ampliar _FEM/_MASC con lo que mas se repita.
"""
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import curp_calc as cc  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT u6rfc, dmname, u6estado FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND dmname IS NOT NULL AND TRIM(dmname)!=''
               AND u6estado IS NOT NULL AND TRIM(u6estado)!=''
             LIMIT 400000""")
pool = c.fetchall()
conn.close()

des = Counter()
filas_por_nombre = Counter()
for rfc, nom, est in pool:
    calc, det = cc.calcular_curp(nom, rfc, est)
    if calc is None:
        mot = str(det)
        if mot.startswith("sexo_nombre_desconocido:"):
            nom_ = mot.split(":", 1)[1]
            des[nom_] += 1
            filas_por_nombre[nom_] += 1

print("Descartes por nombre desconocido: %d nombres distintos" % len(des))
print("Top 120 (ampliar _FEM/_MASC con estos):")
print("  %-26s %9s" % ("NOMBRE DADO", "FILAS"))
tot = 0
for n, k in des.most_common(120):
    print("  %-26s %9d" % (n[:26], k))
    tot += k
print()
print("Top-120 cubren %d filas de %d descartadas" % (tot, sum(des.values())))