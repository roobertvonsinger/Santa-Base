"""TABLA OFICIAL DE VALORES. Este fue el bug de todos los intentos previos:

  MAL   '0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ'  -> le faltan O y P (36 chars)
  BIEN  digitos 0-9 = 0..9, A..N = 10..23, Ñ = 24, O..Z = 25..36  (37 chars)

Se prueba la tabla buena contra los 332 CURPs que RENAPO ACEPTO + la externa
ZAPM740918HJCRRR08 (confirmada en vivo: de los 10 digitos, solo el 8 pasa).
Se exige 100% o se descarta.
"""
import sqlite3

# --- TABLA OFICIAL ---
VAL = {}
for i in range(10):
    VAL[str(i)] = i
_n = 10
for ch in "ABCDEFGHIJKLMN":
    VAL[ch] = _n
    _n += 1
VAL["Ñ"] = 24
_n = 25
for ch in "OPQRSTUVWXYZ":
    VAL[ch] = _n
    _n += 1

print("TABLA OFICIAL (len=%d):" % len(VAL))
print("   0..9 -> 0..9 | A=%d M=%d N=%d Ñ=%d O=%d P=%d Z=%d"
      % (VAL['A'], VAL['M'], VAL['N'], VAL['Ñ'], VAL['O'], VAL['P'], VAL['Z']))
print("   P=%d (antes daba -1: la tabla mala lo omitia)" % VAL['P'])
print()

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT curp FROM santander_records WHERE curp IS NOT NULL
             AND LENGTH(TRIM(curp))=18
             AND results NOT LIKE '%RENAPO%' AND results NOT LIKE '%operador%'""")
REAL = [r[0].strip().upper() for r in c.fetchall()]
conn.close()
EXTERNA = "ZAPM740918HJCRRR08"
REAL.append(EXTERNA)
print("ground truth: %d aceptadas por RENAPO (incluye la externa)\n" % len(REAL))

print("CONTROL manual sobre %s (dígito real aceptado = 8):" % EXTERNA)
tot = 0
for i, ch in enumerate(EXTERNA[:16]):
    v = VAL.get(ch, 0)
    p = v * (2 if i % 2 == 0 else 1)
    r = p // 10 + p % 10
    tot += r
    print("   %2d %s = %2d x%d = %3d -> %d" % (i, ch, v, 2 if i % 2 == 0 else 1, p, r))
print("   suma=%d -> %d   (real=8)" % (tot, tot % 10))
print()


def dsum(pre, wfun, reduce_mode):
    s = 0
    for i, ch in enumerate(pre):
        p = VAL.get(ch, 0) * wfun(i)
        if reduce_mode == 'digits':
            s += p // 10 + p % 10
        elif reduce_mode == 'minus10':
            s += p - 10 if p > 9 else p
        elif reduce_mode == 'once_then_9':
            q = p // 10 + p % 10
            s += q - 10 if q > 9 else q
        else:
            s += p
    return s % 10


WF = {
    'x2_par': lambda i: 2 if i % 2 == 0 else 1,
    'x2_impar': lambda i: 1 if i % 2 == 0 else 2,
    'x1': lambda i: 1,
    'x2': lambda i: 2,
}
print("Variantes con la TABLA OFICIAL:")
res = []
for wn, wf in WF.items():
    for rm in ('digits', 'minus10', 'once_then_9', 'raw'):
        ok = sum(1 for k in REAL if dsum(k[:16], wf, rm) == int(k[17]))
        res.append((100.0 * ok / len(REAL), wn, rm, ok))
res.sort(reverse=True)
for pct, wn, rm, ok in res:
    print("   %6.2f%%  %-9s %-12s %d/%d" % (pct, wn, rm, ok, len(REAL)))

print("\nAplicando a las 6 primeras CURPs aceptadas con la mejor variante:")
best = res[0]
wf = WF[best[1]]
for k in REAL[:6]:
    print("   %s  calculado=%d  real=%d  %s"
          % (k, dsum(k[:16], wf, best[2]), int(k[17]),
             "OK" if dsum(k[:16], wf, best[2]) == int(k[17]) else "FALLA"))