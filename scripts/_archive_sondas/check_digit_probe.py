"""
Falta cerrar pos17 (digito verificador). El test anterior murio por fallo de red.
Aqui se prueba cada digito替代 con reintentos hasta obtener veredicto de RENAPO.
"""
import sys
import time

sys.path.insert(0, r'C:\Users\rober\Dropbox\TESTING DEV\repos\santa-base')

from santander_runner import _execute_attempt

BASE = "ZAPM740918HJCRRR08"
ESTADO = "JALISCO"


def probar(curp, intentos=3):
    for i in range(intentos):
        r = _execute_attempt(curp, state=ESTADO)
        if r.get("status") != "RETRY":
            return r
        print("    (reintento %d por error de red)" % (i + 1), flush=True)
        time.sleep(4)
    return r


for digito in "0123456789":
    curp = BASE[:17] + digito
    r = probar(curp)
    marca = "  <== identico a la CURP que YA paso" if digito == BASE[17] else ""
    print("pos17='%s'  %s -> %-6s %s%s"
          % (digito, curp, r.get("status"), r.get("detail"), marca), flush=True)
    time.sleep(3)
