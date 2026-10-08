"""Diagnostico: para cada posicion 13/14/15 de la CURP real, QUE palabra de dmname
la produce. Cuenta por indice de palabra (contando desde el final)."""
import sqlite3
import unicodedata
from collections import Counter

VOCALES = set("AEIOU")


def _sa(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))


def cons_interna(p):
    v = False
    for ch in p:
        if ch in VOCALES:
            v = True
        elif v:
            return ch
    return "X"


def cons_primera(p):
    for ch in p:
        if ch not in VOCALES:
            return ch
    return "X"


PARTICULAS = ("DE", "DEL", "LA", "LAS", "LOS", "MC", "MA", "VAN", "VON", "DA", "DELA")

conn = sqlite3.connect(r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
c = conn.cursor()
c.execute("""SELECT dmname, curp FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp)) = 18""")
rows = c.fetchall()
conn.close()

for etiqueta, fn in (("INTERNA (tras 1a vocal)", cons_interna), ("PRIMERA consonante", cons_primera)):
    for pos in (12, 13, 14, 15):
        c1 = Counter()
        c2 = Counter()
        for nombre, curp in rows:
            curp = (curp or "").strip().upper()
            if len(curp) != 18:
                continue
            palabras = [w for w in _sa(nombre).upper().split() if w not in PARTICULAS]
            n = len(palabras)
            vals = [fn(w) for w in palabras]
            objetivo = curp[pos]
            # indice desde el final
            for i, v in enumerate(vals):
                if v == objetivo:
                    c1[i - n] += 1          # -2 = penultima, -1 = ultima, 0 = primera
                    break
            # indice desde el inicio
            for i, v in enumerate(vals):
                if v == objetivo:
                    c2[i] += 1
                    break
        print("%s | pos %2d -> indice DESDE EL FINAL: %s"
              % (etiqueta, pos, c1.most_common(4)))
        print("%s | pos %2d -> indice DESDE EL INICIO: %s"
              % (etiqueta, pos, c2.most_common(4)))
    print()
