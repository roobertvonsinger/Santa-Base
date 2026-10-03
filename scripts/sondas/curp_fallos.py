"""Los 6 casos donde mi calculador no reproduce una CURP que RENAPO ACEPTO.
Si pos 1-3 fallan, pos17 'falla' por consecuencia (el digito depende de todo).
Muestra el caso completo para ver la regla que me falta.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import calcular_curp, _particulas  # noqa: E402

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT u6rfc, dmname, genero, estado, curp, results, u6estado
             FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18
               AND (results IS NULL OR (results NOT LIKE '%RENAPO%'
                                        AND results NOT LIKE '%operador%'))""")
rows = c.fetchall()
conn.close()

print("FALLOS del calculador sobre CURPs ACEPTADAS por RENAPO")
print()
for rfc, nom, gen, ed, curp, res, u6ed in rows:
    real = curp.strip().upper()
    calc, _ = calcular_curp(nom, rfc, ed or u6ed, genero_col=gen)
    if not calc or calc == real:
        continue
    diff = [i for i in range(18) if calc[i] != real[i]]
    partes = _particulas(nom).split()
    print("   nombre : %s" % nom)
    print("   partes : %s   (paterno=%s materno=%s dados=%s)"
          % (partes, partes[-2] if len(partes) > 1 else '-',
             partes[-1], partes[:-2]))
    print("   rfc    : %s   curp real: %s" % (rfc, real))
    print("   calc   : %s   difiere en %s" % (calc, diff))
    print("   ini    : real=%s  rfc=%s" % (real[:4], rfc[:4]))
    print()

# Distribucion de fallos por posicion en las ACEPTADAS
from collections import Counter  # noqa: E402
dc = Counter()
tot = 0
for rfc, nom, gen, ed, curp, res, u6ed in rows:
    real = curp.strip().upper()
    calc, _ = calcular_curp(nom, rfc, ed or u6ed, genero_col=gen)
    if not calc:
        continue
    tot += 1
    for i in range(18):
        if calc[i] != real[i]:
            dc[i] += 1
print("fallos por posicion sobre %d aceptadas: %s" % (tot, dict(sorted(dc.items()))))

# y el detalle de las iniciales: pos1 y pos2 son paterno/materno inicial
print()
print("Donde falla pos1 (segunda inicial = interna del paterno segun layout viejo):")
n = 0
for rfc, nom, gen, ed, curp, res, u6ed in rows:
    real = curp.strip().upper()
    calc, _ = calcular_curp(nom, rfc, ed or u6ed, genero_col=gen)
    if calc and len(calc) == 18 and calc[1] != real[1] and n < 8:
        partes = _particulas(nom).split()
        print("   %-40s real=%s calc=%s  rfc=%s" % (nom[:40], real[:4], calc[:4], rfc[:4]))
        n += 1