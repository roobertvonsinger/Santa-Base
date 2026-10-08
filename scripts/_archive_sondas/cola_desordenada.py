"""Las filas que el sync no puede calcular son de otra fuente, no del pool humano.

95.7% de las ultimas filas se descartan por `sexo_nombre_desconocido`, y los
RFC que salen (AUMG800206V89, VIPM480202I16, BAMA760625QS3) no son de persona
fisica mexicana normal. Se mira que son y si conviene calcularlas o dejarlas.

La pregunta operativa: ¿el 8.57% de descarte es HOMOGENEO o son bloques de
basura? Si es basura concentrada, el sync no tiene que recalcularlas 100 veces
en cada corrida.
"""
import os
import sqlite3
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import curp_calc as cc  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

# muestra de las filas que el sync no puede calcular
c.execute("""SELECT id, u6rfc, dmname, u6estado, dmcity FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND (curp IS NULL OR TRIM(curp)='')
               AND dmname IS NOT NULL
             ORDER BY id LIMIT 3000""")
filas = c.fetchall()

desc = []
ok = []
for id_, rfc, nom, est, city in filas:
    calc, det = cc.calcular_curp(nom, rfc, est)
    (ok if calc else desc).append((id_, rfc, nom, est, city, det))

print("Muestra de 3,000 filas pendientes, separadas por si se pueden calcular:")
print("  calculables: %d    no calculables: %d" % (len(ok), len(desc)))
print()
print("MUESTRA de las NO calculables (nombre -> motivo):")
vistos = set()
for id_, rfc, nom, est, city, det in desc[:40]:
    mot = str(det).split(":")[0]
    clave = (nom[:14], mot)
    if clave in vistos:
        continue
    vistos.add(clave)
    print("   %-30s %-14s rfc=%-15s est=%-18s %s"
          % ((nom or '')[:30], mot, rfc, (est or '')[:18], city or ''))
    if len(vistos) >= 30:
        break

# los motivos desglosados
print()
motivos = Counter()
for _, _, nom, _, _, det in desc:
    motivos[str(det)] += 1
print("Motivos exactos (top 25):")
for k, v in motivos.most_common(25):
    print("   %-46s %5d" % (k[:46], v))

# ¿son bloques contiguos por id?
print()
ids_desc = sorted(f[0] for f in desc)
ids_ok = sorted(f[0] for f in ok)
if ids_desc and ids_ok:
    print("Rango de ids NO calculables: %d .. %d" % (ids_desc[0], ids_desc[-1]))
    print("Rango de ids calculables    : %d .. %d" % (ids_ok[0], ids_ok[-1]))
    print("¿se mezclan? %s" % ("NO, son bloques separados" if ids_ok[-1] < ids_desc[0]
                               or ids_desc[-1] < ids_ok[0] else "SI, intercalados"))
conn.close()