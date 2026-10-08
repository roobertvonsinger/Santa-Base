"""Diagnostico del digito verificador: calculo explicito para el caso que SI paso
en vivo (ZAPM740918HJCRRR -> digito real 8) y busqueda amplia de variantes."""
import sqlite3

curp = "ZAPM740918HJCRRR08"
pre = curp[:16]
print("Caso que RENAPO ACEPTO: %s  (prefijo=%s, digito real=%s)" % (curp, pre, curp[17]))
print()

TABLA = "0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ"
d = {c: i for i, c in enumerate(TABLA)}
vals = [(ch, d.get(ch, -1)) for ch in pre]
print("valores:", vals)
print("indices con valor -1 (fuera de tabla):",
      [i for i, (ch, v) in enumerate(vals) if v < 0])
print()

print("%-3s %-3s %-6s %-6s %-8s %s" % ("idx", "ch", "valor", "x2", "x1", "dig"))
for i, (ch, v) in enumerate(vals):
    p2 = v * 2 if i % 2 == 0 else v
    p1 = v if i % 2 == 0 else v * 2
    print("%-3d %-3s %-6d %-6d %-8d %d" % (i, ch, v, p2, p1, p2 // 10 + p2 % 10))

s2 = sum(v * (2 if i % 2 == 0 else 1) for i, (ch, v) in enumerate(vals))
s1 = sum(v * (1 if i % 2 == 0 else 2) for i, (ch, v) in enumerate(vals))
print()
print("suma con peso 2 en indice PAR  = %d  -> mod10 = %d" % (s2, s2 % 10))
print("suma con peso 2 en indice IMPAR= %d  -> mod10 = %d" % (s1, s1 % 10))
print("digito REAL aceptado por RENAPO = %s" % curp[17])
print()

# --- busqueda amplia sobre las 717 ---
conn = sqlite3.connect(r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
c = conn.cursor()
c.execute("""SELECT curp FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp)) = 18""")
rows = [r[0].strip().upper() for r in c.fetchall()]
conn.close()

TABLAS = {
    "0-9ABC..(con Ñ entre M y Q)": "0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ",
    "0-9ABC..(sin Ñ)":            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "0-9ABC..(Ñ entre N y O)":    "0123456789ABCDEFGHIJKLMNOÑPQRSTUVWXYZ",
}
MODOS = ("directa", "digitos", "mod11", "mod10_digitos")
MEJORES = []
for tn, tabla in TABLAS.items():
    dd = {ch: i for i, ch in enumerate(tabla)}
    for pn, par in (("par", True), ("impar", False)):
        for modo in MODOS:
            ok = 0
            for r in rows:
                v = [dd.get(ch, 0) for ch in r[:16]]
                if par:
                    v = [x * (2 if i % 2 == 0 else 1) for i, x in enumerate(v)]
                else:
                    v = [x * (1 if i % 2 == 0 else 2) for i, x in enumerate(v)]
                if modo == "directa":
                    res = sum(v) % 10
                elif modo == "digitos":
                    res = sum(x // 10 + x % 10 for x in v) % 10
                elif modo == "mod11":
                    res = sum(v) % 11
                    if res == 10:
                        res = 0
                else:
                    res = sum(x // 10 + x % 10 for x in v) % 11
                    if res == 10:
                        res = 0
                if str(res) == r[17]:
                    ok += 1
            MEJORES.append((100.0 * ok / len(rows), tn, pn, modo))
MEJORES.sort(reverse=True)
print("Top 6 de 18 variantes:")
for pct, tn, pn, mo in MEJORES[:6]:
    print("   %5.1f%%  %-26s peso2=%-6s %s" % (pct, tn, pn, mo))
