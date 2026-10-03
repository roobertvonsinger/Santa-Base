"""El homoclave (pos16) de las 717 CURPs REALES de la BD, contra su u6rfc.

Ground truth: las 717 filas ya procesadas traen su CURP real. Si el algoritmo
fuera correcto, pos16 seria '0' para todo nacido antes de 2000 y 'A' despues.
Se cruza pos16 con el año de u6rfc[4:6] para ver que banda usa la BD de verdad.
"""
import os
import sqlite3
from collections import Counter

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT u6rfc, curp FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18""")
rows = c.fetchall()
conn.close()

tabla = Counter()
mismatch = 0
mismatch_ej = []
for rfc, curp in rows:
    real = curp.strip().upper()
    if len(rfc) != 13:
        continue
    yy = rfc[4:6]
    if not yy.isdigit():
        continue
    h16 = real[16]
    tabla[(yy, h16)] += 1

print("Cruzamiento u6rfc[4:6] (año) vs CURP real pos16 (homoclave)")
print("=" * 56)
print("  yy    pos16='0'   pos16='A'")
for yy in sorted(set(k[0] for k in tabla)):
    a = tabla.get((yy, '0'), 0)
    b = tabla.get((yy, 'A'), 0)
    marca = "  <<< BANDAS SEPARADAS" if (a and not b) or (b and not a) else ""
    print("  %s        %-6d      %-6d%s" % (yy, a, b, marca))

print()
tot0 = sum(v for (y, h), v in tabla.items() if h == '0')
totA = sum(v for (y, h), v in tabla.items() if h == 'A')
print("  total pos16='0' (nacio antes de 2000): %d" % tot0)
print("  total pos16='A' (nacio 2000+):         %d" % totA)
print()

# Simula MI codigo actual sobre esas mismas filas
mios = Counter()
for rfc, curp in rows:
    real = curp.strip().upper()
    if len(rfc) != 13 or not rfc[4:6].isdigit():
        continue
    anio = int(rfc[4:6])
    completo = 2000 + anio if anio < 50 else 1900 + anio
    mios["0" if completo < 2000 else "A"] += 1
print("Lo que MI codigo produce sobre las mismas filas:")
print("  '0' = %d    'A' = %d" % (mios['0'], mios['A']))
print("  (la real es  '0' = %d    'A' = %d)" % (tot0, totA))
print()

# Simula la regla corregida: pool bancario => todo es 19xx salvo prueba contraria
corr = Counter()
ej = []
for rfc, curp in rows:
    real = curp.strip().upper()
    if len(rfc) != 13 or not rfc[4:6].isdigit():
        continue
    yy = int(rfc[4:6])
    completo = 1900 + yy
    h = '0' if completo < 2000 else 'A'
    corr[h] += 1
    if h != real[16]:
        mismatch += 1
        if len(ej) < 10:
            ej.append((rfc, real, h))
print("Regla corregida (yy siempre 19xx): '0' = %d  'A' = %d" % (corr['0'], corr['A']))
print("  desaciertos pos16: %d de %d" % (mismatch, sum(corr.values())))
for rfc, real, h in ej:
    print("    rfc=%s  real=%s (yy=%s)  yo daria '%s'" % (rfc, real, rfc[4:6], h))