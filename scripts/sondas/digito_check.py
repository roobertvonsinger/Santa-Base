"""Verificacion manual, paso a paso, del digito verificador.

digit_diag.py uso una tabla rota (P daba -1) y por eso concluyo mal. La tabla
oficial tiene Ñ DESPUES de M: 0-9 = 0..9, A..M = 10..22, Ñ = 24, Q = 25 ... Z = 34.

Compara, sobre los 331 CURPs que RENAPO ACEPTO, la suma cruda mod 10 contra la
suma de digitos de cada producto mod 10, y muestra el desglose de dos casos.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sqlite3  # noqa: E402

TABLA = "0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ"
VAL = {c: i for i, c in enumerate(TABLA)}
print("TABLA oficial: len=%d  Z=%d  P=%d  M=%d  N=%d  Ñ=%d  Q=%d"
      % (len(TABLA), VAL['Z'], VAL['P'], VAL['M'], VAL['N'], VAL['Ñ'], VAL['Q']))
print()

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT curp FROM santander_records WHERE curp IS NOT NULL
             AND LENGTH(TRIM(curp))=18
             AND results NOT LIKE '%RENAPO%' AND results NOT LIKE '%operador%'""")
REAL = [r[0].strip().upper() for r in c.fetchall()]
conn.close()
print("CURPs aceptadas por RENAPO: %d\n" % len(REAL))


def digito_crudo(pre):
    return sum(VAL.get(ch, 0) * (2 if i % 2 == 0 else 1)
               for i, ch in enumerate(pre)) % 10


def digito_reducido(pre):
    s = 0
    for i, ch in enumerate(pre):
        v = VAL.get(ch, 0) * (2 if i % 2 == 0 else 1)
        s += v // 10 + v % 10
    return s % 10


ok_crudo = sum(1 for k in REAL if digito_crudo(k[:16]) == int(k[17]))
ok_red = sum(1 for k in REAL if digito_reducido(k[:16]) == int(k[17]))
print("suma cruda   mod 10 : %d/%d  (%.1f%%)" % (ok_crudo, len(REAL), 100.0 * ok_crudo / len(REAL)))
print("suma digitos mod 10 : %d/%d  (%.1f%%)" % (ok_red, len(REAL), 100.0 * ok_red / len(REAL)))
print("azar                 : %.1f%%" % (100.0 / len(REAL)))
print()

# confusion: donde acierta la cruda vs la reducida
both = sum(1 for k in REAL if digito_crudo(k[:16]) == int(k[17]) and digito_reducido(k[:16]) == int(k[17]))
only_c = sum(1 for k in REAL if digito_crudo(k[:16]) == int(k[17]) and digito_reducido(k[:16]) != int(k[17]))
only_r = sum(1 for k in REAL if digito_crudo(k[:16]) != int(k[17]) and digito_reducido(k[:16]) == int(k[17]))
print("   ambas aciertan: %d | solo cruda: %d | solo reducida: %d" % (both, only_c, only_r))
print()

print("Desglose de dos CURPs aceptadas:")
for curp in REAL[:2]:
    print("   %s   pos17 real=%d" % (curp, int(curp[17])))
    tot = 0
    tot_r = 0
    for i, ch in enumerate(curp[:16]):
        v = VAL.get(ch, 0)
        w = 2 if i % 2 == 0 else 1
        p = v * w
        tot += p
        tot_r += p // 10 + p % 10
        print("      %2d %s = %2d x %d = %3d" % (i, ch, v, w, p))
    print("      suma cruda=%d -> %d | suma digitos=%d -> %d"
          % (tot, tot % 10, tot_r, tot_r % 10))
    print()

print("Distribucion de pos17 en las aceptadas (deberia ser ~uniforme 10%%):")
dist = Counter(k[17] for k in REAL)
for d in "0123456789":
    n = dist.get(d, 0)
    print("   '%s' %4d  %5.1f%%  %s" % (d, n, 100.0 * n / len(REAL),
                                        "#" * int(40.0 * n / len(REAL))))