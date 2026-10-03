"""Los 25 fallos de la referencia honesta son TODOS de iniciales (p0-3), no de
sexo. Y la regla vigente ("las iniciales se toman del RFC, no del nombre")
esta en duda: EDUARDO BARBA GARCIA DE ALBA tiene verdad GAAE y el RFC da
BAGE. O el RFC de esas filas esta contaminado, o el nombre es mejor fuente.

Se miden las DOS estrategias en las 714, sin escribir codigo nuevo todavia:
  A) rfc[0:4]           -- lo que hace calcular_curp hoy
  B) iniciales del nombre, con el orden de palabras tal cual
  C) iniciales del nombre, ignorando particulas DE/DEL/LA/Y

Ademas: de los 25 fallos, ¿el RFC[0:4] de esas filas coincide con la verdad?
Si NO coincide, el RFC esta mal en esas filas y no hay contradiccion: el
nombre es la fuente correcta ahi.
"""
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import curp_calc as cc  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT u6rfc, dmname, u6estado, curp, genero FROM santander_records
             WHERE curp IS NOT NULL AND TRIM(curp)!=''
               AND genero IS NOT NULL AND TRIM(genero)!=''
               AND UPPER(SUBSTR(u6rfc,1,4))<>'XXXX'
               AND LENGTH(TRIM(u6rfc))=13""")
ref = c.fetchall()
conn.close()

VOCALES = set("AEIOU")


def inicial_nombre(palabra):
    """Primera letra; si es vocal, la siguiente consona."""
    if not palabra:
        return ""
    p = palabra.upper()
    if p[0] not in VOCALES:
        return p[0]
    for ch in p[1:]:
        if ch not in VOCALES:
            return ch
    return ""


def sin_particulas(nombre):
    return " ".join(w for w in re.split(r"\s+", nombre.upper()) if w
                    and w not in ("DE", "DEL", "LA", "LAS", "LOS", "Y", "EL"))


def estrategia_C(nombre):
    """paterno, materno, nombre-dado: sin contar como paterno las particulas."""
    partes = cc._partes(nombre)
    if len(partes) >= 3:
        return partes
    return cc._partes(sin_particulas(nombre))


a_ok = b_ok = c_ok = 0
n = 0
rfc_malo = 0
ej_a = []
for rfc, nom, est, curp_real, gen in ref:
    real = curp_real.strip().upper()
    n += 1
    ini_rfc = rfc[:4]
    p = cc._partes(nom)
    ini_b = "".join(inicial_nombre(x) for x in (p + ["", ""])[:3])[:4].ljust(4)
    pC = estrategia_C(nom)
    ini_c = "".join(inicial_nombre(x) for x in (pC + ["", ""])[:3])[:4].ljust(4)

    if ini_rfc == real[:4]:
        a_ok += 1
    elif len(ej_a) < 12:
        ej_a.append((nom, rfc[:4], real[:4], ini_b, ini_c))
        rfc_malo += 1
    if ini_b == real[:4]:
        b_ok += 1
    if ini_c == real[:4]:
        c_ok += 1

print("Referencias: %d" % n)
print()
print("  A) rfc[0:4]            %4d / %d = %.2f%%" % (a_ok, n, 100.0 * a_ok / n))
print("  B) iniciales del nombre %4d / %d = %.2f%%" % (b_ok, n, 100.0 * b_ok / n))
print("  C) nombre sin particulas %4d / %d = %.2f%%" % (c_ok, n, 100.0 * c_ok / n))
print()
print("Filas donde el RFC NO coincide con la verdad (A falla): %d" % rfc_malo)
print("  %-40s %-6s %-6s %-6s %-6s" % ("nombre", "rfc", "REAL", "B", "C"))
for nom, r, real, b, cc_ in ej_a:
    print("  %-40s %-6s %-6s %-6s %-6s" % (nom[:40], r, real, b, cc_))
print()
print("Aciertos de B donde A falla: %d" % sum(1 for rfc, nom, est, cr, g in ref
                                             if cc._partes(nom) and
                                             "".join(inicial_nombre(x) for x in
                                                     (cc._partes(nom) + ["", ""])[:3])[:4].ljust(4)
                                             == cr.strip().upper()[:4]
                                             and rfc[:4] != cr.strip().upper()[:4]))