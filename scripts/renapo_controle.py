"""PRUEBA DECISIVA: manda a RENAPO CURPs REALES (las 717 de la BD).

Si una CURP real, correcta por construccion, tambien la rechaza con OB-ORQ-05,
entonces OB-ORQ-05 NO significa "CURP mal formada" sino "esa persona no esta
en el registro de RENAPO" (y mi 29.4% es el TECHO, no un bug del calculo).

Si en cambio las reales pasan, el problema es mio y sigo buscando.

Compara 3 grupos con el mismo pipeline _execute_attempt:
  A) CURPs REALES de la BD, de las que RENAPO ya habia aceptado (control +)
  B) CURPs REALES de la BD, de las que RENAPO habia rechazado (control -)
  C) CURPs CALCULADAS por mi (el grupo que estamos midiendo)
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


def clasificar(r):
    st = r.get("status")
    det = str(r.get("detail"))
    if "OB-ORQ-05" in det:
        return "RENAPO_RECHAZA"
    if st == "ON":
        return "PASA"
    return "OTRO:" + det[:30]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=8, help='por grupo')
    ap.add_argument('--pausa', type=float, default=4.0)
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Grupo A: REALES que RENAPO acepto antes (results sin OB-ORQ-05)
    c.execute("""SELECT u6rfc, dmname, u6estado, curp, results FROM santander_records
                 WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18
                   AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'
                   AND results IS NOT NULL AND results NOT LIKE '%OB-ORQ-05%'
                   AND UPPER(results) NOT LIKE '%DESCARTADO%'
                 ORDER BY id LIMIT ?""", (args.n * 3,))
    aceptadas = c.fetchall()
    # Grupo B: REALES que RENAPO rechazo con OB-ORQ-05
    c.execute("""SELECT u6rfc, dmname, u6estado, curp, results FROM santander_records
                 WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18
                   AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'
                   AND results LIKE '%OB-ORQ-05%'
                 ORDER BY id LIMIT ?""", (args.n * 3,))
    rechazadas = c.fetchall()

    # Grupo C: CALCULADAS por mi, del pool nunca procesado
    c.execute("""SELECT u6rfc, dmname, u6estado FROM santander_records
                 WHERE results IS NULL AND LENGTH(TRIM(u6rfc))=13
                   AND dmname IS NOT NULL AND TRIM(dmname)!=''
                   AND u6estado IS NOT NULL AND TRIM(u6estado)!=''
                 ORDER BY id LIMIT 400""")
    calculadas = []
    for rfc, nom, est in c.fetchall():
        curp, det = calcular_curp(nom, rfc, est)
        if curp and curp_valida(curp):
            calculadas.append((rfc, nom, est, curp, "calculada"))
        if len(calculadas) >= args.n * 3:
            break
    conn.close()

    print("=" * 78)
    print("GRUPO A: CURPs REALES que RENAPO ya habia ACEPTADO antes")
    print("=" * 78)
    tally = {}
    n = 0
    for rfc, nom, est, curp, res in aceptadas:
        if n >= args.n:
            break
        r = probar(curp.strip().upper(), est)
        k = clasificar(r)
        tally[k] = tally.get(k, 0) + 1
        print("   %s  %-34s -> %-14s %s"
              % (curp.strip().upper()[:18], nom[:34], k, str(r.get('detail'))[:26]), flush=True)
        n += 1
        time.sleep(args.pausa)

    print()
    print("=" * 78)
    print("GRUPO B: CURPs REALES que RENAPO RECHAZO con OB-ORQ-05")
    print("=" * 78)
    n = 0
    for rfc, nom, est, curp, res in rechazadas:
        if n >= args.n:
            break
        r = probar(curp.strip().upper(), est)
        k = clasificar(r)
        tally[k] = tally.get(k, 0) + 1
        print("   %s  %-34s -> %-14s %s"
              % (curp.strip().upper()[:18], nom[:34], k, str(r.get('detail'))[:26]), flush=True)
        n += 1
        time.sleep(args.pausa)

    print()
    print("=" * 78)
    print("GRUPO C: CURPs CALCULADAS por mi (pool nunca procesado)")
    print("=" * 78)
    n = 0
    for rfc, nom, est, curp, res in calculadas:
        if n >= args.n:
            break
        r = probar(curp, est)
        k = clasificar(r)
        tally[k] = tally.get(k, 0) + 1
        print("   %s  %-34s -> %-14s %s" % (curp[:18], nom[:34], k,
                                           str(r.get('detail'))[:26]), flush=True)
        n += 1
        time.sleep(args.pausa)

    print()
    print("=" * 78)
    print("RESULTADO por grupo:")
    for etiqueta in ("A: REALES aceptados antes", "B: REALES rechazados antes",
                     "C: CALCULADAS por mi"):
        pass
    print("   (ver arriba). Tally global: %s" % tally)
    print()
    print("INTERPRETACION:")
    print("   Si el grupo A (reales, antes aceptados) ahora da RENAPO_RECHAZA,")
    print("   el rechazo NO es por formato de mi calculo sino por el registro.")


if __name__ == '__main__':
    main()