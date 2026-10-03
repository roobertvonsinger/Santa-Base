"""Auditoria anti-regresion del lexico de sexo tras ampliarlo.

Tres verificaciones, todas sobre DATOS:
  1. Ningun nombre aparece a la vez en _FEM y _MASC.
  2. Contra las 714 filas con `genero` conocido: acierto antes vs ahora.
  3. Cobertura: cuanto del pool sigue sin nombre reconocible.
"""
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import curp_calc as cc  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')

# 1. solapamientos
ambos = cc._FEM & cc._MASC
print("1) Nombres en _FEM y _MASC a la vez: %d" % len(ambos))
for n in sorted(ambos):
    print("     %s" % n)

# 2. acierto contra la verdad
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT dmname, genero FROM santander_records
             WHERE genero IS NOT NULL AND TRIM(genero)!=''
               AND dmname IS NOT NULL AND TRIM(dmname)!=''
               AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'""")
verd = c.fetchall()

aciertos = 0
evaluadas = 0
errs = []
for nom, g in verd:
    real = g.strip().upper()[:1]
    if real not in ("H", "M"):
        continue
    sexo, conf = cc.inferir_sexo(nom, None)
    if sexo is None:
        continue          # descartada, no cuenta como error
    evaluadas += 1
    if sexo == real:
        aciertos += 1
    else:
        errs.append((nom, real, sexo))

print()
print("2) Contra las filas con `genero` conocido:")
print("   evaluadas (con nombre reconocido): %d" % evaluadas)
print("   aciertos: %d = %.2f%%" % (aciertos, 100.0 * aciertos / max(1, evaluadas)))
print("   errores: %d" % len(errs))
vistos = set()
for nom, real, mio in errs:
    p = tuple(cc._partes(nom)[:-2])
    if p in vistos:
        continue
    vistos.add(p)
    print("      %-40s real=%s yo=%s" % (nom[:40], real, mio))
    if len(vistos) >= 25:
        break

# 3. cobertura del pool
c.execute("""SELECT u6rfc, dmname, u6estado FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND dmname IS NOT NULL AND TRIM(dmname)!=''
               AND u6estado IS NOT NULL AND TRIM(u6estado)!=''
             LIMIT 200000""")
pool = c.fetchall()
stats = Counter()
for rfc, nom, est in pool:
    calc, det = cc.calcular_curp(nom, rfc, est)
    stats["ok" if calc else str(det).split(":")[0]] += 1

print()
print("3) Sobre %d filas del pool de 4.86M:" % len(pool))
print("   CALCULABLES : %d  (%.2f%%)" % (stats['ok'], 100.0 * stats['ok'] / max(1, len(pool))))
for k, v in stats.most_common():
    if k != 'ok':
        print("   %-30s %7d  (%.2f%%)" % (k, v, 100.0 * v / max(1, len(pool))))
conn.close()