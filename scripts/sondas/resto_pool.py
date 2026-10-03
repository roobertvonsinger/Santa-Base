"""¿Vale la pena seguir el sync, o esta girando sobre filas muertas?

Medido: el ultimo lote leyo 100,000 y escribio 3. El 95.8% se descarta por
`sexo_nombre_desconocido`. Como `curp_sync` hace
`WHERE curp IS NULL ... ORDER BY id LIMIT N`, en cada corrida vuelve a leer las
MISMAS filas y a descartarlas otra vez. Eso no es que el pool sea malo, es que
el sync no avanza de puntero.

Este script mide, sobre la cola REAL (las filas que quedan sin CURP):
  1. que fraccion es calculable hoy con el lexico actual
  2. si esa fraccion es Homogenea por bloques de id o si al principio si y
     despues no -- si es homogenea, el sync tiene un tope real y conviene
     marcar las imposibles; si es homogenea, el problema es el lexico.
  3. quienes son los nombres desconocidos: gente valida que no esta en mi
     lexico, o basura.
"""
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import curp_calc as cc  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13""")
print("Cola por procesar (RFC persona fisica): %d" % c.fetchone()[0])
print()

# --- 1 y 2: por bloques de 100k, que fraccion es calculable ---------------
print("FRACCION CALCULABLE POR BLOQUE (la cola, no todo el pool):")
print("  %-14s %8s %8s %7s" % ("rango id", "filas", "ok", "pct"))
print("  " + "-" * 40)
bloques = []
INI = 1550000
for base in range(INI, INI + 2000000, 100000):
    c.execute("""SELECT dmname, u6rfc, u6estado FROM santander_records
                 WHERE id >= ? AND id < ? AND results IS NULL
                   AND (curp IS NULL OR TRIM(curp)='')
                   AND LENGTH(TRIM(u6rfc))=13 LIMIT 4000""", (base, base + 100000))
    filas = c.fetchall()
    if not filas:
        continue
    ok = 0
    for nom, rfc, est in filas:
        calc, _ = cc.calcular_curp(nom, rfc, est)
        if calc:
            ok += 1
    pct = 100.0 * ok / len(filas)
    bloques.append(pct)
    print("  %-14s %8d %8d %6.1f%%" % ("%dk-%dk" % (base // 1000, (base + 100000) // 1000),
                                       len(filas), ok, pct))
    if len(bloques) >= 10:
        break

if bloques:
    print()
    print("Rango de fraccion calculable: %.1f%% .. %.1f%%" % (min(bloques), max(bloques)))
    if max(bloques) - min(bloques) < 5:
        print("  -> HOMOGENEA: el lexico esta bien o mal parejo en toda la cola.")
        print("     Si es baja, el techo es el lexico, no el sync.")
    else:
        print("  -> HETEROGENEA: hay bloques buenos y malos. El sync debe saltarse")
        print("     los malos, no re-leerlos eternamente.")
print()

# --- 3: quienes son los desconocidos --------------------------------------
c.execute("""SELECT dmname, u6rfc, u6estado FROM santander_records
             WHERE id >= ? AND results IS NULL AND (curp IS NULL OR TRIM(curp)='')
               AND LENGTH(TRIM(u6rfc))=13 LIMIT 3000""", (INI,))
motos = Counter()
descon = Counter()
ej = []
for nom, rfc, est in c.fetchall():
    calc, det = cc.calcular_curp(nom, rfc, est)
    if calc:
        continue
    mot = str(det)
    motos[mot.split(":")[0]] += 1
    if "sexo_" in mot:
        p = cc._partes(nom)
        dados = p[:-2] if len(p) > 2 else p
        for d in dados:
            descon[d] += 1
    if len(ej) < 18:
        ej.append((nom, mot))

print("Motivos de descarte en la cola:")
for k, v in motos.most_common(8):
    print("   %-40s %5d" % (k, v))
print()
print("Nombres que bloquean el sexo (top 30):")
for k, v in descon.most_common(30):
    print("   %-22s %5d" % (k, v))
print()
print("Ejemplos de nombres bloqueados:")
for nom, mot in ej:
    print("   %-40s %s" % (nom[:40], mot[:40]))
conn.close()