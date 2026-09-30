import sqlite3

c = sqlite3.connect('/opt/kvm4/apps/santander/data/santander.db')
hits = c.execute('SELECT count(*) FROM santander_hits').fetchone()[0]
res = c.execute('SELECT count(*) FROM santander_records WHERE results IS NOT NULL').fetchone()[0]
total = c.execute('SELECT count(*) FROM santander_records').fetchone()[0]
print(f"TOTAL: {total} | HITS: {hits} | RESULTS: {res}")
latest = c.execute('SELECT id, u6acct, curp, dmname, codigo_postal, telefono, checked_at FROM santander_hits ORDER BY id DESC LIMIT 1').fetchone()
print(f"LATEST HIT: {latest}")

