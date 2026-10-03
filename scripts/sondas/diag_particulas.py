"""Dos cosas que hay que separar antes de seguir:

1) La REFERENCIA HONESTA. `curp_medir_final.py` ahora compara 986,612 CURPs
   de las cuales 985,899 las escribio mi propio sync: eso es medir contra su
   propia salida y no vale. Las originales son las que NO synchronizo este
   turno; se isolan y se vuelve a medir solo contra esas.

2) Los NOMBRES CON PARTICULAS. `_partes()` borra DE/DEL/LA, y hay apellidos
   compuestos reales (`GARCIA DE ALBA`, `DE LA ROSA`). Con "ultimos 2 =
   paterno+materno" esos nombres parten mal y el RFC lo delata: los 4
   primeros caracteres del RFC son la verdad. Se mide cuantos hay y si el
   RFC confirma que el corte esta mal.
"""
import os
import re
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import curp_calc as cc  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

# --- 1) referencia honesta: filas con curp Y con genero conocido ------------
c.execute("""SELECT u6rfc, dmname, u6estado, curp, genero, results FROM santander_records
             WHERE curp IS NOT NULL AND TRIM(curp)!=''
               AND genero IS NOT NULL AND TRIM(genero)!=''
               AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'
               AND LENGTH(TRIM(u6rfc))=13""")
honesta = c.fetchall()
print("Referencias con curp + genero + RFC limpio: %d" % len(honesta))
print()

full = 0
evaluadas = 0
pos = Counter()
errs = []
for rfc, nom, est, curp_real, gen, res in honesta:
    real = curp_real.strip().upper()
    calc, det = cc.calcular_curp(nom, rfc, est, genero_col=gen)
    if calc is None:
        continue
    evaluadas += 1
    if calc == real:
        full += 1
    else:
        pos["p0-3 iniciales" if calc[:4] != real[:4] else "p10 sexo"] += 1
        if len(errs) < 10:
            errs.append((nom, real, calc))
print("SOLO contra esas: CURP completa %d/%d = %.2f%%" % (full, evaluadas, 100.0 * full / max(1, evaluadas)))
print("  desglose de fallos: %s" % dict(pos))
for nom, real, calc in errs:
    print("     %-40s real=%s  yo=%s" % (nom[:40], real, calc))
print()

# --- 2) particulas en el pool ----------------------------------------------
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND dmname IS NOT NULL
               AND (dmname LIKE '% DE %' OR dmname LIKE '% DEL %'
                    OR dmname LIKE '% DE LA %' OR dmname LIKE '% Y %')""")
tot_p = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM santander_records WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13")
tot = c.fetchone()[0]
print("Filas del pool con ' DE ' / ' DEL ' / ' DE LA ' / ' Y ': %d de %d = %.2f%%"
      % (tot_p, tot, 100.0 * tot_p / max(1, tot)))
print()

# de esas, cuantas confirmadas por el RFC tienen el corte mal
c.execute("""SELECT u6rfc, dmname, u6estado, curp FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND dmname IS NOT NULL
               AND (dmname LIKE '% DE %' OR dmname LIKE '% DEL %'
                    OR dmname LIKE '% DE LA %' OR dmname LIKE '% Y %')
               AND curp IS NOT NULL AND TRIM(curp)!=''
               AND genero IS NOT NULL AND TRIM(genero)!=''
               AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'""")
mal = 0
ok_ = 0
ej = []
for rfc, nom, est, curp_real in c.fetchall():
    calc, _ = cc.calcular_curp(nom, rfc, est, genero_col=None)
    if calc is None:
        continue
    if calc[:4] == curp_real.strip().upper()[:4]:
        ok_ += 1
    else:
        mal += 1
        if len(ej) < 12:
            ej.append((nom, curp_real.strip().upper()[:4], calc[:4]))
print("De las verificadas por RFC, corte de apellidos:")
print("   correcto: %d    MAL: %d" % (ok_, mal))
for nom, r, m in ej:
    print("     %-42s rfc=%s  yo=%s" % (nom[:42], r, m))

# --- 3) cuantas particulas sobreviven a _partes ----------------------------
print()
c.execute("""SELECT dmname FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND dmname IS NOT NULL
               AND (dmname LIKE '% DE %' OR dmname LIKE '% DEL %'
                    OR dmname LIKE '% DE LA %' OR dmname LIKE '% Y %')
             LIMIT 4000""")
n_tok = Counter()
for (nom,) in c.fetchall():
    p = cc._partes(nom)
    dados = p[:-2] if len(p) > 2 else p
    for d in dados:
        n_tok[d] += 1
print("Nombres que quedan como 'dados' tras _partes (top 15):")
for k, v in n_tok.most_common(15):
    print("   %-18s %d" % (k, v))
conn.close()