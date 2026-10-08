import sqlite3, collections

conn = sqlite3.connect(r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
c = conn.cursor()
c.execute("SELECT u6rfc, curp, genero, fecha_nacimiento FROM santander_records WHERE curp IS NOT NULL AND TRIM(curp)<>''")
rows = c.fetchall()
conn.close()

tabla = collections.defaultdict(collections.Counter)
for rfc, curp, gen, fn in rows:
    tabla[rfc[10]][gen] += 1
print('[H1] RFC[10] -> sexo declarado:')
for k in sorted(tabla):
    print('   "%s": %s' % (k, dict(tabla[k])))

print()
print('[H2] RFC fecha vs fecha_nacimiento')
ok = 0
tot = 0
for rfc, curp, gen, fn in rows:
    if not fn: continue
    tot += 1
    mm, dd, yy = rfc[6:8], rfc[8:10], rfc[4:6]
    if '%s-%s-%s' % (yy, mm, dd) == fn:
        ok += 1
print('   %d/%d coinciden' % (ok, tot))

print()
print('[H3] RFC[11] == CURP[11]')
ok3 = sum(1 for rfc, curp, gen, fn in rows if rfc[11] == curp[11])
print('   %d/%d' % (ok3, len(rows)))

print()
print('[H4] Casos RFC[:10] != CURP[:10]')
n = 0
for rfc, curp, gen, fn in rows:
    if rfc[:10].upper() != curp[:10].upper():
        n += 1
        if n <= 6:
            print('   RFC=%s  CURP=%s  fecha=%s' % (rfc, curp, fn))
print('   total discordantes: %d' % n)