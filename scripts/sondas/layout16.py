"""pos16: ¿diferenciador de homonimos o consonante del 2do nombre?

Las 717 traen pos16='0' SIEMPRE, con nombres de hasta 2 dados
("MAYRA JOCELYN CERVANTES HERNANDEZ" -> pos16='0', pero el 2do dado JOCELYN
daria consonante interna 'C'). Eso descarta "consonante del 2do nombre".
Queda la regla oficial: pos16 = 0 si no hay homonimos, letra A-Z si los hay.

Ademas reconstruye el nombre detras de cada una de las 717 para verificar
pos13/14/15 palabra por palabra, y busca el registro del CURP real aceptado."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc_test import _particulas, _consonante_interna_palabra, VOCALES  # noqa

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()

print("=" * 78)
print("A) ¿Existe el CURP real ZAPM740918HJCRRR08 en la base?")
print("=" * 78)
for tab in ("santander_records", "santander_hits"):
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tab,))
        if not c.fetchone():
            print("   tabla %s: no existe" % tab)
            continue
        c.execute("PRAGMA table_info(%s)" % tab)
        cols = [r[1] for r in c.fetchall()]
        where = " OR ".join("%s LIKE ?" % col for col in cols if col)
        c.execute("SELECT * FROM %s WHERE %s LIMIT 3" % (tab, where), tuple(["%ZAPM740918%"] * len([x for x in cols if x])))
        rs = c.fetchall()
        print("   tabla %s: %d filas con ZAPM740918" % (tab, len(rs)))
        for r in rs:
            print("      %s" % dict(zip(cols, r)))
    except Exception as e:
        print("   tabla %s -> %s" % (tab, e))

print()
print("=" * 78)
print("B) pos16 == '0' siempre? y nombres de 1 vs 2 dados")
print("=" * 78)
c.execute("""SELECT curp, dmname FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp)) = 18""")
rows = [(r[0].strip().upper(), (r[1] or "").strip()) for r in c.fetchall()]

from collections import Counter
print("   pos16: %s" % Counter(r[16] for r, _ in rows).most_common(8))

n1 = n2 = 0
cons2_correct = cons2_wrong = 0
mismatch13 = mismatch14 = mismatch15 = 0
detalles = []
for curp, nom in rows:
    w = _particulas(nom).split()
    if len(w) < 3:
        continue
    paterno, materno = w[-2], w[-1]
    dados = w[:-2]
    if len(dados) == 1:
        n1 += 1
        esperado16 = "0"
    else:
        n2 += 1
        esperado16 = _consonante_interna_palabra(dados[1]) if len(dados) > 1 else "0"
    if esperado16 == curp[16]:
        cons2_correct += 1
    else:
        cons2_wrong += 1
        if cons2_wrong <= 6:
            detalles.append((nom, curp, "esperado16=%s real16=%s" % (esperado16, curp[16])))

print("   nombres con 1 dado : %d   con 2+ dados: %d" % (n1, n2))
print("   pos16 == cons.2do nombre dado : %d ok / %d mal" % (cons2_correct, cons2_wrong))
for d in detalles:
    print("      %-40s %s  %s" % (d[0][:40], d[1], d[2]))
print()
print("   LECTURA: si hay nombres de 2 dados y pos16 sigue siendo '0', entonces")
print("   pos16 NO es la consonante del 2do nombre -> es el diferenciador de")
print("   homonimos, y '0' es el valor correcto cuando no hay homonimos.")

print()
print("=" * 78)
print("C) pos13/14/15 palabra por palabra (que palabra es cual)")
print("=" * 78)
c.execute("""SELECT curp, dmname FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp)) = 18 AND dmname IS NOT NULL
             LIMIT 800""")
rows2 = [(r[0].strip().upper(), (r[1] or "").strip()) for r in c.fetchall()]
import unicodedata

for etiqueta, idx_pat, idx_mat, pos in [("pat", -2, -1, 13), ("mat", -1, -1, 14)]:
    pass

exp13 = exp14 = exp15 = 0
tot = 0
mal15 = []
for curp, nom in rows2:
    w = _particulas(nom).split()
    if len(w) < 3:
        continue
    tot += 1
    paterno, materno = w[-2], w[-1]
    dados = w[:-2]
    if _consonante_interna_palabra(paterno) == curp[13]:
        exp13 += 1
    if _consonante_interna_palabra(materno) == curp[14]:
        exp14 += 1
    if dados and _consonante_interna_palabra(dados[0]) == curp[15]:
        exp15 += 1
    elif len(mal15) < 8:
        mal15.append((nom, curp, dados[0] if dados else "-", curp[15]))
print("   total con >=3 palabras: %d" % tot)
print("   pos13 == cons(paterno, penultima) : %d  (%.1f%%)" % (exp13, 100.0 * exp13 / max(1, tot)))
print("   pos14 == cons(materno, ULTIMA)   : %d  (%.1f%%)" % (exp14, 100.0 * exp14 / max(1, tot)))
print("   pos15 == cons(1er dado)           : %d  (%.1f%%)" % (exp15, 100.0 * exp15 / max(1, tot)))
print()
print("   Fallos de pos15:")
for m in mal15:
    print("      %-40s %s  dado=%-12s esperado=%s" % (m[0][:40], m[1], m[2][:12], m[3]))
conn.close()