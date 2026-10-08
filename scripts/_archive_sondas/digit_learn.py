"""Busqueda del algoritmo real del digito verificador, con ground truth de
331 CURPs que RENAPO ACEPTO (results sin OB-ORQ-05, sin 'descartado por
operador') mas la ZAPM externa confirmada en vivo.

Amplia lo que ya se descarto (digit_wide.py):
  - tabla de valor por letra/digito: 0-9 A-Z, 1-9 A-Z, con/sin Ñ, y Ñ con
    valor propio (0), y Ñ igual a N
  - pesos: constante, alternos 2-1 / 1-2, y "2 hasta el indice 15, 1 en 16"
  - el digito se toma ANTES o DESPUES de la reduccion (mod10 sobre la suma
    cruda vs sobre la suma de digitos de cada producto)
  - offset constante 0-9
  - orden de las posiciones: normal, y reversed
  - el digito tambien puede depender de la fecha o de una suma parcial
"""
import itertools
import sqlite3

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT curp FROM santander_records WHERE curp IS NOT NULL
             AND LENGTH(TRIM(curp))=18
             AND results NOT LIKE '%RENAPO%' AND results NOT LIKE '%operador%'""")
REAL = [r[0].strip().upper() for r in c.fetchall()]
conn.close()
REAL.append("ZAPM740918HJCRRR08")
print("ground truth: %d CURPs aceptadas por RENAPO (+1 externa)\n" % len(REAL))

# ---- catalogos de valor -------------------------------------------------
def tbl(dig, letra0, n_val, n_ques, pos_ques, n_pos_n):
    """dig: valor de '0'; letra0: valor de 'A'; n_val: valor de 'Ñ'."""
    m = {}
    for i in range(10):
        m[str(i)] = dig + i
    letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i, ch in enumerate(letras):
        if ch == "N" and pos_ques:
            m["Ñ"] = n_val if n_val is not None else m.get("N", 0)
        m[ch] = letra0 + i
    if "Ñ" not in m:
        m["Ñ"] = 0
    return m


CATALOGOS = {}
for dig in (0, 1):
    for letra0 in (0, 1, 10):
        for nv in (None, 0, 14):
            CATALOGOS["d%g_l%g_n%s" % (dig, letra0, nv)] = tbl(dig, letra0, nv, 1, True, 15)

# ---- esquemas de peso ---------------------------------------------------
def pesos(kind, n):
    if kind == "c1":
        return [1] * n
    if kind == "c2":
        return [2] * n
    if kind == "alt21":
        return [2 if i % 2 == 0 else 1 for i in range(n)]
    if kind == "alt12":
        return [1 if i % 2 == 0 else 2 for i in range(n)]
    if kind == "alt21_r":
        return [2 if i % 2 == 0 else 1 for i in range(n)][::-1]
    return None


KINDS = ["c1", "c2", "alt21", "alt12", "alt21_r"]


def calc(pre, tab, ws, dsum, mod, off, inv):
    v = [tab.get(ch, 0) * w for ch, w in zip(pre, ws)]
    if dsum:
        v = [x // 10 + x % 10 for x in v]
    s = sum(v)
    if mod == 10:
        r = s % 10
    else:
        r = s % 11
        if r == 10:
            r = 0
    return (r + off) % 10


res = []
for cn, tab in CATALOGOS.items():
    for kind in KINDS:
        ws = pesos(kind, 16)
        for dsum in (False, True):
            for mod in (10, 11):
                for off in range(10):
                    for inv in (False, True):
                        ok = 0
                        for curp in REAL:
                            pre = curp[:16] if not inv else curp[:16][::-1]
                            w = ws if not inv else ws[::-1]
                            if calc(pre, tab, w, dsum, mod, off, inv) == int(curp[17]):
                                ok += 1
                        res.append((100.0 * ok / len(REAL), cn, kind,
                                    "dsum" if dsum else "raw", "mod%d" % mod, off, inv))
res.sort(reverse=True)
print("TOP 15 (azar = 10.0%%):")
for pct, cn, kind, ds, mod, off, inv in res[:15]:
    print("   %5.1f%%  %-12s %-8s %-5s %-5s off=%d rev=%s" % (pct, cn, kind, ds, mod, off, inv))
print("\nProbado: %d combinaciones" % len(res))