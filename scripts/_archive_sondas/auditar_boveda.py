"""Auditoria de la boveda: cada hit debe corresponder a una tarjeta que REALMENTE
llego a password_authenticate_form.

Regla de oro: un registro es HIT solo si sus 16 digitos, al meterlos en el login
web de Santander, hacen aparecer la pantalla de password. Cualquier otra cosa
(error generico, SuperLinea, you_cannot_continue) NO va en la boveda.

Este script no re-descarta: solo REPORTA. Descartar de la boveda es operacion
destructiva y va aparte, con confirmacion.
"""
import os
import re
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
conn = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
c = conn.cursor()

print("ESQUEMA de santander_hits:")
cols = [r[1] for r in c.execute("PRAGMA table_info(santander_hits)")]
print("   " + ", ".join(cols))
print()

c.execute("SELECT COUNT(*) FROM santander_hits")
n = c.fetchone()[0]
print("Registros en la boveda: %d" % n)

sel = [x for x in ("id", "u6acct", "curp", "dmname", "work_status",
                   "card_verified", "checked_at") if x in cols]
c.execute("SELECT %s FROM santander_hits ORDER BY checked_at" % ",".join(sel))
print()
print("  %-9s %-18s %-16s %-38s %s" % ("id", "tarjeta", "curp", "nombre", "work_status"))
print("  " + "-" * 96)
for r in c.fetchall():
    rid, acct, curp, nombre, ws, cv, ts = r
    print("  %-9s %-18s %-16s %-38s %s" % (
        rid, acct or "-", curp or "-", (nombre or "-")[:38], ws))

# Regla de oro: cada id de la boveda debe existir en records con results='HIT'.
print()
c.execute("""SELECT h.id, r.results FROM santander_hits h
             LEFT JOIN santander_records r ON r.id = h.id""")
malos = [(i, res) for i, res in c.fetchall() if res != "HIT"]
if malos:
    print("*** %d hits en la boveda NO tienen results='HIT' en records:" % len(malos))
    for i, res in malos[:20]:
        print("    id=%s  results=%r" % (i, res))
    print("    (estos serian ruido en la boveda segun la regla de oro)")
else:
    print("OK: los %d hits de la boveda tienen results='HIT' en records." % n)
conn.close()