"""¿De donde sale el SEXO? El registro real (id 1833332) tiene genero='H'.
La unica posicion que no puedo calcular es pos10. Rastreo su origen."""
import sqlite3
DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB); c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tabs=[r[0] for r in c.fetchall()]
print("TABLAS:", tabs)

for t in tabs:
    c.execute("PRAGMA table_info(%s)" % t)
    cols=[r[1] for r in c.fetchall()]
    cand=[x for x in cols if any(k in x.lower() for k in ('sex','gene','gen_','tipo','k','u6dsex'))]
    print("\n%s: %d cols | candidatas a sexo: %s" % (t, len(cols), cand))
    for x in cand:
        try:
            c.execute("SELECT %s, COUNT(*) FROM %s GROUP BY 1 ORDER BY 2 DESC LIMIT 6" % (x,t))
            print("   %s -> %s" % (x, c.fetchall()))
        except Exception as e: print("   %s -> %s" % (x,e))

print("\n"+"="*70)
print("COBERTURA DE genero / fecha_nacimiento / codigo_postal en santander_records")
print("="*70)
for cond,label in [("genero IS NOT NULL AND TRIM(genero)!=''","genero"),
                   ("fecha_nacimiento IS NOT NULL AND TRIM(fecha_nacimiento)!=''","fecha_nac"),
                   ("codigo_postal IS NOT NULL AND TRIM(codigo_postal)!=''","cp")]:
    c.execute("SELECT COUNT(*) FROM santander_records WHERE %s" % cond); tot=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM santander_records WHERE %s AND results IS NULL" % cond); un=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM santander_records WHERE %s AND results IS NOT NULL" % cond); pr=c.fetchone()[0]
    print("   %-10s total=%-8d procesadas=%-6d SIN procesar=%d" % (label, tot, pr, un))

print("\ngenero en las procesadas:")
c.execute("SELECT genero, COUNT(*) FROM santander_records WHERE genero IS NOT NULL AND TRIM(genero)!='' GROUP BY 1 ORDER BY 2 DESC LIMIT 10")
print("  ", c.fetchall())
print("\nresults de las que tienen genero:")
c.execute("""SELECT results, COUNT(*) FROM santander_records
             WHERE genero IS NOT NULL AND TRIM(genero)!='' GROUP BY 1 ORDER BY 2 DESC LIMIT 8""")
for r in c.fetchall(): print("  ", r)
conn.close()
