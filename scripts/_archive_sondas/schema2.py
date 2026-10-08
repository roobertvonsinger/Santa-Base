"""ESQUEMA COMPLETO + busqueda exhaustiva de la columna de SEXO.
El diagnostico anterior probó que pos10 (H/M) sale siempre 'M' -> el sexo esta
corrupto o ausente, y sin el CURP completo es imposible. Rastreo TODA columna
que pueda servir: nombre, tipo y distribucion, en las 4.86M sin procesar."""
import sqlite3

DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("TABLAS:", [r[0] for r in c.fetchall()])
print()

c.execute("PRAGMA table_info(santander_records)")
cols = c.fetchall()
print("santander_records: %d columnas" % len(cols))
print()
for cid, name, typ, notnull, dflt, pk in cols:
    c.execute("SELECT COUNT(*) FROM santander_records WHERE %s IS NOT NULL AND TRIM(CAST(%s AS TEXT)) != ''" % (name, name))
    n = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT %s) FROM santander_records WHERE %s IS NOT NULL AND TRIM(CAST(%s AS TEXT)) != ''" % (name, name, name))
    d = c.fetchone()[0]
    print("  %-28s %-14s no_null=%-9d distintos=%d" % (name, typ, n, d))
print()

# --- toda columna con pocos distintos y no nula: candidata a SEXO ---
print("=" * 78)
print("CANDIDATAS A COLUMNA DE SEXO (pocos distintos, cobertura alta)")
print("=" * 78)
for cid, name, typ, notnull, dflt, pk in cols:
    c.execute("SELECT COUNT(DISTINCT %s) FROM santander_records WHERE %s IS NOT NULL AND TRIM(CAST(%s AS TEXT)) != ''" % (name, name, name))
    d = c.fetchone()[0]
    if d == 0 or d > 30:
        continue
    c.execute("SELECT COUNT(*) FROM santander_records WHERE %s IS NOT NULL AND TRIM(CAST(%s AS TEXT)) != ''" % (name, name))
    n = c.fetchone()[0]
    if n < 1000:
        continue
    c.execute("SELECT %s, COUNT(*) FROM santander_records WHERE %s IS NOT NULL AND TRIM(CAST(%s AS TEXT)) != '' GROUP BY 1 ORDER BY 2 DESC LIMIT 12" % (name, name, name))
    dist = c.fetchall()
    print("  %-24s (%d no_null, %d distintos)" % (name, n, d))
    print("      %s" % " | ".join("%r=%d" % (k, v) for k, v in dist))
print()

# --- como esta realmente armado el RFC en el pool ---
print("=" * 78)
print("RFC de persona fisica en el pool: estructura real por posicion")
print("=" * 78)
c.execute("""SELECT u6rfc FROM santander_records
             WHERE results IS NULL AND u6rfc IS NOT NULL AND LENGTH(TRIM(u6rfc)) = 13
             LIMIT 40000""")
rfcs = [r[0].strip().upper() for r in c.fetchall()]
for pos in range(13):
    ch = "".join(r[pos] for r in rfcs if len(r) > pos)
    hm = sum(1 for x in ch if x.isdigit())
    print("  RFC[%2d]  digitos=%5d  letras=%5d   ej: %s" % (pos, hm, len(ch) - hm, "".join(sorted(set(ch)))))
print()
print("  RFC[10] en el pool (donde deberia ir H/M):")
from collections import Counter
cc = Counter(r[10] for r in rfcs)
print("     %s" % " ".join("%r:%d" % (k, v) for k, v in cc.most_common(12)))
print("  RFC[11]:")
cc = Counter(r[11] for r in rfcs)
print("     %s" % " ".join("%r:%d" % (k, v) for k, v in cc.most_common(12)))

# RFC[10] deberia ser H/M si el RFC es persona fisica completo
hm10 = cc.get("H", 0) + cc.get("M", 0)
print()
print("  RFC[10] en {H,M}: %d / %d  (%.1f%%)  -> el RFC NO trae el sexo" % (hm10, len(rfcs), 100.0 * hm10 / len(rfcs)))
conn.close()