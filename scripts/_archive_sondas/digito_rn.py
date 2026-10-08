"""Algoritmo OFICIAL del digito verificador, extraido del codigo de la
calculadora de RENAPO (wp-content/plugins/curp-calculator/assets/curp.js):

    diccionario = "0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ"   (& = Ñ)
    suma  = sum(valor[curp[i]] * (18 - i) for i in 0..16)
    digito = (10 - suma % 10) % 10

OJO: el peso NO es alterno 2,1 -- es descendente (18,17,16...2) sobre 17
caracteres, y el resultado es un complemento a 10, no un mod 10 directo.

Se exige 100% contra los 332 CURPs que RENAPO acepto + la ZAPM externa.
"""
import sqlite3

DICC = "0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ"
VAL = {c: i for i, c in enumerate(DICC)}
VAL["Ñ"] = VAL["&"]


def digito_oficial(curp17):
    suma = 0
    for i in range(17):
        v = VAL.get(curp17[i], 0)
        suma += v * (18 - i)
    d = 10 - (suma % 10)
    if d == 10:
        d = 0
    return str(d)


def verificar(curp18):
    return len(curp18) == 18 and digito_oficial(curp18[:17]) == curp18[17]


DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT curp, results FROM santander_records WHERE curp IS NOT NULL
             AND LENGTH(TRIM(curp))=18""")
ALL = [(r[0].strip().upper(), (r[1] or '')) for r in c.fetchall()]
conn.close()

ACEPT = [cu for cu, r in ALL
         if 'RENAPO' not in r.upper() and 'OPERADOR' not in r.upper()]
RECH = [cu for cu, r in ALL if 'RENAPO' in r.upper()]

print("ALGORITMO OFICIAL (pesos descendentes 18..2, complemento a 10)")
print()
print("CONTROL ZAPM740918HJCRRR08:")
curp = "ZAPM740918HJCRRR08"
tot = 0
for i in range(17):
    v = VAL.get(curp[i], 0)
    p = v * (18 - i)
    tot += p
print("   suma=%d -> %d   (real=%d)" % (tot, 10 - (tot % 10), int(curp[17])))
print("   calculado=%s  real=%s  %s"
      % (digito_oficial(curp[:17]), curp[17],
         "OK" if verificar(curp) else "FALLA"))
print()

ok_a = sum(1 for cu in ACEPT if verificar(cu))
ok_r = sum(1 for cu in RECH if verificar(cu))
print("ACEPTADAS por RENAPO: %d/%d  (%.2f%%)" % (ok_a, len(ACEPT), 100.0 * ok_a / max(1, len(ACEPT))))
print("RECHAZADAS por RENAPO: %d/%d  (%.2f%%)" % (ok_r, len(RECH), 100.0 * ok_r / max(1, len(RECH))))
print()

print("Primeras 12 ACEPTadas:")
for cu in ACEPT[:12]:
    print("   %s  calc=%s real=%s  %s"
          % (cu, digito_oficial(cu[:17]), cu[17],
             "OK" if verificar(cu) else "FALLA"))
print()
print("Primeras 12 RECHAZADAS:")
for cu in RECH[:12]:
    print("   %s  calc=%s real=%s  %s"
          % (cu, digito_oficial(cu[:17]), cu[17],
             "OK" if verificar(cu) else "FALLA"))