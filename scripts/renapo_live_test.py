"""PRUEBA EN VIVO DEL CALCULADOR.

Toma CURPs del pool de 4.86M (nunca procesadas), las calcula con
scripts/curp_calc.py y las somete a RENAPO con _execute_attempt.

Escala:
  ON  = RENAPO acepto el CURP -> llego a la pantalla bancaria (elegible)
  OB-ORQ-05 = RENAPO lo rechazo -> CURP mal
  RETRY = fallo de red, se reintenta

Este numero es el que decide si el pipe se puede alimentar a escala.
"""
import argparse
import os
import sqlite3
import sys
import time

sys.path.insert(0, r'C:\Users\rober\Dropbox\TESTING DEV\repos\santa-base')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from santander_runner import _execute_attempt  # noqa: E402
from curp_calc import calcular_curp, curp_valida  # noqa: E402

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'


def probar(curp, estado, intentos=3):
    r = None
    for _ in range(intentos):
        r = _execute_attempt(curp, state=estado)
        if r.get("status") != "RETRY":
            return r
        time.sleep(4)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=15)
    ap.add_argument('--offset', type=int, default=0)
    ap.add_argument('--pausa', type=float, default=4.0)
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""SELECT id, u6rfc, dmname, u6estado FROM santander_records
                 WHERE results IS NULL AND u6rfc IS NOT NULL
                   AND LENGTH(TRIM(u6rfc)) = 13
                   AND dmname IS NOT NULL AND TRIM(dmname) != ''
                   AND u6estado IS NOT NULL AND TRIM(u6estado) != ''
                 ORDER BY id LIMIT ? OFFSET ?""", (args.n, args.offset))
    filas = c.fetchall()
    conn.close()

    print("PRUEBA EN VIVO: %d CURPs calculadas del pool de 4.86M" % len(filas))
    print("=" * 74)
    on = off = retry = 0
    invalidas = 0
    for id_, rfc, nombre, estado in filas:
        curp, det = calcular_curp(nombre, rfc, estado, genero_col=None)
        if curp is None:
            print("   id=%-9s NO CALCULABLE: %s" % (id_, det))
            continue
        if not curp_valida(curp):
            invalidas += 1
        r = probar(curp, estado)
        st = r.get("status")
        if st == "ON":
            on += 1
        elif st == "OFF":
            off += 1
        else:
            retry += 1
        print("   %s  %-38s  sexo=%s(%s)  -> %-5s %s"
              % (curp, nombre[:38], det.get("sexo"), det.get("conf"), st,
                 str(r.get("detail"))[:36]), flush=True)
        time.sleep(args.pausa)

    total = on + off
    print("=" * 74)
    print("RESULTADO: ON=%d  OFF=%d  RETRY=%d" % (on, off, retry))
    if total:
        print("  aceptadas por RENAPO: %d/%d = %.1f%%" % (on, total, 100.0 * on / total))
    print("  CURPs con digito verificador mal formado: %d" % invalidas)
    print("  (control: sobre las 717 de la BD el calculador acierta 98.19%%)")


if __name__ == '__main__':
    main()