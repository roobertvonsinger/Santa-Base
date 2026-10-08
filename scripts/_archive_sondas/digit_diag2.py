"""La tabla anterior estaba mal construida (P daba -1). Se re-mide con tablas
correctas, incluida la version SIN Ñ que usan algunos paises y la oficial RENAPO."""
import sqlite3

TABLAS = {
    "A=0-9A-Z  (Ñ entre M y Q)": "0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ",
    "B=0-9A-Z  (Ñ entre N y O)": "0123456789ABCDEFGHIJKLMNOPÑQRSTUVWXYZ",
    "C=0-9A-Z  (sin Ñ)":        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
}


def calc(pre16, tabla, par, metodo):
    d = {ch: i for i, ch in enumerate(tabla)}
    v = [d.get(ch, 0) for ch in pre16]
    if par:
        v = [x * (2 if i % 2 == 0 else 1) for i, x in enumerate(v)]
    else:
        v = [x * (1 if i % 2 == 0 else 2) for i, x in enumerate(v)]
    if metodo == "directa":
        return str(sum(v) % 10)
    if metodo == "digitos":
        return str(sum(x // 10 + x % 10 for x in v) % 10)
    if metodo == "mod11":
        r = sum(v) % 11
        return "0" if r == 10 else str(r)
    r = sum(x // 10 + x % 10 for x in v) % 11
    return "0" if r == 10 else str(r)


# control: el caso que RENAPO acepto
CASO = "ZAPM740918HJCRRR"
print("CONTROL ZAPM740918HJCRRR -> digito real aceptado = 8")
for tn, tabla in TABLAS.items():
    for par in (True, False):
        for metodo in ("directa", "digitos", "mod11", "mod11_digitos"):
            print("   %-28s peso2=%-5s %-13s = %s"
                  % (tn, "par" if par else "impar", metodo, calc(CASO, tabla, par, metodo)))
print()

conn = sqlite3.connect(r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
c = conn.cursor()
c.execute("""SELECT curp FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp)) = 18""")
rows = [r[0].strip().upper() for r in c.fetchall()]
conn.close()

res = []
for tn, tabla in TABLAS.items():
    for par in (True, False):
        for metodo in ("directa", "digitos", "mod11", "mod11_digitos"):
            ok = sum(1 for r in rows if calc(r[:16], tabla, par, metodo) == r[17])
            res.append((100.0 * ok / len(rows), tn, par, metodo))
res.sort(reverse=True)
print("SOBRE LAS %d CURPs conocidas:" % len(rows))
for pct, tn, par, mo in res[:8]:
    print("   %5.1f%%  %-28s peso2=%-5s %s" % (pct, tn, "par" if par else "impar", mo))
