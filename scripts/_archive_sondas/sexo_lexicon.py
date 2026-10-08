"""Construye el lexicono de nombres debiles (femeninos/masculinos) con DATOS.

Fuentes, en orden de confianza:
  1. Las 717 filas procesadas que traen columna `genero`: nombre dado -> H/M.
  2. Los nombres mas frecuentes del pool completo de 4.86M (no hay sexo ahi,
     pero saber cuales son los comunes dice cuales me estan cayendo en
     `inicial`, que es el modo que falla).

Salida: los nombres debiles que YA cubre el lexicono actual vs los que se le
escapan, para no anadir a ciegas.
"""
import os
import sqlite3
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import _partes, _FEM, _MASC, inferir_sexo  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

# --- 1. verdad conocida -------------------------------------------------
c.execute("""SELECT dmname, genero FROM santander_records
             WHERE genero IS NOT NULL AND TRIM(genero)!=''
               AND dmname IS NOT NULL AND TRIM(dmname)!=''
               AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'""")
verd = c.fetchall()
print("Filas con `genero` conocido (fuera de los RFC enmascarados): %d" % len(verd))

nombres_sexo = defaultdict(Counter)
for nom, g in verd:
    g = g.strip().upper()[:1]
    p = _partes(nom)
    for d in p[:-2] if len(p) > 2 else p:
        if d:
            nombres_sexo[d][g] += 1

# --- 2. los debiles que el lexicono actual ERRA ------------------------
print()
print("Nombres con verdad conocida que mi lexicono clasifica MAL:")
print("-" * 68)
errores = []
for nombre, cnt in sorted(nombres_sexo.items(), key=lambda x: -sum(x[1].values())):
    tot = cnt['H'] + cnt['M']
    if tot < 2:
        continue
    real = 'M' if cnt['M'] > cnt['H'] else 'H'
    _, conf = inferir_sexo(nombre + " X Y", None)
    # infiero solo con el nombre dado
    if nombre in _FEM:
        mio = 'M'
    elif nombre in _MASC:
        mio = 'H'
    else:
        mio, conf = inferir_sexo(nombre, None)
        conf = 'inicial'
    if mio != real:
        errores.append((nombre, real, mio, tot, cnt['M'], cnt['H'], conf))
for e in errores[:30]:
    print("   %-22s real=%s  yo=%s  (n=%d: %dM/%dH)  conf=%s"
          % (e[0], e[1], e[2], e[3], e[4], e[5], e[6]))
print("   TOTAL errores de sexo entre los nombres con verdad conocida: %d" % len(errores))

# --- 3. ataque al lexicono: quien cae en `inicial` ----------------------
print()
print("=" * 68)
print("Nombres mas FRECUENTES del pool de 4.86M (top 60)")
print("=" * 68)
c.execute("""SELECT dmname, COUNT(*) c FROM santander_records
             WHERE results IS NULL AND dmname IS NOT NULL AND TRIM(dmname)!=''
             GROUP BY 1 ORDER BY c DESC LIMIT 400""")
pool = c.fetchall()
frecuencia = Counter()
for nom, n in pool:
    p = _partes(nom)
    for d in (p[:-2] if len(p) > 2 else p):
        if d:
            frecuencia[d] += n

top = frecuencia.most_common(80)
print("   %-24s %10s %8s %8s" % ("NOMBRE DADO", "EN POOL", "SEXO", "CONF"))
caen_inicial = []
for nombre, n in top:
    if nombre in _FEM:
        s, conf = 'M', 'lexicono'
    elif nombre in _MASC:
        s, conf = 'H', 'lexicono'
    else:
        s, conf = inferir_sexo(nombre, None)
    if conf == 'inicial':
        caen_inicial.append((nombre, n))
    print("   %-24s %10d %8s %8s" % (nombre[:24], n, s, conf))

print()
print("=" * 68)
print("De los 80 mas comunes, %d caen en modo `inicial` (sospechosos):" % len(caen_inicial))
for nombre, n in caen_inicial:
    print("   %-24s %10d" % (nombre[:24], n))
tot_ini = sum(n for _, n in caen_inicial)
print("   personas afectadas en el pool: %d" % tot_ini)

conn.close()