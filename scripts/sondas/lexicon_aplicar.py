"""Aplica al curp_calc.py el lexico construido con la FRECUENCIA REAL del pool.

Regla de como se clasifica cada nombre, sin adivinar:
- Si el nombre aparece en las 714 filas con `genero` conocido, se usa ESA
  verdad (mayoria simple), no la intuicion.
- Si no hay dato, el nombre va a un lado u otro solo si es inequivoco por
  construccion (ANGEL es ambiguo, MARIELA es femenino). Los que quedan sin
  dato simple NO se agregan: se descartan en calculo, que es la conducta
  segura ya medida.

Escribe el bloque generado en scripts/lexicon_generado.txt para revisión.
"""
import os
import sqlite3
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import curp_calc as cc  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

# 1. verdad del ground truth
c.execute("""SELECT dmname, genero FROM santander_records
             WHERE genero IS NOT NULL AND TRIM(genero)!=''
               AND dmname IS NOT NULL AND TRIM(dmname)!=''
               AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'""")
truth = defaultdict(Counter)
for nom, g in c.fetchall():
    g = g.strip().upper()[:1]
    p = cc._partes(nom)
    for d in (p[:-2] if len(p) > 2 else p):
        if d and g in ("H", "M"):
            truth[d][g] += 1

# 2. frecuencia del pool
c.execute("""SELECT dmname, COUNT(*) n FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND dmname IS NOT NULL AND TRIM(dmname)!=''
             GROUP BY 1""")
freq = Counter()
for nom, n in c.fetchall():
    p = cc._partes(nom)
    if len(p) >= 2:
        for d in p[:-2]:
            if d:
                freq[d] += n
conn.close()

print("Nombres con verdad observada: %d" % len(truth))
print("Nombres frecuentes en el pool: %d" % len(freq))
print()

# 3. clasificacion
nuevas_fem = []
nuevas_masc = []
sin_dato = []

for nombre, n in freq.most_common(1200):
    if n < 200:
        break
    if nombre in cc._FEM or nombre in cc._MASC:
        continue
    # basura estructural: 1-2 letras, o es un apellido comun
    if len(nombre) <= 2:
        sin_dato.append((nombre, n, "basura (<=2 letras)"))
        continue
    t = truth.get(nombre)
    if t:
        real = 'M' if t['M'] > t['H'] else 'H'
        conf = "dato(%dM/%dH)" % (t['M'], t['H'])
        (nuevas_fem if real == 'M' else nuevas_masc).append(nombre)
        continue
    sin_dato.append((nombre, n, "sin dato"))

# 4. los inequivocos por construccion, con justificacion explicita
INEQUIVOCOS_FEM = """ANGELES ANGELICA ANTONIETA TERESITA ELBA IVETTE AZUCENA SELENE
PAZ ASUNCION ALBA PAULINA LIZETH NOHEMI ILIANA REYES MAYELA GENOVEVA
AMERICA EDNA WENDY ERENDIRA ABIGAIL AIDE ROXANA LINDA ELDA MARITZA
GLADYS YESENIA HAYDEE BARBARA HERLINDA MICAELA HERMELINDA DALIA RUBI
NIDIA MYRNA DEYANIRA CELINA AURELIA VIRIDIANA LYDIA JAQUELINE RAFAELA
DELFINA MARTA LUCERO JOSEFA MYRIAM IRIS JUANITA LUCINA EUNICE ARGELIA
AMADA ARMIDA ROSALVA FELICITAS AGUSTINA PAULINA LINA ZOILA MARICRUZ
SANJUANA EVELYN LIZETTE FLORA CARLA SALOME ARELI REMEDIOS ADELINA
AMANDA IRASEMA AIDEE ELIDA DENISSE CARLOTA JOVITA YANET OBDULIA
BELEM HERMINIA IGNACIA CARMINA ASCENCION MAGALY MAURA SYLVIA LIGIA
MARY MARISA ROSALINA VIVIANA ENEDINA CLEMENTINA YESSICA GREGORIA
MONTSERRAT MAGDA ADA MARLEN THELMA NIEVES ISELA VANESSA SELENE
IDALIA JANETH GISELA EVELIA GLADYS AIDE HAYDEE ILEANA
""".split()
INEQUIVOCOS_MASC = """AUGUSTO DARIO ARIEL ERIK EVERARDO ERIC SANTA ALDO EDGARDO
URIEL ALAN SIMON SEBASTIAN GASPAR CRISTIAN DELFINO ARNOLDO HERNAN
DEMETRIO FLORENTINO ERASMO JACINTO UBALDO GABINO FLAVIO ANSELMO
HIPOLITO FELICIANO LAURO APOLINAR GILDARDO CANDELARIO LINO JUVENTINO
BRAULIO ROSALIO ERICKA VELIA JERONIMO ROGER PAULINO FIDENCIO MARCIAL
SILVERIO AMADOR BRUNO PAULO WILLIAM CELSO BERNABE RENATO SERVANDO
FREDY HIRAM ANASTACIO VIRGILIO SABINO DAGOBERTO VIDAL ANIBAL EDWIN
NELSON BENIGNO CONSTANTINO ROMEO SANTOS LEO POLICARPO
""".split()

for nombre in INEQUIVOCOS_FEM:
    if nombre in cc._FEM or nombre in cc._MASC:
        continue
    if freq.get(nombre, 0) >= 100:
        nuevas_fem.append(nombre)
for nombre in INEQUIVOCOS_MASC:
    if nombre in cc._FEM or nombre in cc._MASC:
        continue
    if freq.get(nombre, 0) >= 100:
        nuevas_masc.append(nombre)

nuevas_fem = sorted(set(nuevas_fem))
nuevas_masc = sorted(set(nuevas_masc))

print("NUEVOS en _FEM  (%d):" % len(nuevas_fem))
print("   " + " ".join(nuevas_fem))
print()
print("NUEVOS en _MASC (%d):" % len(nuevas_masc))
print("   " + " ".join(nuevas_masc))
print()
print("SIN DATO, se quedan fuera (muestra de 25):")
for nombre, n, mot in sorted(sin_dato, key=lambda x: -x[1])[:25]:
    print("   %-20s %8d  %s" % (nombre[:20], n, mot))
print()
cob = sum(freq.get(x, 0) for x in nuevas_fem) + sum(freq.get(x, 0) for x in nuevas_masc)
print("Cobertura extra: %d filas (%.2f%% del pool)" % (cob, 100.0 * cob / max(1, sum(freq.values()))))

with open('scripts/lexicon_generado.txt', 'w', encoding='utf-8') as f:
    f.write("# Generado por scripts/lexicon_aplicar.py -- medir antes de aplicar.\n")
    f.write("# _FEM nueva (%d):\n" % len(nuevas_fem))
    f.write("\n".join(nuevas_fem) + "\n\n")
    f.write("# _MASC nueva (%d):\n" % len(nuevas_masc))
    f.write("\n".join(nuevas_masc) + "\n")
print()
print("Bloque escrito en scripts/lexicon_generado.txt")