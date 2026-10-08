"""PRUEBA DE PROVENIENCIA.

Si las 331 CURPs que RENAPO acepto siguen el layout oficial calculado desde
dmname, mi algoritmo del digito debe reproducirlas. No lo hace (6.6%).

Hipotesis: esas CURPs NO se calcularon desde este registro -- vinieron de otra
fuente (CURPs reales traidas de otro lado) y dmname no corresponde al titular
que RENAPO resolvio.

Prediccion falsable: si es cierto, las 331 aceptadas deben empatar PEOR con
dmname que las 244 rechazadas, porque sus consonantes vienen de otro nombre.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import _particulas, cons_interna, digito_verificador  # noqa: E402

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT curp, results, dmname, u6rfc FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp)) = 18""")
rows = [(r[0].strip().upper(), (r[1] or ''), (r[2] or ''), (r[3] or '').strip().upper())
        for r in c.fetchall()]
conn.close()


def cat(res):
    r = res.upper()
    if 'RENAPO' in r:
        return 'RECHAZADA'
    if 'OPERADOR' in r:
        return 'NUNCA_ENVIADA'
    return 'ACEPTADA'


G = {}
for curp, res, nom, rfc in rows:
    G.setdefault(cat(res), []).append((curp, nom, rfc))

print("Coincidencia del layout oficial calculado desde dmname, por grupo:")
print()
print("   grupo            n     RFC[0:10]  pos13   pos14   pos15   digito")
for g, data in sorted(G.items(), key=lambda x: -len(x[1])):
    if g == 'NUNCA_ENVIADA':
        continue
    a = b = d_ = e = f = dg = 0
    for curp, nom, rfc in data:
        w = _particulas(nom).split()
        if len(w) < 3:
            continue
        d_ += 1
        if rfc[:10] == curp[:10]:
            a += 1
        if cons_interna(w[-2]) == curp[13]:
            b += 1
        if cons_interna(w[-1]) == curp[14]:
            e += 1
        if cons_interna(w[0]) == curp[15]:
            f += 1
        if digito_verificador(curp[:16]) == curp[17]:
            dg += 1
    print("   %-14s %4d  %8.1f%%  %5.1f%%  %5.1f%%  %5.1f%%  %5.1f%%"
          % (g, len(data), 100 * a / d_, 100 * b / d_, 100 * e / d_,
             100 * f / d_, 100 * dg / d_))

print()
print("Detalle pos13-15: real vs calculado desde dmname (muestra ACEPTADAS):")
for curp, nom, rfc in G['ACEPTADA'][:16]:
    w = _particulas(nom).split()
    if len(w) < 3:
        continue
    print("   %-40s real=%s  calc=%s%s%s"
          % (nom[:40], curp[13:16], cons_interna(w[-2]),
             cons_interna(w[-1]), cons_interna(w[0])))

print()
print("Curp[0:4] (iniciales) de las ACEPTADAS -- de quien son?")
for curp, nom, rfc in G['ACEPTADA'][:16]:
    w = _particulas(nom).split()
    print("   %-40s curp=%s  rfc=%s" % (nom[:40], curp[:4], rfc[:4]))