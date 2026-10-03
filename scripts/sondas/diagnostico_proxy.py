"""Diagnostico del bucle de fallos de proxy que quemo el pool.

Sintoma: el daemon dejo de producir OFF/HIT y solo emite RETRY con
'curl: (56) CONNECT tunnel failed'. En 30+ min no avanzo ni un registro.

Preguntas que responde, cada una con medicion:
  1. Cuantas filas quedaron en results='RETRY...' (pool quemado sin resultado)
  2. Desde cuando falla (primer y ultimo RETRY del log)
  3. El proxy responde ahora, o sigue muerto
  4. Que se hizo del tramo >= $484k mientras tanto
"""
import os
import re
import socket
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
CRED = ("CAST(REPLACE(REPLACE(COALESCE(u6licrea,'0'),'$',''),',','') "
        "AS INTEGER)")

conn = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
c = conn.cursor()

print("=== 1. DAMO EN EL POOL ===")
# `results LIKE 'RETRY%'` no se puede interpolar con `%`: el % de LIKE choca con
# el formateo de la cadena. Se pasa como parametro.
c.execute("SELECT COUNT(*) FROM santander_records WHERE results LIKE ?",
          ("RETRY%",))
n_retry = c.fetchone()[0]
print("filas con results='RETRY...' : %d" % n_retry)
c.execute("SELECT COUNT(*) FROM santander_records "
          "WHERE results LIKE ? AND %s >= 484000" % CRED, ("RETRY%",))
print("  de las cuales con credito >= $484k : %d" % c.fetchone()[0])

print()
print("=== 2. DESDE CUANDO FALLA ===")
log = "purger_daemon.log"
if os.path.exists(log):
    primero = None
    ultimo = None
    n_ok = 0
    with open(log, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "RETRY]" in line:
                if primero is None:
                    primero = line.strip()[:80]
                ultimo = line.strip()[:80]
            elif "OFF]" in line or "HIT #" in line:
                n_ok += 1
    print("primer RETRY : %s" % (primero or "ninguno"))
    print("ultimo  RETRY: %s" % (ultimo or "ninguno"))
    print("lineas con resultado real (OFF/HIT) en todo el log : %d" % n_ok)
else:
    print("no hay log")

print()
print("=== 3. PROXY VIVO? ===")
# El purger usa un proxy-cliente contra :8888 (ver PROJECTS_MAP / config).
for host, port in (("127.0.0.1", 8888),):
    s = socket.socket()
    s.settimeout(5)
    try:
        s.connect((host, port))
        print("%s:%d  ESCUCHA (el puerto responde)" % (host, port))
    except Exception as e:
        print("%s:%d  SIN RESPUESTA: %s" % (host, port, e))
    finally:
        s.close()

print()
print("=== 4. TRAMO >= $484k ===")
c.execute("""SELECT COUNT(*) FROM santander_records
             WHERE results IS NULL AND curp IS NOT NULL AND %s >= 484000"""
          % CRED)
print("sin procesar : %d" % c.fetchone()[0])
c.execute("SELECT COUNT(*) FROM santander_hits")
print("boveda       : %d" % c.fetchone()[0])
conn.close()