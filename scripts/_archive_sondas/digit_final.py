"""PRUEBA DE DETERMINISMO.

Si pos17 fuera una funcion determinista de los primeros 16 chars, dos CURPs con
los mismos 16 chars tendrían que llevar el MISMO digito. Se buscan duplicados
en los 16 primeros caracteres, entre todas las 717 y dentro de cada grupo.

Ademas prueba la variante oficial que faltaba: el multiplicador se aplica y si
el producto pasa de 9 se RESTA 10 (no se suman sus digitos). Es distinta de las
dos que ya medi.
"""
import os
import sqlite3
import sys
from collections import defaultdict

TABLA = "0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ"
VAL = {c: i for i, c in enumerate(TABLA)}

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT curp, results FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18""")
ALL = [(r[0].strip().upper(), (r[1] or '')) for r in c.fetchall()]
conn.close()


def grupo(res):
    r = res.upper()
    if 'RENAPO' in r:
        return 'RECHAZADA'
    if 'OPERADOR' in r:
        return 'NUNCA_ENVIADA'
    return 'ACEPTADA'


print("=" * 72)
print("1) DETERMINISMO: mismos 16 chars -> mismo pos17?")
print("=" * 72)
pre = defaultdict(set)
for curp, res in ALL:
    pre[curp[:16]].add(curp[17])
dups = {k: v for k, v in pre.items() if len(v) > 1}
print("   prefijos de 16 chars distintos : %d" % len(pre))
print("   prefijos con MAS DE UN digito  : %d" % len(dups))
for k, v in list(dups.items())[:10]:
    print("      %s -> digitos %s" % (k, sorted(v)))

# mismo prefijo dentro de las aceptadas
G = defaultdict(set)
for curp, res in ALL:
    if grupo(res) == 'ACEPTADA':
        G[curp[:16]].add(curp[17])
dupA = {k: v for k, v in G.items() if len(v) > 1}
print("   dentro de las ACEPTADAS: %d prefijos con >1 digito (de %d prefijos)"
      % (len(dupA), len(G)))
for k, v in list(dupA.items())[:5]:
    print("      %s -> %s" % (k, sorted(v)))
print()
if not dups:
    print("   LECTURA: no hay ningun prefijo repetido -> no se puede probar el")
    print("   determinismo con estos datos (el pool 4.86M tiene homonimos, aqui no).")
else:
    print("   LECTURA: pos17 NO es funcion de los 16 chars -> no se puede calcular.")

print()
print("=" * 72)
print("2) Variante oficial que faltaba: producto - 10 si > 9")
print("=" * 72)
REAL = [cu for cu, r in ALL if grupo(r) == 'ACEPTADA']


def v_menos10(pre16):
    s = 0
    for i, ch in enumerate(pre16):
        p = VAL.get(ch, 0) * (2 if i % 2 == 0 else 1)
        s += p - 10 if p > 9 else p
    return s % 10


def v_menos10_x1_2(pre16):
    s = 0
    for i, ch in enumerate(pre16):
        p = VAL.get(ch, 0) * (1 if i % 2 == 0 else 2)
        s += p - 10 if p > 9 else p
    return s % 10


def v_menos10_c1(pre16):
    return sum((VAL.get(ch, 0) - 10 if VAL.get(ch, 0) > 9 else VAL.get(ch, 0))
               for ch in pre16) % 10


def v_menos10_c2(pre16):
    return sum((VAL.get(ch, 0) * 2 - 10 if VAL.get(ch, 0) * 2 > 9 else VAL.get(ch, 0) * 2)
               for ch in pre16) % 10


for nombre, fn in [("x2 en indice par, -10", v_menos10),
                   ("x2 en indice impar, -10", v_menos10_x1_2),
                   ("x1 todos, -10", v_menos10_c1),
                   ("x2 todos, -10", v_menos10_c2)]:
    ok = sum(1 for k in REAL if fn(k[:16]) == int(k[17]))
    print("   %-26s %d/%d  (%.1f%%)" % (nombre, ok, len(REAL), 100.0 * ok / len(REAL)))
print("   %-26s %d/%d  (%.1f%%)" % ("azar", 0, len(REAL), 0.0))

print()
print("=" * 72)
print("3) ¿El prefijo de 17 chars es unico en toda la BD?")
print("=" * 72)
p17 = defaultdict(int)
for curp, res in ALL:
    p17[curp[:17]] += 1
rep = {k: v for k, v in p17.items() if v > 1}
print("   prefijos de 17 distintos: %d | repetidos: %d" % (len(p17), len(rep)))
for k, v in list(rep.items())[:6]:
    print("      %s -> %d veces" % (k, v))