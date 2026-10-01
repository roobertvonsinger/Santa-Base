import sqlite3

c = sqlite3.connect('/opt/kvm4/apps/santander/data/santander.db')

# 1. Total hits y conteo por fecha
hits_today = c.execute("SELECT count(id) FROM santander_hits WHERE checked_at >= '2026-09-30'").fetchone()[0]
total_hits = c.execute("SELECT count(id) FROM santander_hits").fetchone()[0]

print(f"Total HITS en Bóveda: {total_hits}")
print(f"HITS registrados hoy (2026-09-30): {hits_today}")

# 2. Desglose de resultados clasificados
print("\n--- Desglose de todos los resultados guardados en santander_records ---")
for r, cnt in c.execute("SELECT results, count(id) FROM santander_records WHERE results IS NOT NULL GROUP BY results ORDER BY count(id) DESC").fetchall():
    print(f"{cnt:5d} | {r}")

# 3. Clasificaciones nuevas del pipeline HTTP (las que tienen prefijo 'OFF:')
print("\n--- Clasificaciones nuevas del pipeline HTTP ---")
new_http = c.execute("SELECT results, count(id) FROM santander_records WHERE results LIKE 'OFF: %' GROUP BY results ORDER BY count(id) DESC").fetchall()
total_new_http = sum(cnt for _, cnt in new_http)
print(f"Total procesados por HTTP purger: {total_new_http}")
for r, cnt in new_http:
    print(f"{cnt:5d} | {r}")
