"""Estructura REAL de la CURP: la que RENAPO acepto en vivo fue ZAPM740918HJCRRR08.
   Desglose:
     0-3  ZAPM  iniciales
     4-9  740918 fecha
     10   H    sexo
     11-12 JC   entidad
     13   R    consonante interna paterno   (HERNANDEZ -> R)
     14   R    consonante interna materno   (MARTINEZ  -> R)
     15   R    consonante interna nombre    (RICARDO   -> R)
     16   R    consonante interna 2do nombre (ROBERTO -> R)
     17   8    digito verificador
   Es la estructura oficial de 18 chars: pos16 = consonante interna del SEGUNDO
   nombre, NO un digito homonimo (el homonimo vive en el RFC, no en la CURP).

   Este script mide si las 717 CURPs de la BD siguen ese layout o el equivocado,
   y si el RFC de las 4.86M me da lo que falta (sexo, homonimo).
"""
import sqlite3
from collections import Counter

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()

print("=" * 78)
print("1) Las 717 CURPs de la BD: que hay en cada posicion")
print("=" * 78)
c.execute("""SELECT curp, u6rfc, dmname FROM santander_records
             WHERE curp IS NOT NULL AND TRIM(curp) != '' AND LENGTH(TRIM(curp)) = 18""")
rows = [(r[0].strip().upper(), (r[1] or "").strip().upper(), (r[2] or "").strip()) for r in c.fetchall()]
conn.close()
print("   total = %d" % len(rows))

for pos, etiqueta in [(15, "pos15"), (16, "pos16"), (17, "pos17")]:
    cls = Counter(("DIGITO" if r[pos].isdigit() else "LETRA") for r, _, _ in rows)
    print("   %s  %s   ej: %s" % (pos, etiqueta, " ".join(r[pos] for r, _, _ in rows[:20])))

print()
print("=" * 78)
print("2) RFC vs CURP: el RFC trae justo lo que a la CURP le falta")
print("=" * 78)
# RFC persona fisica (13): LAAA AAAAAAAA S H H  ->  0-3 letras, 4-9 fecha, 10 sexo, 11-12 homoclave
ok_len = sum(1 for _, rfc, _ in rows if len(rfc) == 13)
print("   RFC de 13 chars (persona fisica): %d / %d" % (ok_len, len(rows)))

# RFC[0:10] debe ser identico a CURP[0:10]
same = sum(1 for curp, rfc, _ in rows if len(rfc) == 13 and curp[:10] == rfc[:10])
print("   CURP[0:10] == RFC[0:10] : %d / %d  (%.1f%%)" % (same, len(rows), 100.0 * same / max(1, len(rows))))

same_sexo = sum(1 for curp, rfc, _ in rows if len(rfc) == 13 and curp[10] == rfc[10])
print("   CURP[10]   == RFC[10]   : %d / %d  (%.1f%%)   <-- SEXO desde el RFC" % (same_sexo, len(rows), 100.0 * same_sexo / max(1, len(rows))))

# Homonimo: RFC[11] primer caracter de la homoclave -> digito 0-9
LET_A_NUM = {chr(ord('A') + i): i for i in range(26)}


def homo(ch: str) -> str:
    if ch.isdigit():
        return ch
    return str(LET_A_NUM.get(ch, 0))


h_ok = sum(1 for curp, rfc, _ in rows if len(rfc) == 13 and homo(rfc[11]) == curp[16])
h_ok2 = sum(1 for curp, rfc, _ in rows if len(rfc) == 13 and homo(rfc[11]) == curp[17])
print("   homo(RFC[11]) == CURP[16]: %d / %d  (%.1f%%)" % (h_ok, len(rows), 100.0 * h_ok / max(1, len(rows))))
print("   homo(RFC[11]) == CURP[17]: %d / %d  (%.1f%%)" % (h_ok2, len(rows), 100.0 * h_ok2 / max(1, len(rows))))

print()
print("=" * 78)
print("3) Muestra cruda (nombre | rfc | curp)")
print("=" * 78)
for curp, rfc, nom in rows[:12]:
    print("   %-38s | %-14s | %s" % (nom[:38], rfc, curp))

print()
print("=" * 78)
print("4) Las 4.86M sin curp: que campos traen (persona fisica)")
print("=" * 78)
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND u6rfc IS NOT NULL AND LENGTH(TRIM(u6rfc)) = 13""")
print("   RFC de 13 chars, results IS NULL : %d" % c.fetchone()[0])
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND u6rfc IS NOT NULL AND LENGTH(TRIM(u6rfc)) = 13
               AND dmname IS NOT NULL AND TRIM(dmname) != ''
               AND u6estado IS NOT NULL AND TRIM(u6estado) != ''""")
print("   ... y con dmname + u6estado     : %d" % c.fetchone()[0])
c.execute("""SELECT u6rfc, dmname, u6estado FROM santander_records
             WHERE results IS NULL AND u6rfc IS NOT NULL AND LENGTH(TRIM(u6rfc)) = 13
               AND dmname IS NOT NULL AND TRIM(dmname) != ''
             LIMIT 10""")
for r in c.fetchall():
    print("   %-14s | %-42s | %s" % (r[0], (r[1] or "")[:42], r[2]))
conn.close()