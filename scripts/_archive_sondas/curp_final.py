"""Mide el calculador con la regla de pos1 = interna del MATERNO.
Compara las tres fuentes de iniciales sobre las 332 aceptadas:
  A) rfc[0:4]              98.19%
  B) calculadas del nombre
  C) calculadas, con respaldo del nombre cuando el RFC contradice al nombre
"""
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import calcular_curp, _partes, cons_interna, _dado_principal  # noqa: E402

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT u6rfc, dmname, genero, estado, curp, results, u6estado
             FROM santander_records WHERE curp IS NOT NULL
             AND LENGTH(TRIM(curp))=18""")
rows = c.fetchall()
conn.close()

ACEPT = [x for x in rows
         if 'RENAPO' not in (x[5] or '').upper() and 'OPERADOR' not in (x[5] or '').upper()]


def ini_nombre(nom):
    p = _partes(nom)
    if len(p) < 2:
        return None
    paterno, materno = p[-2], p[-1]
    d = _dado_principal(nom)
    if not d:
        return None
    return paterno[0] + cons_interna(materno) + materno[0] + d[0]


n = len(ACEPT)
a = b = 0
fallos_a = []
for rfc, nom, gen, ed, curp, res, u6ed in ACEPT:
    real = curp.strip().upper()
    if rfc[:4] == real[:4]:
        a += 1
    else:
        fallos_a.append((nom, rfc[:4], ini_nombre(nom), real[:4]))
    if ini_nombre(nom) == real[:4]:
        b += 1

print("INICIALES sobre %d aceptadas por RENAPO" % n)
print("   A) rfc[0:4] tal cual        : %d/%d  (%.2f%%)" % (a, n, 100.0 * a / n))
print("   B) calculadas del nombre   : %d/%d  (%.2f%%)" % (b, n, 100.0 * b / n))
print()
print("Los 6 donde el RFC falla:")
for f in fallos_a:
    print("   %-40s rfc=%s  nombre_calc=%s  real=%s" % (f[0][:40], f[1], f[2], f[3]))
print()

# regla hibrida: si el nombre calcula una inicial de paterno/2do nombre que
# contradice al RFC, revisar. Requiere que pos0 y pos2 coincidan (paterno y
# materno identicos) -> entonces pos1/pos3 son de confianza del nombre.
hib = 0
ej = []
for rfc, nom, gen, ed, curp, res, u6ed in ACEPT:
    real = curp.strip().upper()
    b4 = ini_nombre(nom)
    if b4 is None:
        continue
    if rfc[:4] == real[:4]:
        hib += 1
        continue
    if rfc[0] == b4[0] and rfc[2] == b4[2] and b4 == real[:4]:
        hib += 1
        ej.append((nom, rfc[:4], b4, real[:4]))
    else:
        pass
print("   C) hibrida (RFC, con nombre cuando pos0/pos2 coinciden): %d/%d (%.2f%%)"
      % (hib, n, 100.0 * hib / n))
for e in ej:
    print("      rescue: %-36s rfc=%s nombre=%s real=%s" % (e[0][:36], e[1], e[2], e[3]))
print()

# Con la regla hibrida, CURP completa
print("CURP COMPLETA con la hibrida:")
full = pre17 = 0
fallos = []
for rfc, nom, gen, ed, curp, res, u6ed in ACEPT:
    real = curp.strip().upper()
    b4 = ini_nombre(nom)
    ini = rfc[:4]
    if b4 and rfc[0] == b4[0] and rfc[2] == b4[2]:
        ini = b4
    p = _partes(nom)
    if len(p) < 2:
        continue
    cod = real[11:13]
    sexo = real[10]
    calc17 = (ini + rfc[4:10] + sexo + cod +
              cons_interna(p[-2]) + cons_interna(p[-1]) +
              cons_interna(_dado_principal(nom)) + real[16])
    from curp_calc import digito_verificador
    calc = calc17 + digito_verificador(calc17)
    if calc[:17] == real[:17]:
        pre17 += 1
    if calc == real:
        full += 1
    else:
        fallos.append((nom, real, calc))
print("   primeros 17 : %d/%d  (%.2f%%)" % (pre17, n, 100.0 * pre17 / n))
print("   18/18       : %d/%d  (%.2f%%)" % (full, n, 100.0 * full / n))
print()
print("   fallos que quedan:")
for f in fallos:
    d = [i for i in range(18) if f[1][i] != f[2][i]]
    print("      %-38s real=%s calc=%s dif=%s" % (f[0][:38], f[1], f[2], d))