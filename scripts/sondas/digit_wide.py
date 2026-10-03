"""473 CURPs CONFIRMADAS por RENAPO = ground truth. Busqueda exhaustiva del
algoritmo del digito verificador sobre ellas."""
import sqlite3, itertools
DB=r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn=sqlite3.connect(DB);c=conn.cursor()
c.execute("""SELECT curp FROM santander_records WHERE curp IS NOT NULL
             AND LENGTH(TRIM(curp))=18 AND (results IS NULL OR results NOT LIKE '%RENAPO%')""")
REAL=[r[0].strip().upper() for r in c.fetchall()]
c.execute("""SELECT curp FROM santander_records WHERE curp IS NOT NULL
             AND LENGTH(TRIM(curp))=18 AND results LIKE '%RENAPO%'""")
BAD=[r[0].strip().upper() for r in c.fetchall()]
conn.close()
print("ground truth: %d aceptadas por RENAPO, %d rechazadas" % (len(REAL),len(BAD)))

# --- catalogos de valor ---
cats={}
cats['A_10_35_ñMQ']="0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ"
cats['B_10_35_ñNO']="0123456789ABCDEFGHIJKLMNOPÑQRSTUVWXYZ"
cats['C_10_35_sinñ']="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
cats['D_1_26_ñMQ'] ="123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ0"   # letra=1..26, digito=0
cats['E_1_26_ñNO'] ="123456789ABCDEFGHIJKLMNOPÑQRSTUVWXYZ0"
cats['F_1_26_sinñ']="123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ0"
cats['G_0_25_ñMQ'] = "0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ"   # letra=0..25 -> reindex
cats['H_AZ_solo']  = "ABCDEFGHIJKLMNÑQRSTUVWXYZ"
cats['I_ñ_solo']   = "ÑABCDEFGHIJKLMNOPQRSTUVWXYZ"

def mk(t): return {ch:i for i,ch in enumerate(t)}
# variante G: reindex sin digitos primero
dG={ch:i for i,ch in enumerate("ABCDEFGHIJKLMNÑQRSTUVWXYZ")}

def weights(n,kind):
    if kind=='const1': return [1]*n
    if kind=='const2': return [2]*n
    if kind=='alt_21': return [2 if i%2==0 else 1 for i in range(n)]
    if kind=='alt_12': return [1 if i%2==0 else 2 for i in range(n)]
    return None

def reduce_sum(s,met):
    if met=='mod10': return str(s%10)
    if met=='dsum_mod10': return str(sum(x//10+x%10 for x in ROW)%10) if False else None
    return None

def calc(pre,tab,ws,met,dsum_first,offset=0):
    vals=[tab.get(ch,0) for ch in pre]
    vals=[v*w for v,w in zip(vals,ws)]
    if dsum_first: vals=[x//10+x%10 for x in vals]
    s=sum(vals)+offset
    if met=='mod10': return s%10
    if met=='mod11': 
        r=s%11; return 0 if r==10 else r
    return None

def render(res):
    return str(res) if res<10 else res

KINDS=['const1','const2','alt_21','alt_12']
best=[]
for cn,t in cats.items():
    tab = dG if cn=='G_0_25_ñMQ' else mk(t)
    for kind in KINDS:
        ws=weights(16,kind)
        for dsum in (False,True):
            for met in ('mod10','mod11'):
                for off in range(0,10):
                    ok=0
                    for curp in REAL:
                        r=calc(curp[:16],tab,ws,met,dsum,off)
                        if r is not None and render(r)==curp[17]: ok+=1
                    best.append((100.0*ok/len(REAL),cn,kind,'dsum' if dsum else 'raw',met,off))
best.sort(reverse=True)
print("\nTOP 12 sobre las %d CURPs reales:" % len(REAL))
for pct,cn,kind,ds,met,off in best[:12]:
    print("   %5.1f%%  %-14s %-7s %-5s %-6s offset=%d" % (pct,cn,kind,ds,met,off))
