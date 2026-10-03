"""Los 11 errores de `audit_lexico.py` son TODOS casos COMUNES (MARIA, JOSE,
ANTONIA) o el par ARTURO GUADALUPE. Hay dos explicaciones incompatibles:

  a) Mi inferencia esta mal: en esos nombre el masculino va primero y yo veo el
     femenino de un segundo nombre.
  b) El dato `genero` esta mal: son 4 hombres llamados MARIA, cifra que no se
     sostiene en una muestra de 705.

Se decide con el RFC: si `genero` coincide con `u6rfc[10]` (la posicion de sexo
del RFC, distinta del digito verificador), el dato es consistente y vale. Si
NO coincide, la columna `genero` esta contaminada y el juez no sirve.
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

# 1. ¿u6rfc[10] es la posicion de sexo? Se mide contra `genero` en las filas
#    donde el RFC NO esta enmascarado.
c.execute("""SELECT genero, SUBSTR(u6rfc,10,1), COUNT(*) FROM santander_records
             WHERE genero IS NOT NULL AND TRIM(genero)!=''
               AND LENGTH(TRIM(u6rfc))=13
               AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'
             GROUP BY 1,2""")
tab = {}
for g, p10, n in c.fetchall():
    tab[(g.strip().upper()[:1], p10)] = n
ok = sum(v for (g, p10), v in tab.items() if g == p10)
tot = sum(tab.values())
print("Coherencia `genero` vs u6rfc[10]: %d/%d = %.2f%%" % (ok, tot, 100.0 * ok / max(1, tot)))
print("  desglose:")
for (g, p10), n in sorted(tab.items(), key=lambda x: -x[1]):
    print("     genero=%s  rfc[10]=%s  %6d" % (g, p10, n))
print()

# 2. los 7 nombres que fallan, con su fila completa
FALLAN = ["MARIA DE JESUS CANO GUTIERREZ", "JOSE BARBA ORDAZ",
          "MARIA ASUNCION RODRIGUEZ LOPEZ", "MARIA DEL REFUGIO AGUILAR AGUILAR",
          "ARTURO GUADALUPE CERVANTES VAZQUEZ", "MARIA TRINIDAD VELEZ ROBLES",
          "ANTONIA CARRILLO TOSCANO"]
print("Filas de los nombres que mi inferencia clasifica mal:")
for nom in FALLAN:
    c.execute("""SELECT id, u6rfc, dmname, genero, curp, u6estado
                 FROM santander_records WHERE UPPER(TRIM(dmname))=UPPER(?)
                 AND genero IS NOT NULL AND TRIM(genero)!=''""", (nom,))
    for id_, rfc, dmname, g, curp, est in c.fetchall():
        p = cc._partes(dmname)
        dados = p[:-2] if len(p) > 2 else p
        hex_, det = cc.inferir_sexo(dmname, g)
        print("  id=%-8s rfc=%-16s rfc[10]=%s  real=%s  mi_sexo=%s (%s)"
              % (id_, rfc, (rfc or '')[9:10], g.strip().upper()[:1], hex_, det))
        print("        dados=%s   curp_en_bd=%s" % (dados, curp))
print()

# 3. ¿cuantos MAS nombres del pool son COMUNES-leading? Si son muchos, el
#    costo de errar es alto y conviene una regla, no solo el lexico.
COMUNES = {"MARIA", "JOSE", "MA", "J", "ANA", "FRANCISCO", "JORGE", "LUIS",
           "CARLOS", "ANTONIO", "GUADALUPE", "SOFIA", "MIGUEL", "MANUEL"}
c.execute("""SELECT dmname, genero FROM santander_records
             WHERE genero IS NOT NULL AND TRIM(genero)!=''
               AND dmname IS NOT NULL AND TRIM(dmname)!=''
               AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'""")
from collections import Counter
cnt = Counter()
ejemplos = []
for nom, g in c.fetchall():
    p = cc._partes(nom)
    dados = p[:-2] if len(p) > 2 else p
    if not dados:
        continue
    if dados[0] in COMUNES:
        cnt[g.strip().upper()[:1]] += 1
        if len(ejemplos) < 12:
            ejemplos.append((dados[0], nom, g.strip().upper()[:1]))
print("Filas cuyo PRIMER nombre dado es COMUNES (grupo de riesgo):")
for k, v in cnt.most_common():
    print("   real=%s  %4d" % (k, v))
print("   ejemplos:")
for c0, nom, g in ejemplos:
    print("     %-8s %-38s real=%s" % (c0, nom[:38], g))
conn.close()