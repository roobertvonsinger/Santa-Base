"""Las 4 iniciales (p0-p3): mejor el RFC de la BD o derivarlas del nombre?

Medicion A/B sobre las 714 CURPs reales limpias. La DB toma sus iniciales del
RFC (fuente de verdad de la persona); el nombre las recalcula. Se mide cada
posicion por separado y tambien el bloque completo 0-3.
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
c.execute("""SELECT u6rfc, dmname, u6estado, curp, genero
             FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18
               AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'""")
ref = c.fetchall()
conn.close()

A = Counter()   # RFC
B = Counter()   # nombre
D = Counter()   # discrepancia RFC vs nombre
ej = []
n = 0
for rfc, nom, est, curp_real, gen in ref:
    real = curp_real.strip().upper()
    calc, det = cc.calcular_curp(nom, rfc, est, genero_col=gen)
    if calc is None:
        continue
    n += 1
    por_rfc = calc[0:4]
    por_nom = cc._iniciales_calculadas(nom)
    if not por_nom:
        continue
    if por_rfc == real[0:4]:
        A['ok'] += 1
    else:
        A['dif'] += 1
    if por_nom == real[0:4]:
        B['ok'] += 1
    else:
        B['dif'] += 1
    if por_rfc != por_nom:
        D['discrepan'] += 1
        if len(ej) < 25:
            ej.append((nom, real[0:4], por_rfc, por_nom))

print("Iniciales p0-p3 sobre %d CURPs reales" % n)
print("=" * 74)
print("  A) tomar del RFC de la BD  : %3d ok  %3d mal  -> %.2f%%"
      % (A['ok'], A['dif'], 100.0*A['ok']/max(1,A['ok']+A['dif'])))
print("  B) recalcular del nombre   : %3d ok  %3d mal  -> %.2f%%"
      % (B['ok'], B['dif'], 100.0*B['ok']/max(1,B['ok']+B['dif'])))
print("  C) RFC y nombre discrepan  : %d" % D['discrepan'])
print()
print("  En las que discrepan, quien le atina mas?")
a_gana = b_gana = nadie = 0
for nom, real, pr, pn in ej:
    if pr == real:
        a_gana += 1
    elif pn == real:
        b_gana += 1
    else:
        nadie += 1
print("     RFC atina: %d   nombre atina: %d   ninguno: %d" % (a_gana, b_gana, nadie))
print()
print("  Muestra (solo discrepantes):")
print("     %-36s %-6s %-6s %-6s" % ("NOMBRE", "REAL", "RFC", "NOMBRE"))
for nom, real, pr, pn in ej[:25]:
    print("     %-36s %-6s %-6s %-6s" % (nom[:36], real, pr, pn))

# Hybrid: si el RFC no cuadra con el nombre, recalcular
print()
print("  D) HYBRID: usar el RFC salvo que sus letras no existan en el nombre,")
print("     en cuyo caso recalcular del nombre")
H = 0
for rfc, nom, est, curp_real, gen in ref:
    real = curp_real.strip().upper()
    calc, det = cc.calcular_curp(nom, rfc, est, genero_col=gen)
    if calc is None:
        continue
    ini = calc[0:4]
    p = cc._partes(nom)
    letras = set(w[0] for w in p)
    if not (set(ini) - letras):
        continue          # el RFC es coherente con el nombre
    por_nom = cc._iniciales_calculadas(nom)
    if por_nom and por_nom == real[0:4]:
        H += 1
print("     el RFC no cuadra con el nombre en %d filas; de esas, el nombre"
      % (D['discrepan']))
print("     reconstruye la inicial correcta en %d" % H)