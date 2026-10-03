"""Mide el embudo completo para saber si el daemon continuo es viable.

Salida medida hasta ahora (120 registros, workers=4):
  RENAPO OB-ORQ-05   67 (56%)
  rechazo bancario   31 (26%)   PE170 x27, PE110 x2, PE1002 x2, PE160, PE020
  LikeU Pro           8 (7%)
  contacto preexistente 6 (5%)
  ELEGIBLES          ~8 (7%)
  -> tarjeta INACTIVE ~7, HIT 1

1 hit en 120 = 0.83%. A ese ritmo, un hit cada ~2 horas de corrida continua.
La pregunta que responde este script: ¿el cuello es RENAPO (no hay datos que
lleguen) o la tarjeta (llegan pero no son clientes activos)?

Se lee el log de la ultima corrida y se desglosa. No inventa: solo cuenta lo
que el purger escribio.
"""
import os
import re
import sys
from collections import Counter

# misma razon que en santander_purger: la consola de Windows es cp1252 y los
# logs traen emoji. Sin esto el propio analisis del embudo truena al imprimir.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

LOG = sys.argv[1] if len(sys.argv) > 1 else "purger_lote.log"
if not os.path.exists(LOG):
    print("no existe el log %s" % LOG)
    sys.exit(1)

txt = open(LOG, encoding="utf-8", errors="replace").read()

motivos = Counter()
hits = []
eleg = 0
for line in txt.splitlines():
    if "[OFF]" in line or "OFF]" in line:
        if "OB-ORQ-05" in line:
            motivos["RENAPO OB-ORQ-05"] += 1
        elif "Rechazo bancario" in line:
            m = re.search(r"\((PE\d+)\)", line)
            motivos["banco %s" % (m.group(1) if m else "?")] += 1
        elif "LikeU Pro" in line:
            motivos["LikeU Pro (derivacion)"] += 1
        elif "Contacto preexistente" in line:
            motivos["contacto preexistente"] += 1
        elif "tarjeta inactiva" in line:
            motivos["TARJETA inactiva"] += 1
        else:
            motivos["otro OFF"] += 1
    if "CARD INACTIVE" in line:
        motivos["TARJETA inactiva"] += 1
    if "CARD ERROR" in line:
        motivos["ERROR tarjeta (no quema lead)"] += 1
    if "HIT #" in line:
        hits.append(line.strip())
        motivos["HIT"] += 1
    if "Elegible" in line:
        eleg += 1

# `re.search` solo devolvia el PRIMER resumen. Al concatenar varios lotes
# (`cat a.log b.log > acum.log`) el encabezado quedaba mintiendo sobre el
# total: mostraba 120 cuando el archivo tenia 270.
# Se itera TODOS los resumenes y se suman.
_rx = re.compile(r"Total procesados: (\d+).*?HITS: (\d+).*?OFF: (\d+)")
_tot = _hit = _off = 0
_sesiones = 0
for m in _rx.finditer(txt):
    _sesiones += 1
    _tot += int(m.group(1))
    _hit += int(m.group(2))
    _off += int(m.group(3))
print("Log: %s" % LOG)
if _sesiones:
    print("Resumenes en el archivo: %d  ->  acumulado de todas las sesiones"
          % _sesiones)
    print("Total procesados: %d | HITS: %d | OFF: %d" % (_tot, _hit, _off))
print()
tot = sum(motivos.values()) or 1
for k, v in motivos.most_common():
    print("  %-34s %4d  %5.1f%%" % (k, v, 100.0 * v / tot))

if hits:
    print()
    print("HITS:")
    for h in hits:
        print("  " + re.sub(r"\s+", " ", h)[:110])

# tasa y proyeccion
mh = motivos.get("HIT", 0)
mp = _tot or tot
if mp:
    print()
    print("Tasa de hit: %d/%d = %.2f%%" % (mh, mp, 100.0 * mh / mp))
    if mh:
        cola = 1472163
        print("Proyeccion lineal a %d CURPs en cola: %d hits"
              % (cola, int(cola * mh / mp)))
        print("OJO: es aritmetica, no una promesa. El pool se ordena por")
        print("credito_desc, no al azar, asi que el rendimiento puede cambiar")
        print("segun se vacie la parte alta. Hay que re-medir cada lote.")