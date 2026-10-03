"""Mide la inferencia de sexo contra la columna `genero` (verdad conocida, 717)."""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import inferir_sexo, calcular_curp, _particulas

DB=r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn=sqlite3.connect(DB);c=conn.cursor()
c.execute("""SELECT dmname, genero, u6rfc, estado, curp FROM santander_records
             WHERE genero IS NOT NULL AND TRIM(genero)!=''""")
rows=c.fetchall();conn.close()
print("muestra con sexo conocido: %d" % len(rows))

ok=okcol=okname=okinicial=0
from collections import Counter
errs=[]
for nom,gen,rfc,ed,curp in rows:
    g,conf=inferir_sexo(nom,None)   # SIN columna: solo nombre
    g2,conf2=inferir_sexo(nom,gen)  # CON columna
    if g2==gen: okcol+=1
    if g==gen: ok+=1
    else:
        errs.append((nom,gen,g,conf))
    if conf=='nombre': okname+=1
    if conf=='inicial': okinicial+=1
n=len(rows)
print("  con columna genero   : %d/%d (%.1f%%)" % (okcol,n,100.0*okcol/n))
print("  solo por NOMBRE      : %d/%d (%.1f%%)" % (ok,n,100.0*ok/n))
print("     resueltos por nombre: %d | por inicial: %d" % (okname,okinicial))
print("\n  primeros 15 fallos:")
for e in errs[:15]: print("     %-42s real=%s inf=%s (%s)" % (e[0][:42],e[1],e[2],e[3]))

# Base: cuanto gano por usar la inicial en vez del nombre?
ini_ok=sum(1 for nom,gen,*_ in rows if ("M" if _particulas(nom).split()[0][0] in "R" else "H")==gen)
print("\n  referencia: solo 1a inicial del 1er nombre -> %.1f%%" % (100.0*ini_ok/n))

# Ahora CURP completa sobre las que pasaron RENAPO
c2=sqlite3.connect(DB);k=c2.cursor()
k.execute("""SELECT dmname, genero, u6rfc, estado, curp FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18 AND results NOT LIKE '%RENAPO%'""")
r2=k.fetchall();c2.close()
full=sum(1 for nom,gen,rfc,ed,curp in r2
         if (calcular_curp(nom,rfc,ed,gen) or ("",))[0]==curp)
print("\nCURP 18/18 identica sobre las %d que pasaron RENAPO: %d (%.1f%%)"
      % (len(r2), full, 100.0*full/max(1,len(r2))))
