import sqlite3

conn = sqlite3.connect(r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
c = conn.cursor()
c.execute("PRAGMA table_info(santander_records)")
cols = c.fetchall()
print('COLUMNAS DE santander_records (%d):' % len(cols))
for col in cols:
    print('   %-22s %s' % (col[1], col[2]))

print()
print('MUESTRAS DE CADA COLUMNA (1 fila con datos):')
for col in cols:
    name = col[1]
    c.execute('SELECT "%s" FROM santander_records WHERE "%s" IS NOT NULL AND TRIM("%s") != %s LIMIT 1'
              % (name, name, name, "''"))
    r = c.fetchone()
    print('   %-22s -> %s' % (name, (str(r[0])[:60] if r else 'TODAS NULL')))
conn.close()