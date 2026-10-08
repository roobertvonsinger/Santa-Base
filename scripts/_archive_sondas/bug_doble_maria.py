"""DOS BUGS que el smoke test del purger destapo:

BUG 1: COMUNES incluye 'MARIA'. _dado_principal('MARIA DE LOS ANGELES PACHECO
SANDOVAL') devuelve ANGELES porque MARIA esta en COMUNES, y la inicial p3 sale
'A'. Pero si el RFC ya trae la inicial correcta, esto no importa... salvo que
COMUNES tambien Rovina a los nombres compuestos, cambiando la CONSONANTE
INTERNA de p15. Medir cuanto del pool se ve afectado.

BUG 2: CURPs con 'X' en p0-p3 por nombres sin consonante, y CURPs cuya p3 no
coincide con lo que dice el nombre (el RFC manda, ya se midio 96.50%). Checar
que ninguna de las dos cosas produzca CURPs estructuralmente invalidas.

Ademas: nombres como 'JOSE MIGUEL DIAZ INFANTE AGUILAR' tienen 5 palabras;
paterno y materno se toman como las dos ULTIMAS, que es la convencion, pero
'INFANTE' como materno es raro. Medir cuantos nombres tienen >4 palabras.
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
c.execute("""SELECT u6rfc, dmname, u6estado, curp FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND dmname IS NOT NULL AND TRIM(dmname)!=''
             LIMIT 300000""")
pool = c.fetchall()
conn.close()

# --- BUG 1: efecto de COMUNES sobre p15 ------------------------------
con_dado = Counter()
nombres_largos = Counter()
x_curps = 0
mismatch_p3 = 0
n = 0
for rfc, nom, est, curp in pool:
    calc, det = cc.calcular_curp(nom, rfc, est)
    if not calc:
        continue
    n += 1
    p = cc._partes(nom)
    nombres_largos[len(p)] += 1
    if "X" in calc:
        x_curps += 1
    # p3 del RFC vs primer nombre dado (o el 2do si el 1ro es comun)
    partes = p[:-2] if len(p) > 2 else p
    if partes:
        esperado = partes[0][0] if calc[3] == partes[0][0] else None
        if esperado is None:
            mismatch_p3 += 1

print("Muestra de %d CURPs calculadas" % n)
print()
print("Distribucion de palabras por nombre:")
for k, v in sorted(nombres_largos.items()):
    print("   %2d palabras: %8d  (%.1f%%)" % (k, v, 100.0 * v / max(1, n)))
print()
print("Nombres con >4 palabras: %d (%.2f%%)"
      % (sum(v for k, v in nombres_largos.items() if k > 4),
         100.0 * sum(v for k, v in nombres_largos.items() if k > 4) / max(1, n)))
print()
print("CURPs con 'X' en alguna posicion (consonante interna no encontrada): %d (%.2f%%)"
      % (x_curps, 100.0 * x_curps / max(1, n)))
print()
print("Nombres con MARIA/JOSE al inicio (afectados por COMUNES):")
con_dado = Counter()
for rfc, nom, est, curp in pool:
    calc, det = cc.calcular_curp(nom, rfc, est)
    if not calc:
        continue
    p = cc._partes(nom)
    dados = p[:-2] if len(p) > 2 else p
    if dados and dados[0] in cc.COMUNES:
        con_dado[dados[0]] += 1
for k, v in con_dado.most_common():
    print("   %-8s %8d  (%.2f%% del pool)" % (k, v, 100.0 * v / max(1, n)))
print("   TOTAL con nombre comun: %d (%.2f%%)"
      % (sum(con_dado.values()), 100.0 * sum(con_dado.values()) / max(1, n)))