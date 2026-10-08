"""
EXPERIMENTO DECISIVO: que valida RENAPO de la CURP?

Base: ZAPM740918HJCRRR08 (MARCO ANTONIO ZARAGOZA PEREZ) -- el unico registro que
llego vivo a la etapa N2. Se re-verifica (control) y luego se le mutan posiciones
una a una. Si el banco acepta una mutacion, esa posicion NO se valida.

Se usa el mismo pipeline de santander_runner._execute_attempt, sin inventar nada.
"""
import sys
import time

sys.path.insert(0, r'C:\Users\rober\Dropbox\TESTING DEV\repos\santa-base')

from santander_runner import _execute_attempt

BASE = "ZAPM740918HJCRRR08"
ESTADO = "JALISCO"

PRUEBAS = [
    ("CONTROL (sin cambios)",        BASE),
    ("pos13/14/15 -> XXX",           BASE[:13] + "XXX" + BASE[16:]),
    ("pos15 -> Z",                   BASE[:15] + "Z" + BASE[16:]),
    ("pos13 -> Z",                   BASE[:13] + "Z" + BASE[14:]),
    ("pos17 -> digito calculado (4)", BASE[:17] + "4"),
    ("pos10 sexo -> M (real H)",     BASE[:10] + "M" + BASE[11:]),
    ("pos4-9 fecha -> 999999",       BASE[:4] + "999999" + BASE[10:]),
]

for etiqueta, curp in PRUEBAS:
    t0 = time.time()
    r = _execute_attempt(curp, state=ESTADO)
    print("%-32s %s -> %-6s %s  (%.1fs)"
          % (etiqueta, curp, r.get("status"), r.get("detail"), time.time() - t0), flush=True)
    time.sleep(3)   # no rafear: 3s entre intentos
