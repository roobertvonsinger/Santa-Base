"""Construye el mapa municipio -> entidad CURP y lo mete en curp_calc.

`u6estado` no siempre trae la entidad: a veces trae el MUNICIPIO
('MONTERREY', 'ZAPOPAN', 'MEXICALI') o varios ('CUERNAVACA,MOR'). Esos casos se
descartan hoy con `estado_desconocido` = 0.63% del pool (1260 de cada 200,000).

Se arma el mapa con los municipios que REALMENTE aparecen en u6estado, no con
los 2,463 de Mexico: lo que importa es la cobertura del pool.
"""
import os
import re
import sqlite3
import sys
from collections import Counter

re_split = re.compile(r"[,;]").split

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import ESTADO_CURP, codigo_estado, sin_acentos  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("""SELECT u6estado, COUNT(*) n FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND u6estado IS NOT NULL AND TRIM(u6estado)!=''
             GROUP BY 1 ORDER BY n DESC""")
todos = c.fetchall()
conn.close()

desconocidos = [(e, n) for e, n in todos if not codigo_estado(e)]
print("u6estado distintos: %d" % len(todos))
print("  con codigo resuelto hoy : %d  (%d filas)"
      % (len(todos) - len(desconocidos),
         sum(n for _, n in todos) - sum(n for _, n in desconocidos)))
print("  SIN codigo (a mapear)   : %d  (%d filas)"
      % (len(desconocidos), sum(n for _, n in desconocidos)))
print()

print("Top 60 de los SIN codigo (el mapa tiene que cubrir estos):")
print("  %-34s %9s   %s" % ("u6estado", "FILAS", "CODIGO REAL"))
for e, n in desconocidos[:60]:
    e1 = " ".join(sin_acentos(e).upper().split())
    cod = ""
    if "," in e1 or ";" in e1:
        for sep in (",", ";"):
            if sep in e1:
                partes = [p.strip() for p in e1.split(sep) if p.strip()]
                for p in partes:
                    if p in ("MOR", "MEX", "PUE", "VER", "SIN", "JAL",
                             "GUA", "YUC", "QUE", "NLE", "CHP", "BCS"):
                        cod = p + " <- probable"
                if not cod:
                    cod = partes[-1] + " <- sufijo"
                break
    else:
        cod = "(municipio, falta el estado)"
    print("  %-34s %9d   %s" % (e[:34], n, cod))

print()
print("Sufijos de estado que aparecen en los compuestos:")
suf = Counter()
for e, n in desconocidos:
    e1 = " ".join(sin_acentos(e).upper().split())
    if "," in e1 or ";" in e1:
        partes = [p.strip() for p in re_split(e1) if p.strip()]
        if len(partes) > 1:
            suf[partes[-1]] += n
for k, v in suf.most_common(45):
    cod = ESTADO_CURP.get(k, "")
    print("  %-6s %9d  -> %s" % (k, v, cod or "SIN MAPA"))