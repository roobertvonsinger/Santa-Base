"""¿Funciona el onboarding de Santander SIN proxy?

Contexto medido:
  - proxy001 rechaza la cuenta (403/431 en las 4 variantes de usuario)
  - proxy-gate vive en la VPS Karen, que esta inaccesible (SSH y Tailscale caidos)
  -> no hay ninguna fuente de proxy disponible

La pregunta que decide si hay salida: ¿el onboarding responde desde la IP de
Robert directamente? Si responde, el purger puede correr sin proxy (con el
riesgo de que Santander bloquee esa IP, que es decision de Robert, no mia).

UNA sola llamada. No es una prueba de carga: es medir si existe camino.
"""
import os
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
import asyncio  # noqa: E402
from santander_runner import check_single_curp  # noqa: E402

# Un CURP ya conocido del pool (NO del boveda de hits: es material gastado,
# pedirlo de nuevo no gasta nada nuevo y no expone un hit a una IP sin proxy).
CURP = os.environ.get("TEST_CURP", "GATJ621114HMCRRM08")

print("Probando onboarding SIN proxy, 1 sola llamada")
print("curp de prueba: %s" % CURP)
print()
t0 = time.time()
try:
    # check_single_curp es una corrutina: hay que correrla en un event loop.
    # `use_proxy=False` es lo que de verdad quita el proxy; con proxy=None NO
    # bastaba (el runner reponia el suyo).
    r = asyncio.run(check_single_curp(CURP, proxy=None, state="CIUDAD DE MEXICO",
                                      use_proxy=False))
    dt = time.time() - t0
    print("status : %s" % r.get("status"))
    print("detalle: %s" % str(r.get("detail"))[:150])
    print("pantalla: %s" % r.get("pantalla"))
    print("tiempo : %.1fs" % dt)
    print()
    if r.get("status") == "ON":
        print("VEREDICTO: HAY CAMINO. El onboarding responde desde la IP de Robert.")
        print("Se puede correr el purger sin proxy. El riesgo de baneo de IP")
        print("existe y es decision de Robert que aceptarlo.")
    elif r.get("status") == "OFF":
        det = str(r.get("detail"))
        if "OB-ORQ-05" in det:
            print("VEREDICTO: HAY CAMINO. Rechazo de RENAPO = la peticion LLEGO")
            print("al servidor y laiko respondio. Lo unico que fallo es el dato,")
            print("no la conectividad. El proxy no es bloqueante aqui.")
        else:
            print("VEREDICTO: LLEGO al banco pero OFF por '%s'." % det[:60])
    else:
        print("VEREDICTO: RETRY/error -> sin camino sin proxy.")
except Exception as e:
    print("EXCEPCION en %.1fs: %s" % (time.time() - t0, str(e)[:220]))