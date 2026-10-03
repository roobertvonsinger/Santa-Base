"""Construye _FEM/_MASC a partir de la FRECUENCIA REAL del pool, no de memoria.

Los nombres como GASTON, ANEL, IRINEO, NEMESIO son perfektamente validos y
estan en el pool, pero no estaban en mi lexico escrito a mano. Se extraen los
N mas frecuentes de TODO el pool con su conteo, para ampliar el lexico con dato
y no con suposicion.

El sexo de cada nombre NO se puede leer del pool (no hay columna). Lo que si se
puede: la lista de nombres frecuentes, para cargarlos al lexico. Los que ya
estaban se omiten para no re-litigar los existentes.
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

# Los nombres dados del pool. En vez de traer 4.86M filas, se usan los que
# salen como PRIMER nombre (posicion 0 tras limpiar) -- que es donde esta el
# lexico, no en los apellidos.
c.execute("""SELECT dmname, COUNT(*) n FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
               AND dmname IS NOT NULL AND TRIM(dmname)!=''
             GROUP BY 1""")
nombres_completos = c.fetchall()
conn.close()
print("Nombres completos distintos en el pool: %d" % len(nombres_completos))

freq = Counter()
for nom, n in nombres_completos:
    p = cc._partes(nom)
    if len(p) >= 2:
        # nombres dados = todo menos paterno y materno (las 2 ultimas)
        for d in p[:-2]:
            if d:
                freq[d] += n

print("Nombres dados distintos: %d" % len(freq))
print()
print("Top 900 YA EN MI LEXICO (para no duplicar):")
ya_fem = [k for k in freq if k in cc._FEM]
ya_masc = [k for k in freq if k in cc._MASC]
print("   en _FEM : %d" % len(ya_fem))
print("   en _MASC: %d" % len(ya_masc))
print()
print("=" * 74)
print("TOP 900 NOMBRES DEL POOL QUE NO ESTAN EN MI LEXICO")
print("=" * 74)
print("  (estos son los que hay que anadir; el genero se asigna a mano o por regla)")
faltan = [(k, v) for k, v in freq.most_common(900) if k not in cc._FEM and k not in cc._MASC]
n = 0
for k, v in faltan:
    print("  %-26s %9d" % (k[:26], v))
    n += 1
print()
print("Total faltantes en el top 900: %d" % n)
print("Filas que cubren: %d (%.2f%% del pool)"
      % (sum(v for _, v in faltan), 100.0 * sum(v for _, v in faltan) / max(1, sum(freq.values()))))