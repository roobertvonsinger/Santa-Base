"""MEDICION FINAL del calculador contra las CURPs REALES de la BD.

Compara posicion por posicion la CURP calculada contra la real en las 714 filas
limpias (las 717 menos las 3 con RFC 'XXXX' enmascarado, que no son personas).
Reporta ademas que % del pool de 4.86M sobrevive los filtros.
"""
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import calcular_curp, curp_valida  # noqa: E402

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

ETIQUETAS = ["p0 paterno", "p1 int.pat", "p2 materno", "p3 nombre",
             "p4-9 fecha", "p10 sexo", "p11-12 entidad",
             "p13 int.pat", "p14 int.mat", "p15 int.nom", "p16 homoclave",
             "p17 digito"]
RANGOS = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 10), (10, 11), (11, 13),
          (13, 14), (14, 15), (15, 16), (16, 17), (17, 18)]

ok_pos = Counter()
dif_pos = Counter()
ejemplos = {i: [] for i in range(len(RANGOS))}
full = 0
evaluadas = 0
descartes = Counter()

for rfc, nom, est, curp_real, gen in ref:
    real = curp_real.strip().upper()
    calc, det = calcular_curp(nom, rfc, est, genero_col=gen)
    if calc is None:
        descartes[str(det).split(":")[0]] += 1
        continue
    evaluadas += 1
    igual = True
    for i, (a, b) in enumerate(RANGOS):
        if calc[a:b] == real[a:b]:
            ok_pos[i] += 1
        else:
            dif_pos[i] += 1
            igual = False
            if len(ejemplos[i]) < 4:
                ejemplos[i].append((nom, real[a:b], calc[a:b]))
    if igual:
        full += 1

print("MEDICION FINAL  (referencia: %d CURPs reales, RFC no enmascarado)" % len(ref))
print("=" * 72)
print("  evaluables: %d    descartadas: %d" % (evaluadas, sum(descartes.values())))
for k, v in descartes.most_common():
    print("     %-28s %d" % (k, v))
print()
print("  %-16s %8s %8s %8s" % ("POSICION", "OK", "DIF", "ACIERTO"))
print("  " + "-" * 44)
for i, (a, b) in enumerate(RANGOS):
    n = ok_pos[i] + dif_pos[i]
    pct = 100.0 * ok_pos[i] / max(1, n)
    print("  %-16s %8d %8d %7.2f%%" % (ETIQUETAS[i], ok_pos[i], dif_pos[i], pct))
    for nom, r, m in ejemplos[i][:2]:
        print("        ej: %-34s real=%-10s yo=%s" % (nom[:34], r, m))
print()
print("  CURP COMPLETA (18/18): %d / %d = %.2f%%" % (full, evaluadas, 100.0*full/max(1,evaluadas)))
print()

# --- cobertura del pool ------------------------------------------------
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT u6rfc, dmname, u6estado FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND dmname IS NOT NULL AND TRIM(dmname)!=''
               AND u6estado IS NOT NULL AND TRIM(u6estado)!=''
             LIMIT 200000""")
pool = c.fetchall()
conn.close()

stats = Counter()
for rfc, nom, est in pool:
    calc, det = calcular_curp(nom, rfc, est)
    if calc is None:
        stats[str(det).split(":")[0]] += 1
    else:
        stats["ok"] += 1
        stats["digito_malo"] += 0 if curp_valida(calc) else 1

print("SOBRE %d filas del pool de 4.86M:" % len(pool))
print("  %-30s %10d   %6.2f%%" % ("CALCULABLES", stats['ok'], 100.0*stats['ok']/max(1,len(pool))))
print("  %-30s %10d   %6.2f%%" % ("digito verificador malo", stats['digito_malo'], 100.0*stats['digito_malo']/max(1,len(pool))))
for k, v in stats.most_common():
    if k not in ('ok', 'digito_malo'):
        print("  DESCARTADA %-23s %10d   %6.2f%%" % (k, v, 100.0*v/max(1,len(pool))))