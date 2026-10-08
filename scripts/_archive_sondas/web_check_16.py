"""PRUEBA DE ORO: las 16 digitos de una CURP elegible, en el login web real.

REGLA DE LA BOVEDA (no negociable): un registro es hit real SOLO si meter sus
16 digitos en el login web de Santander llega a `password_authenticate_form`.
Cualquier otra cosa -- error generico, SuperLinea, you_cannot_continue -- se
borra. No hay "OFF" ni ruido en la boveda.

Se usa la MISMA funcion que el purger, no una copia, para que lo que se mide
aqui sea exactamente lo queCorrera en produccion.
"""
import argparse
import os
import sys
import time

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _RAIZ)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuenta", required=True, help="16 digitos")
    ap.add_argument("--curp", default="")
    ap.add_argument("--nombre", default="")
    ap.add_argument("--id", default="")
    ap.add_argument("--headed", action="store_true")
    return ap.parse_args()


a = parse_args()
cuenta = "".join(ch for ch in a.cuenta if ch.isdigit())
assert len(cuenta) == 16, "la cuenta debe tener 16 digitos, tiene %d" % len(cuenta)

from santander_runner import check_card_existence  # noqa: E402

print("=" * 74)
print("CUENTA  : %s" % cuenta)
if a.curp:
    print("CURP    : %s" % a.curp)
if a.nombre:
    print("NOMBRE  : %s" % a.nombre)
if a.id:
    print("id      : %s" % a.id)
print("=" * 74)

t0 = time.time()
try:
    r = check_card_existence(cuenta)
except Exception as e:
    print("EXCEPCION: %s: %s" % (type(e).__name__, e))
    sys.exit(2)

dt = time.time() - t0
print()
for k, v in r.items():
    print("  %-22s %s" % (k, v))
print()
print("  (%.1fs)" % dt)

veredicto = str(r.get("status") or "").upper()
detalle = str(r.get("detail") or "")
print()
if veredicto == "ACTIVE":
    # ACTIVE solo se devuelve si la respuesta del banco trae
    # "password_authenticate_form" (santander_runner.py:671). No hay otra ruta
    # de codigo que produzca ACTIVE, asi que es HIT por construccion.
    print(">> HIT REAL: el banco devolvio password_authenticate_form.")
    print("   Se queda en la boveda.  detalle: %s" % detalle)
elif veredicto == "INACTIVE":
    print(">> NO HIT: se descarta de la boveda.  detalle: %s" % detalle)
else:
    print(">> ERROR: no se pudo determinar. NO cuenta como hit ni como descarte;")
    print("   hay que reintentar.  detalle: %s" % detalle)
    sys.exit(3)