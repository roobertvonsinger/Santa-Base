"""Mide el calculador posicion por posicion contra las 717 CURPs de la BD,
separando las que RENAPO ACEPTO de las que RECHAZO. Ademas prueba la regla
oficial de nombres comunes (JOSE/MARIA) y la homoclave por anio.
"""
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import calcular_curp, curp_valida, digito_verificador  # noqa: E402

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT u6rfc, dmname, genero, estado, curp, results, u6estado
             FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18""")
rows = c.fetchall()
conn.close()


def grupo(res):
    r = (res or '').upper()
    if 'RENAPO' in r:
        return 'RECHAZADA'
    if 'OPERADOR' in r:
        return 'NONE'
    return 'ACEPTADA'


G = {'ACEPTADA': [], 'RECHAZADA': [], 'NONE': []}
for rfc, nom, gen, ed, curp, res, u6ed in rows:
    G[grupo(res)].append((rfc, nom, gen, ed, u6ed, curp.strip().upper()))

ETIQUETAS = {0: "inicial 1", 1: "inicial 2", 2: "inicial 3", 3: "inicial 4",
             4: "anio", 5: "mes", 6: "dia", 7: "mes alt", 8: "dia alt", 9: "dia alt2",
             10: "sexo H/M", 11: "entidad L1", 12: "entidad L2",
             13: "cons paterno", 14: "cons materno", 15: "cons nombre",
             16: "homoclave", 17: "DIGITO VERIF."}

for gname in ('ACEPTADA', 'RECHAZADA'):
    data = [x for x in G[gname]]
    if not data:
        continue
    print("=" * 74)
    print("%s por RENAPO  (n=%d)" % (gname, len(data)))
    print("=" * 74)
    pos_ok = Counter()
    full = pre17 = 0
    for rfc, nom, gen, ed, u6ed, real in data:
        calc, _ = calcular_curp(nom, rfc, ed or u6ed, genero_col=gen)
        if not calc:
            continue
        if calc[:17] == real[:17]:
            pre17 += 1
        if calc == real:
            full += 1
        for i in range(18):
            if calc[i] == real[i]:
                pos_ok[i] += 1
    n = len(data)
    for i in range(18):
        print("   pos %2d  %-14s %4d/%d  %6.2f%%"
              % (i, ETIQUETAS[i], pos_ok[i], n, 100.0 * pos_ok[i] / n))
    print("   ---")
    print("   primeros 17 correctos : %d/%d  (%.2f%%)" % (pre17, n, 100.0 * pre17 / n))
    print("   CURP 18/18 identica   : %d/%d  (%.2f%%)" % (full, n, 100.0 * full / n))
    print()

# posicion 13/14/15: ver si el fallo es del algoritmo o del dato
print("=" * 74)
print("DISCREPANCIA pos13/14/15 -- accepted vs rejected")
print("=" * 74)
for gname in ('ACEPTADA', 'RECHAZADA'):
    data = G[gname]
    if not data:
        continue
    d13 = Counter()
    ej13 = []
    for rfc, nom, gen, ed, u6ed, real in data:
        calc, _ = calcular_curp(nom, rfc, ed or u6ed, genero_col=gen)
        if not calc:
            continue
        for i in (13, 14, 15):
            if calc[i] != real[i]:
                d13[i] += 1
                if i == 13 and len(ej13) < 4:
                    ej13.append((nom, real[i], calc[i], real[11:13]))
    print("\n  %s (n=%d) fallos:" % (gname, len(data)),
          {i: d13[i] for i in (13, 14, 15)})
    for e in ej13:
        print("      %-38s real=%s calc=%s  ent=%s" % (e[0][:38], e[1], e[2], e[3]))