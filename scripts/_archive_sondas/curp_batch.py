"""Calcula y escribe la CURP en el pool sin procesar, en lotes.

No es un simulacro: escribe el valor real calculado en la columna `curp` de
`santander_records`, para que el purger (que exige curp IS NOT NULL) vuelva a
ver candidatos. Los lotes son para no cargar 4.86M de memoria de una vez.

    python scripts/curp_batch.py --limit 5000 --offset 0

Reporta cuantos quedaron pendientes y por que motivo.
"""
import argparse
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import calcular_curp  # noqa: E402

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=5000)
    ap.add_argument('--offset', type=int, default=0)
    ap.add_argument('--dry', action='store_true', help='solo muestra, no escribe')
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()

    c.execute("""SELECT id, u6rfc, dmname, u6estado FROM santander_records
                 WHERE (curp IS NULL OR TRIM(curp) = '')
                   AND u6rfc IS NOT NULL AND LENGTH(TRIM(u6rfc)) = 13
                 ORDER BY id LIMIT ? OFFSET ?""", (args.limit, args.offset))
    filas = c.fetchall()
    print("lote: %d filas (offset %d)" % (len(filas), args.offset))

    stats = Counter()
    updates = []
    for id_, rfc, nombre, estado in filas:
        curp, det = calcular_curp(nombre, rfc, estado, genero_col=None)
        if curp is None:
            stats[det] += 1
            continue
        stats['ok'] += 1
        updates.append((curp, id_))

    print("calculadas: %d   rechazadas: %d" % (
        stats['ok'], sum(v for k, v in stats.items() if k != 'ok')))
    for k, v in stats.most_common():
        if k != 'ok':
            print("   motivo %-40s %d" % (k, v))

    print("muestra:")
    for curp, id_ in updates[:5]:
        print("   id=%-9d %s" % (id_, curp))

    if args.dry:
        print("dry-run: nada escrito")
        conn.close()
        return

    c.executemany("UPDATE santander_records SET curp = ? WHERE id = ?", updates)
    conn.commit()
    print("escritas: %d" % len(updates))

    c.execute("""SELECT COUNT(*) FROM santander_records
                 WHERE curp IS NOT NULL AND TRIM(curp) != '' AND results IS NULL""")
    print("pool ahora con curp y sin procesar: %d" % c.fetchone()[0])
    conn.close()


if __name__ == '__main__':
    main()