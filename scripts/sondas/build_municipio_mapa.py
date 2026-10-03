"""Construye el mapa municipio -> estado CURP a partir de los propios datos.

u6estado a veces trae el municipio en vez del estado ("MONTERREY", "MERIDA",
"CUERNAVACA,MOR"). No hace falta un catalogo externo: para cada municipio de
u6delomu se toma el u6estado MODAL de las filas donde u6estado SI es un estado
valido. Es la misma fuente, ya presente en la base.

Salida: scripts/municipio_estado.json
"""
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import ESTADO_CURP, sin_acentos  # noqa: E402

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'municipio_estado.json')


def norm(s):
    return " ".join(sin_acentos(s or '').upper().split())


def es_estado_valido(s):
    e = norm(s)
    if e in ESTADO_CURP:
        return True
    for k in ESTADO_CURP:
        kk = norm(k)
        if kk and (kk in e or e in kk):
            return True
    return False


conn = sqlite3.connect(DB)
c = conn.cursor()

print("1) Muestreando filas donde u6estado SI es estado valido...")
c.execute("""SELECT u6delomu, u6estado FROM santander_records
             WHERE u6delomu IS NOT NULL AND TRIM(u6delomu) != ''
               AND u6estado IS NOT NULL AND TRIM(u6estado) != ''
               AND LENGTH(TRIM(u6rfc)) = 13
             LIMIT 1500000""")
pares = c.fetchall()
print("   pares leidos: %d" % len(pares))

modal = defaultdict(Counter)
for muni, edo in pares:
    if es_estado_valido(edo):
        modal[norm(muni)][norm(edo)] += 1

mapa = {}
for muni, cnt in modal.items():
    mapa[muni] = cnt.most_common(1)[0][0]
print("2) municipios con estado inferido: %d" % len(mapa))

# ejemplo de los que fallaban
print("3) Los que fallaban en el lote, ya resueltos:")
for m in ("MONTERREY", "MEXICALI", "REYNOSA", "CUERNAVACA,MOR", "SAN NICOLAS DE LOS G",
          "MERIDA", "ZAPOPAN", "MORELIA", "CIUDAD JUAREZ"):
    print("   %-24s -> %s" % (m, mapa.get(m, "SIN MAPA")))

# que queda sin resolver
c.execute("""SELECT u6estado, COUNT(*) FROM santander_records
             WHERE (curp IS NULL OR TRIM(curp)='')
               AND u6rfc IS NOT NULL AND LENGTH(TRIM(u6rfc)) = 13
               AND u6estado IS NOT NULL AND TRIM(u6estado) != ''
             GROUP BY 1 ORDER BY 2 DESC LIMIT 4000""")
dist = c.fetchall()
sin_mapa = []
for edo, n in dist:
    e = norm(edo)
    if es_estado_valido(e):
        continue
    if e in mapa:
        continue
    sin_mapa.append((edo, n))
print()
print("4) u6estado que NO son estado y NO aparecen como municipio: %d valores, %d filas"
      % (len(sin_mapa), sum(n for _, n in sin_mapa)))
for edo, n in sin_mapa[:25]:
    print("   %-34s %d" % (edo, n))

with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump(mapa, fh, ensure_ascii=False, indent=0)
print()
print("escrito: %s (%d entradas)" % (OUT, len(mapa)))
conn.close()