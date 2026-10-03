"""PRUEBA VIVA Y DEFINITIVA DEL DIGITO.

La contradiccion: 332 CURPs que RENAPO ACEPTO en la BD dan 9% con mi algoritmo
(azar es 10%), y 244 que RECHAZO dan 11.9%. Si mi algoritmo fuera correcto, las
aceptadas deberian dar ~100%.

Experimento: se toma una CURP REAL de la BD que RENAPO ya acepto, se KNOWS-outh
el digito (pos17) y se prueban los 10 contra RENAPO en vivo.
  - si el digito original da ON -> mi algoritmo esta mal y ademas la BD trae
    CURPs cuyo digito NO es el oficial
  - si el digito de mi algoritmo da ON -> mi algoritmo acierta y la BD trae
    CURPs con digito corrupto
  - si ninguna da ON -> la posicion 17 no se valida sola y depende de mas

Ademas: mutar pos17 de una CURP calculada por mi, de una fila con genero
conocido, para ver si el Generador de la BD es o no el que produce lo que
RENAPO acepta.
"""
import os
import sqlite3
import sys
import time

sys.path.insert(0, r'C:\Users\rober\Dropbox\TESTING DEV\repos\santa-base')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from santander_runner import _execute_attempt  # noqa: E402
from curp_calc import digito_verificador  # noqa: E402

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT curp, results, dmname, u6rfc, estado FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp)) = 18
               AND results NOT LIKE '%RENAPO%' AND results NOT LIKE '%operador%'
             LIMIT 6""")
ACEPTADAS = [(r[0].strip().upper(), (r[1] or ''), r[2], r[3], r[4])
             for r in c.fetchall()]
conn.close()


def probar(curp, estado, intentos=3):
    r = None
    for i in range(intentos):
        r = _execute_attempt(curp, state=estado or "JALISCO")
        if r.get("status") != "RETRY":
            return r
        print("      (reintento %d: %s)" % (i + 1, str(r.get('detail'))[:50]), flush=True)
        time.sleep(4)
    return r


print("=" * 74)
print("A) CURPs que la BD ya tiene como ACEPTADAS: re-verifico en vivo")
print("   (si el ON se mantiene, la BD tiene CURPs genuinas)")
print("=" * 74)
for curp, res, nom, rfc, ed in ACEPTADAS[:4]:
    print("\n  %s   %s" % (curp, nom[:38]), flush=True)
    print("     RENAPO dice: %s" % str(res)[:46], flush=True)
    r = probar(curp, ed)
    print("     -> re-consulta EN VIVO: %-6s %s" % (r.get("status"), str(r.get("detail"))[:44]), flush=True)
    time.sleep(3)

print()
print("=" * 74)
print("B) Mismo prefijo de una ACEPTADA, los 10 digitos posibles en pos17")
print("=" * 74)
curp0, res0, nom0, rfc0, ed0 = ACEPTADAS[0]
prefijo = curp0[:17]
print("   Base: %s  (aceptada en BD, pos17 real='%s')" % (curp0, curp0[17]))
print("   Digito que dice MI algoritmo: %s" % digito_verificador(curp0[:16]))
print()
for d in "0123456789":
    cand = prefijo + d
    r = probar(cand, ed0)
    marca = ""
    if cand == curp0:
        marca = "  <== LA CURP REAL DE LA BD"
    elif cand == prefijo + digito_verificador(curp0[:16]):
        marca = "  <== MI ALGORITMO"
    print("   pos17='%s' %s -> %-6s %s%s"
          % (d, cand, r.get("status"), str(r.get("detail"))[:38], marca), flush=True)
    time.sleep(3)