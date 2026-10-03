"""La regla COMUNES (JOSE/MARIA -> el nombre que cuenta es el SIGUIENTE)
afecta al 15.45% del pool. Antes de confiar en ella, medirla.

Se compara, sobre las 714 CURPs reales, la p15 (consonante interna del nombre
dado) que produce cada variante:
  A) COMUNES = {JOSE, MARIA, MA, J}  (lo que hay ahora)
  B) siempre el primer nombre dado
  C) COMUNES solo con JOSE/MARIA exactos

A la vez se mira p3, que en las CURPs reales SIEMPRE viene del RFC y por eso
sirve de referencia: si el nombre tiene MARIA de primera, la inicial de p3
delata cual nombre usado RENAPO.
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
c.execute("""SELECT u6rfc, dmname, u6estado, curp, genero FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18
               AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'""")
ref = c.fetchall()
conn.close()


def p15_con(nombre, comunes):
    """Consonante interna del 'nombre dado' bajo una regla COMUNES dada."""
    p = cc._partes(nombre)
    dados = p[:-2] if len(p) > 2 else p
    if not dados:
        return ""
    if len(dados) > 1 and dados[0] in comunes:
        return cc.cons_interna(dados[1])
    return cc.cons_interna(dados[0])


VARIANTES = {
    "A) COMUNES {JOSE,MARIA,MA,J}": {"JOSE", "MARIA", "MA", "J"},
    "B) sin COMUNES (1er nombre)": set(),
    "C) solo {JOSE,MARIA}": {"JOSE", "MARIA"},
}

tally = Counter()
solo_con_comunes = Counter()
for rfc, nom, est, curp_real, gen in ref:
    real = curp_real.strip().upper()
    p = cc._partes(nom)
    dados = p[:-2] if len(p) > 2 else p
    es_comun = bool(dados) and dados[0] in cc.COMUNES
    for etiqueta, comunes in VARIANTES.items():
        mi = p15_con(nom, comunes)
        ok = (mi == real[15])
        tally[(etiqueta, ok)] += 1
        if es_comun:
            solo_con_comunes[(etiqueta, ok)] += 1

print("p15 (consonante interna del nombre dado) sobre 714 CURPs reales")
print("=" * 72)
for etiqueta in VARIANTES:
    ok = tally[(etiqueta, True)]
    dif = tally[(etiqueta, False)]
    print("  %-34s %3d ok  %3d mal   -> %.2f%%"
          % (etiqueta, ok, dif, 100.0 * ok / max(1, ok + dif)))
print()
print("Solo en los nombres que empiezan con JOSE/MARIA/MA/J (los que la regla decide):")
n_comun = sum(1 for rfc, nom, est, cr, g in ref
              if (cc._partes(nom)[:-2] or [None]) and
              (cc._partes(nom)[:-2] or [''])[0] in cc.COMUNES)
for etiqueta in VARIANTES:
    ok = solo_con_comunes[(etiqueta, True)]
    dif = solo_con_comunes[(etiqueta, False)]
    tot = ok + dif
    print("  %-34s %3d ok  %3d mal   -> %s"
          % (etiqueta, ok, dif,
             ("%.2f%%" % (100.0 * ok / max(1, tot))) if tot else "n/a"))

# evidencia directa: que dice p3 (del RFC, fiable) de esos casos
print()
print("MUESTRA de nombres con MARIA/JOSE de primera, y que dice p3 del RFC:")
n = 0
for rfc, nom, est, curp_real, gen in ref:
    real = curp_real.strip().upper()
    p = cc._partes(nom)
    dados = p[:-2] if len(p) > 2 else p
    if not dados or dados[0] not in cc.COMUNES:
        continue
    print("   %-42s p3(RFC)=%s  p15 real=%s  mi p15=%s  %s"
          % (nom[:42], real[3], real[15], p15_con(nom, cc.COMUNES),
             "OK" if p15_con(nom, cc.COMUNES) == real[15] else "DIF"))
    n += 1
    if n >= 25:
        break