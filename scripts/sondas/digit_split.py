"""El estudio anterior mezclo 244 CURPs INVALIDOS (rechazados por RENAPO) con
~472 VALIDOS. Se separa por `results` y se re-mide el algoritmo del digito."""
import sqlite3
from collections import defaultdict
DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn=sqlite3.connect(DB); c=conn.cursor()
c.execute("""SELECT curp, results, genero, u6rfc, dmname, fecha_nacimiento, estado
             FROM santander_records WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18""")
rows=[(r[0].strip().upper(), (r[1] or ''), (r[2] or '').strip(), (r[3] or '').strip().upper(),
       (r[4] or ''), (r[5] or ''), (r[6] or '')) for r in c.fetchall()]
conn.close()

def grupo(res):
    r=res.upper()
    if 'RENAPO' in r or 'OB-ORQ-05' in r: return 'INVALIDO (rechazado RENAPO)'
    if 'operador' in r: return 'descartado por operador'
    return 'VALIDO (paso RENAPO)'
g=defaultdict(list)
for curp,res,gen,rfc,nom,fn,ed in rows: g[grupo(res)].append((curp,res,gen,rfc,nom,fn,ed))
print("GRUPOS:")
for k,v in sorted(g.items(), key=lambda x:-len(x[1])): print("   %-30s %d" % (k,len(v)))

TABLAS={"A":"0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ",
        "B":"0123456789ABCDEFGHIJKLMNOPÑQRSTUVWXYZ",
        "C":"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
def digit(pre,tab,par,met):
    d={ch:i for i,ch in enumerate(tab)}
    v=[d.get(ch,0) for ch in pre]
    v=[x*(2 if i%2==0 else 1) for i,x in enumerate(v)] if par else [x*(1 if i%2==0 else 2) for i,x in enumerate(v)]
    if met=='directa': return str(sum(v)%10)
    if met=='digitos': return str(sum(x//10+x%10 for x in v)%10)
    r=sum(v)%11; return '0' if r==10 else str(r)

print("\nDIGITO VERIFICADOR por grupo y variante:")
best={}
for gname,data in sorted(g.items(), key=lambda x:-len(x[1])):
    print("\n  --- %s (n=%d) ---" % (gname, len(data)))
    res=[]
    for tn,tab in TABLAS.items():
        for par in (True,False):
            for met in ('directa','digitos','mod11'):
                ok=sum(1 for curp,*_ in data if digit(curp[:16],tab,par,met)==curp[17])
                res.append((100.0*ok/max(1,len(data)),tn,'par' if par else 'impar',met))
    res.sort(reverse=True)
    for pct,tn,pn,mo in res[:4]: print("      %5.1f%%  tabla%s peso2=%-5s %s" % (pct,tn,pn,mo))
    best[gname]=res[0]

print("\nSEXO: curp[10] vs genero en la columna")
for gname,data in sorted(g.items(), key=lambda x:-len(x[1])):
    ok=sum(1 for curp,res,gen,*_ in data if gen and curp[10]==gen)
    tot=sum(1 for curp,res,gen,*_ in data if gen)
    from collections import Counter
    dist=Counter(curp[10] for curp,*_ in data)
    print("   %-30s curp[10]=%s | coincide con genero: %d/%d" % (gname, dict(dist), ok, tot))
