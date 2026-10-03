"""Puebla la columna `curp` del pool de 4.86M con CURPs calculadas.

El purger exige `curp IS NOT NULL` (santander_purger.build_segment_query), asi
que sin este paso el pool es invisible para el servicio: de ahi que la boveda
llevara vacia.

Calcula con scripts/curp_calc.py (digito verificador oficial RENAPO, validado
al 100% sobre 576 CURPs de la BD) y escribe en lotes para no cargar 4.86M de
memoria ni un solo WAL gigante.

    python scripts/curp_sync.py --limit 50000
    python scripts/curp_sync.py --status
"""
import argparse
import os
import sqlite3
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import calcular_curp, curp_valida  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')

# CHECKPOINT DEL PUNTERO -- por que existe.
#
# El filtro era `curp IS NULL ... ORDER BY id LIMIT N`. Las filas que NO se
# pueden calcular (RFC enmascarado, estado desconocido, nombre sin lexico)
# siguen con `curp IS NULL` para siempre, asi que cada corrida las volvia a
# leer y el puntero no avanzaba NUNCA. Medido: lote de 100,000 leidas ->
# 3 escritas, y el id maximo con CURP se quedaba clavado.
#
# Ahora el puntero vive en un archivo y avanza con el, de modo que las filas
# imposibles se intentan una sola vez. `--reset` lo pone en 0.
PTR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        ".curp_sync_puntaje")


def leer_puntaje():
    try:
        with open(PTR_PATH) as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def guardar_puntaje(valor):
    tmp = PTR_PATH + ".tmp"
    with open(tmp, "w") as f:
        f.write(str(int(valor)))
    os.replace(tmp, PTR_PATH)


def conectar():
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def estado(conn):
    c = conn.cursor()
    c.execute("""SELECT
                 (SELECT COUNT(*) FROM santander_records WHERE results IS NULL),
                 (SELECT COUNT(*) FROM santander_records
                   WHERE (curp IS NULL OR TRIM(curp)='') AND results IS NULL
                     AND u6rfc IS NOT NULL AND LENGTH(TRIM(u6rfc))=13),
                 (SELECT COUNT(*) FROM santander_records
                   WHERE curp IS NOT NULL AND TRIM(curp)!='' AND results IS NULL),
                 (SELECT COUNT(*) FROM santander_hits)""")
    tot, pend, con_curp, hits = c.fetchone()
    print("  pool sin procesar            : %d" % tot)
    print("  de esos, RFC persona fisica : %d" % pend)
    print("  ya con CURP calculada       : %d" % con_curp)
    print("  boveda de hits              : %d" % hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=50000, help='filas por lote')
    ap.add_argument('--lotes', type=int, default=1, help='cuantos lotes followed')
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--reset', action='store_true',
                    help='pone el puntaje en 0 (reintenta filas ya descartadas)')
    ap.add_argument('--desde', type=int, default=None,
                    help='arranca en este id y actualiza el puntaje')
    args = ap.parse_args()

    conn = conectar()
    print("ESTADO ACTUAL")
    estado(conn)
    print("  puntaje del sync          : %d" % leer_puntaje())
    if args.status or args.dry:
        if args.dry:
            pass
        else:
            conn.close()
            return

    if args.reset:
        guardar_puntaje(0)
        print("  puntaje reiniciado a 0")
    if args.desde is not None:
        guardar_puntaje(args.desde)
        print("  puntaje fijado en %d" % args.desde)

    puntaje = leer_puntaje()
    if args.status or args.dry:
        if args.dry:
            pass
        else:
            conn.close()
            return

    for n_lote in range(args.lotes):
        c = conn.cursor()
        # `id > ?` es lo que hace avanzar el sync. Sin esto (ver la nota del
        # PTR_PATH) el lote se releia entero en cada corrida.
        c.execute("""SELECT id, u6rfc, dmname, u6estado, genero FROM santander_records
                     WHERE (curp IS NULL OR TRIM(curp) = '')
                       AND results IS NULL
                       AND u6rfc IS NOT NULL AND LENGTH(TRIM(u6rfc)) = 13
                       AND id > ?
                     ORDER BY id LIMIT ?""", (puntaje, args.limit))
        filas = c.fetchall()
        if not filas:
            print("\nlote %d: sin filas pendientes (puntaje=%d)" % (n_lote + 1, puntaje))
            break

        stats = Counter()
        updates = []
        for id_, rfc, nombre, estado_txt, genero in filas:
            # `genero` se pasa: es el unico dato de sexo que existe y vale mas
            # que el lexico. Sin el, MARIA+JESUS se resuelve como M siendo H.
            curp, det = calcular_curp(nombre, rfc, estado_txt, genero_col=genero)
            if curp is None:
                stats[str(det).split(":")[0]] += 1
                continue
            if not curp_valida(curp):
                stats["digito_invalido"] += 1
                continue
            stats["ok"] += 1
            if det.get("conf") == "nombre":
                stats["sexo_por_nombre"] += 1
            elif det.get("conf") == "inicial":
                stats["sexo_por_inicial"] += 1
            updates.append((curp, id_))

        if args.dry:
            print("\nlote %d (dry): %d filas -> %d calculadas" % (n_lote + 1, len(filas), stats['ok']))
            for k, v in stats.most_common():
                if k != 'ok':
                    print("    %s = %d" % (k, v))
            conn.close()
            return

        t0 = time.time()
        c.executemany("UPDATE santander_records SET curp = ? WHERE id = ?", updates)
        conn.commit()
        dt = time.time() - t0

        pct_sexo = (100.0 * stats["sexo_por_nombre"] / max(1, stats['ok']))
        print("\nlote %d: leidas=%d  escritas=%d  (%.1fs, %.0f filas/s)"
              % (n_lote + 1, len(filas), len(updates), dt,
                 len(updates) / max(0.01, dt)))
        print("    sexo por nombre : %d  (%.1f%% de las calculadas)"
              % (stats["sexo_por_nombre"], pct_sexo))
        print("    sexo por inicial: %d" % stats["sexo_por_inicial"])
        for k, v in stats.most_common():
            if k not in ("ok", "sexo_por_nombre", "sexo_por_inicial"):
                print("    DESCARTADA %-24s %d" % (k, v))
        print("    muestra:")
        for curp, id_ in updates[:3]:
            print("      id=%-9d %s" % (id_, curp))

        # El puntero avanza con el ULTIMO id del lote, se haya calculado o no.
        # Si solo avanzara con los `updates`, las 99,997 descartadas volverian
        # a entrar en el siguiente lote y el sync no progresaria.
        nuevo_puntaje = max(f[0] for f in filas)
        if nuevo_puntaje > puntaje:
            guardar_puntaje(nuevo_puntaje)
            puntaje = nuevo_puntaje
        print("    puntaje -> %d" % puntaje)

    print("\nESTADO FINAL")
    estado(conn)
    conn.close()


if __name__ == '__main__':
    main()