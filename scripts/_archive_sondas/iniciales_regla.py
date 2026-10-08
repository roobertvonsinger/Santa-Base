"""Regla de las 4 iniciales. El RFC de la BD acierta 98.5% pero tiene errores
(EAJO vs EAPJ, HEFJ vs HUFJ). Compara tres fuentes:
   A) rfc[0:4] tal cual
   B) calculadas del nombre con la regla oficial
   C) RFC corregido por nombre solo cuando el nombre da una inicial valida
      que difiere (para no romper los casos donde el RFC es correcto)
Y sobre todo imprime el desglose de cuando difieren, para ver la regla.
"""
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import _particulas, cons_interna, COMUNES  # noqa: E402

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT u6rfc, dmname, curp, results FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18""")
rows = c.fetchall()
conn.close()


def aceptada(res):
    r = (res or '').upper()
    return 'RENAPO' not in r and 'OPERADOR' not in r


def partes(nombre):
    return [p for p in _particulas(nombre).split() if p]


def ini_rfc(rfc):
    return rfc[:4]


def ini_nombre(nombre):
    """Regla oficial: paterno[0], cons_interna(paterno), materno[0], 1er dado[0].
    Si hay dos dados y el 1ro es composicional (MARIA/JOSE), pos3 = 2do."""
    p = partes(nombre)
    if len(p) < 2:
        return None
    paterno, materno = p[-2], p[-1]
    dados = p[:-2] if len(p) > 2 else p
    if not dados:
        return None
    c1 = paterno[0]
    c2 = cons_interna(paterno)
    c3 = materno[0]
    c4 = dados[0][0]
    return c1 + c2 + c3 + c4


ACEPT = [x for x in rows if aceptada(x[3])]
print("Muestra: %d CURPs aceptadas por RENAPO\n" % len(ACEPT))

a_ok = sum(1 for rfc, nom, curp, _ in ACEPT if ini_rfc(rfc) == curp.strip().upper()[:4])
b_ok = sum(1 for rfc, nom, curp, _ in ACEPT
           if ini_nombre(nom) == curp.strip().upper()[:4])
n = len(ACEPT)
print("   A) rfc[0:4] tal cual      : %d/%d  (%.2f%%)" % (a_ok, n, 100.0 * a_ok / n))
print("   B) calculadas del nombre  : %d/%d  (%.2f%%)" % (b_ok, n, 100.0 * b_ok / n))
print()

print("Casos donde A falla (rfc mal) -- que dice el nombre:")
n = 0
for rfc, nom, curp, res in ACEPT:
    real = curp.strip().upper()
    if ini_rfc(rfc) != real[:4] and n < 12:
        print("   %-38s rfc=%s  nombre=%s  real=%s" % (nom[:38], rfc[:4], ini_nombre(nom), real[:4]))
        n += 1
print()

print("Casos donde A acierta y B falla (nombre no sirve):")
n = 0
for rfc, nom, curp, res in ACEPT:
    real = curp.strip().upper()
    if ini_rfc(rfc) == real[:4] and ini_nombre(nom) != real[:4] and n < 12:
        print("   %-38s rfc=%s  nombre=%s  real=%s" % (nom[:38], rfc[:4], ini_nombre(nom), real[:4]))
        n += 1
print()

# pos1: interna del paterno o inicial del materno?
d = Counter()
for rfc, nom, curp, res in ACEPT:
    real = curp.strip().upper()
    p = partes(nom)
    if len(p) < 3:
        continue
    c_int = cons_interna(p[-2])
    d['pos1=interna_paterno' if real[1] == c_int else 'pos1=interna_materno'] += 1
print("pos1 (2da inicial) segun la regla:", dict(d))
d2 = Counter()
for rfc, nom, curp, res in ACEPT:
    real = curp.strip().upper()
    p = partes(nom)
    if len(p) < 3:
        continue
    dados = p[:-2]
    if len(dados) > 1:
        d2['pos3=%s(1ro)' % real[3] if real[3] == dados[0][0] else 'pos3=%s(2do)' % dados[1][0]] += 1
    else:
        d2['un solo dado'] += 1
print("pos3 cuando hay 2 nombres dados:", dict(d2))
print()

# regla hibrida: RFC primero, nombre cuando el RFC no cuadra con el patron
def ini_hibrida(rfc, nombre):
    a = ini_rfc(rfc)
    b = ini_nombre(nombre)
    if b and a[0] == b[0] and a[2] == b[2] and a[3] == b[3]:
        return b   # solo pos1 discrepa -> usa la del nombre
    return a


h_ok = sum(1 for rfc, nom, curp, _ in ACEPT if ini_hibrida(rfc, nom) == curp.strip().upper()[:4])
print("   C) hibrida (nombre solo si 3 de 4 coinciden): %d/%d  (%.2f%%)"
      % (h_ok, n, 100.0 * h_ok / n))