import sqlite3, collections, re

conn = sqlite3.connect(r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
c = conn.cursor()

# RFC persona fisica: 13 chars, 4 letras + 6 digitos fecha + 3 homoclave
# RFC persona moral: empieza con & o 3 letras
print('[1] FORMA DEL RFC en las 4.89M filas:')
c.execute("""
SELECT
  SUM(CASE WHEN u6rfc LIKE '&%' THEN 1 ELSE 0 END) AS morales_amp,
  SUM(CASE WHEN u6rfc GLOB '[A-Z][A-Z][A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9]*' THEN 1 ELSE 0 END) AS fisicas_13,
  SUM(CASE WHEN u6rfc GLOB '[A-Z][A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9][0-9]*' THEN 1 ELSE 0 END) AS morales_3letras,
  COUNT(*) AS total
FROM santander_records
""")
amp, fis, mor3, tot = c.fetchone()
print('   RFC persona MORAL (&...):      %9d' % amp)
print('   RFC persona FISICA (4 letras): %9d' % fis)
print('   RFC persona MORAL (3 letras):  %9d' % mor3)
print('   TOTAL filas:                   %9d' % tot)

print()
print('[2] De las FISICAS, cuantas siguen SIN procesar (results IS NULL):')
c.execute("""
SELECT COUNT(*) FROM santander_records
WHERE u6rfc GLOB '[A-Z][A-Z][A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9]*'
  AND results IS NULL
""")
print('   %d' % c.fetchone()[0])

print()
print('[3] Estados donde hay FISICAS sin procesar:')
c.execute("""
SELECT estado, COUNT(*) FROM santander_records
WHERE u6rfc GLOB '[A-Z][A-Z][A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9]*'
  AND results IS NULL
GROUP BY estado ORDER BY COUNT(*) DESC LIMIT 15
""")
for r in c.fetchall():
    print('   %9d  %s' % (r[1], r[0]))

conn.close()