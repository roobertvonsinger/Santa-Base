"""Aclaracion: `calcular_curp` SI usa rfc[0:4] (linea verificada). Entonces
los 25 fallos de "p0-3" no son de iniciales sino de las consonantes internas
p13-p15, que se contaron dentro del rango 0..4.

Aqui se separa posicion por posicion con la verdad, sobre las 714 honestas,
para saber exactamente que character del RFC esta mal cuando el A falla.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import curp_calc as cc  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT u6rfc, dmname, u6estado, curp, genero FROM santander_records
             WHERE curp IS NOT NULL AND TRIM(curp)!=''
               AND genero IS NOT NULL AND TRIM(genero)!=''
               AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'
               AND LENGTH(TRIM(u6rfc))=13""")
ref = c.fetchall()
conn.close()

# posicion: (etiqueta, ini, fin)
POS = [("p0 pat", 0, 1), ("p1 int.pat", 1, 2), ("p2 mat", 2, 3), ("p3 nom", 3, 4),
       ("p13 int.pat", 13, 14), ("p14 int.mat", 14, 15), ("p15 int.nom", 15, 16)]

ok = {e: 0 for e, _, _ in POS}
n = 0
malos = []
for rfc, nom, est, curp_real, gen in ref:
    real = curp_real.strip().upper()
    calc, _ = cc.calcular_curp(nom, rfc, est, genero_col=gen)
    if calc is None:
        continue
    n += 1
    for e, a, b in POS:
        if calc[a:b] == real[a:b]:
            ok[e] += 1
        elif e == "p13 int.pat" and len(malos) < 14:
            malos.append((nom, rfc, real, calc))

print("Referencias evaluadas: %d" % n)
print()
for e, a, b in POS:
    print("  %-14s %4d/%d = %.2f%%" % (e, ok[e], n, 100.0 * ok[e] / n))
print()
print("Filas donde falla p13 (con rfc / real / mio completos):")
print("  %-38s %-15s %-18s %-18s" % ("nombre", "rfc", "REAL", "YO"))
for nom, rfc, real, calc in malos:
    p = cc._partes(nom)
    print("  %-38s %-15s %-18s %-18s  pat=%s mat=%s" % (nom[:38], rfc, real, calc, p[-2:], p[-1:]))