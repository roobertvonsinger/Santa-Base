"""¿Cuales de los nombres que hoy BLOQUEAN el sync tienen verdad observada?

El sync escribe 3 de 100,000 porque el 95.8% se descarta por
`sexo_nombre_desconocido`, y el bloqueador #1 es GABRIEL (124 filas en una
muestra de 3,000). GABRIEL no esta en el lexico por ser unisex.

La pregunta: ¿la columna `genero` de las 714 filas dice cual es el sexo real de
los nombres que hoy bloquean? Si lo dice, la regla no es "agregar al lexico"
sino "usar la columna cuando exista y descartar cuando no" -- y el unico
cambio que hace falta es dejar de tirar `genero` en el camino, que ya se
arreglo en curp_sync.py, mas anadir los nombres CON verdad medida.

Los que no tienen verdad observada se quedan fuera: no se inventan.
"""
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import curp_calc as cc  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("""SELECT dmname, genero FROM santander_records
             WHERE genero IS NOT NULL AND TRIM(genero)!=''
               AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'
               AND LENGTH(TRIM(u6rfc))=13""")
t = {}
t_2do = {}
for nom, g in c.fetchall():
    g = g.strip().upper()[:1]
    if g not in ("H", "M"):
        continue
    p = cc._partes(nom)
    dados = p[:-2] if len(p) > 2 else p
    for pos, d in enumerate(dados):
        if pos == 0:
            t.setdefault(d, Counter())[g] += 1
        else:
            t_2do.setdefault(d, Counter())[g] += 1

print("Referencias con genero: %d nombres en 1er puesto, %d en 2do"
      % (len(t), len(t_2do)))
print()
print("NOTA DE METODO: solo el PRIMER nombre dado decide el sexo de la CURP")
print("(los nombres compuestos se saltan al primero con la regla COMUNES).")
print("Medir la verdad de un nombre que aparece sobre todo como 2do nombre")
print("da el sexo equivocado -- REFUGIO sale H (0M/4H) solo porque en las 714")
print("aparece en 'MARIA DEL REFUGIO', que es mujer. Por eso se mide solo pos 0.")
print()
print()

# los bloqueadores que salio resto_pool.py, en orden de peso
BLOQ = ["GABRIEL", "REFUGIO", "ANGELES", "LEONCIO", "J", "ILDEFONSO", "REYES",
        "BERNARDINO", "CRESCENCIO", "ALEJANDRINA", "JULISSA", "VIDAL",
        "JENNIFER", "HERMILO", "JULIANA", "ERICA", "APOLONIO", "ODILON",
        "YUNUEN", "ADELAIDA", "MARTINIANO", "MARICARMEN", "NALLELY", "RUFINO",
        "NELIDA", "NOEL", "ELIGIO", "LAUREANO", "ANABELL", "BONIFACIO",
        "VANNIA", "YANELI", "AYDE", "VEUDI", "DARISNEL", "ERICKA",
        "OTILIA", "MARCELA", "GUADALUPE", "JORGE", "LUIS", "MARIA"]

f_confiables = []
f_sin_dato = []
print("Verdad observada de los nombres que hoy bloquean:")
for n in BLOQ:
    v = t.get(n)
    if v and (v['M'] + v['H']) >= 2:
        real = 'M' if v['M'] > v['H'] else 'H'
        conf = 1.0 * max(v['M'], v['H']) / (v['M'] + v['H'])
        print("   %-14s -> %s  (%dM/%dH, conf %.0f%%)" % (n, real, v['M'], v['H'], conf * 100))
        f_confiables.append(n)
    elif v:
        real = 'M' if v['M'] > v['H'] else 'H'
        print("   %-14s -> %s  (1 sola muestra, NO alcanza)" % (n, real))
    else:
        print("   %-14s -> sin dato" % n)
        f_sin_dato.append(n)

print()
print("CON verdad medida (>=2 muestras): %d -> %s"
      % (len(f_confiables), " ".join(f_confiables)))
print()
print("SIN dato: %d -> NO se agregan (no se inventa el sexo)" % len(f_sin_dato))
conn.close()