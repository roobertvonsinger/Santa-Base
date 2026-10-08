"""¿El limite de credito predice si un registro llega a la pantalla de tarjeta?

Medido hasta ahora: lo procesado tiene credito medio $504,665; la cola tiene
$24,943. Los 270 medidos son la punta de la distribucion (p50 de la cola =
$12,000), asi que la proyeccion lineal NO se puede extender a los 4.55M.

Esto mide si el credito tiene poder predictivo sobre las etapas:
  - RENAPO rechaza (OB-ORQ-05): el mas barato, se cae antes de todo
  - banco rechaza (PE*): llego a caso/preexistencia
  - llega a tarjeta:llego a la pantalla final
  - HIT: es cliente activo

Si `credito` no separa los grupos, el orden credito_desc es indiferente y se
puede dejar como esta. Si separa, el pool hay que muestrearlo de otra parte.
"""
import os
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
CRED = ("CAST(REPLACE(REPLACE(COALESCE(u6licrea,'0'),'$',''),',','') "
        "AS INTEGER)")

conn = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
c = conn.cursor()

c.execute("""SELECT id, results, %s FROM santander_records
             WHERE results IS NOT NULL""" % CRED)
filas = c.fetchall()
print("Filas ya procesadas (results no nulo): %d" % len(filas))


def etapa(r):
    r = r or ""
    if r == "HIT" or r.startswith("HIT"):
        return "HIT (cliente activo)"
    if "tarjeta inactiva" in r:
        return "llego a TARJETA"
    if "LikeU" in r:
        return "LikeU / derivacion"
    if "Contacto preexistente" in r:
        return "contacto preexistente"
    if "PE" in r:
        return "banco rechazo (PE*)"
    if "OB-ORQ-05" in r:
        return "RENAPO rechazo"
    if r.startswith("RETRY"):
        return "RETRY (red)"
    return "descartado por operador"


grupos = {}
for rid, res, cred in filas:
    grupos.setdefault(etapa(res), []).append(cred)

print()
print("%-24s %6s %10s %10s %10s %10s"
      % ("etapa", "n", "med", "min", "max", "mediana"))
print("-" * 76)
for k, v in sorted(grupos.items(), key=lambda x: -len(x[1])):
    v = sorted(x for x in v if x is not None)
    if not v:
        continue
    print("%-24s %6d %10s %10s %10s %10s"
          % (k, len(v), round(sum(v) / len(v)), v[0], v[-1], v[len(v) // 2]))

print()
# Lo que de verdad importa: llegar a la pantalla final de tarjeta.
al_card = (grupos.get("HIT (cliente activo)", []) + grupos.get("llego a TARJETA", []))
todo = [c_ for v in grupos.values() for c_ in v if c_ is not None]
print("--- el punto que decide la proyeccion ---")
print("credito de los que LLEGARON A TARJETA : n=%d  mediana=%s  max=%s"
      % (len(al_card), sorted(al_card)[len(al_card) // 2] if al_card else "-",
         max(al_card) if al_card else "-"))
print("credito de TODO lo procesado         : n=%d  mediana=%s"
      % (len(todo), sorted(todo)[len(todo) // 2] if todo else "-"))
print()
print("Si la mediana de 'llego a tarjeta' >> la de 'todo', el credito alto SI")
print("predice y la proyeccion de la cola (mediana $12,000) es pesima.")
print("Con lo medido no alcanza para cambiar nada: se sigue acumulando.")
conn.close()