import sqlite3

conn = sqlite3.connect(r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
c = conn.cursor()

# El prefijo de 5 digitos del CP mexicano ES la clave de estado (catalogo SEPOMEX/CONEPO)
# 01xxx = Aguascalientes ... 32xxx = Yucatan
# Rango JALISCO = 44xxx-48xxx
print('[1] Muestra de codigos_postal con estado NO NULL:')
c.execute("""SELECT codigo_postal, estado, dmzip FROM santander_records
             WHERE estado IS NOT NULL AND TRIM(estado)!='' LIMIT 8""")
for r in c.fetchall():
    print('   cp=%-8s estado=%-12s dmzip=%s' % (r[0], r[1], r[2]))

print()
print('[2] Pre correlacion CP(5) -> estado en las 717 filas procesadas:')
c.execute("""SELECT codigo_postal, estado FROM santander_records
             WHERE estado IS NOT NULL AND TRIM(estado)!='' AND codigo_postal IS NOT NULL""")
pairs = c.fetchall()
m = {}
for cp, edo in pairs:
    if cp and cp.strip().isdigit() and len(cp.strip()) == 5:
        m.setdefault(cp.strip()[:2], {}).setdefault(edo, 0)
        m[cp.strip()[:2]][edo] += 1
for k in sorted(m)[:15]:
    print('   CP %sxxx -> %s' % (k, m[k]))

print()
print('[3] Cuantas filas tienen codigo_postal utilizable (5 digitos):')
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE codigo_postal IS NOT NULL AND LENGTH(TRIM(codigo_postal))=5
               AND TRIM(codigo_postal) GLOB '[0-9][0-9][0-9][0-9][0-9]'""")
print('   %d' % c.fetchone()[0])

print()
print('[4] De esas, cuantas son persona fisica SIN procesar:')
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE u6rfc GLOB '[A-Z][A-Z][A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9]*'
               AND results IS NULL
               AND codigo_postal IS NOT NULL AND LENGTH(TRIM(codigo_postal))=5
               AND TRIM(codigo_postal) GLOB '[0-9][0-9][0-9][0-9][0-9]'""")
print('   %d' % c.fetchone()[0])

print()
print('[5] Muestra de personas fisicas sin procesar (campos disponibles):')
c.execute("""SELECT id, u6acct, u6rfc, dmname, codigo_postal, ciudad, dmcity, u6estado
             FROM santander_records
             WHERE u6rfc GLOB '[A-Z][A-Z][A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9]*'
               AND results IS NULL LIMIT 6""")
for r in c.fetchall():
    print('   u6acct=%s rfc=%s cp=%s ciudad=%s dmcity=%s u6estado=%s' % (r[1], r[2], r[4], r[5], r[6], r[7]))
    print('       nombre=%s' % r[3])
conn.close()