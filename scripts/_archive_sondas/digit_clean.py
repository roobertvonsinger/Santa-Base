"""Ground truth REAL: solo los que pasaron curp/consulta. Excluye:
   - RENAPO rejects (OB-ORQ-05)      -> CURP mal
   - 'descartado por operador'        -> nunca se envio a RENAPO
   Solo los que llegaron a la pantalla bancaria (confirm-contact, derivacion, PE*)
   pasaron RENAPO con un CURP valido."""
import sqlite3
from collections import Counter
DB=r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn=sqlite3.connect(DB);c=conn.cursor()
c.execute("""SELECT curp, results FROM santander_records WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18""")
allrows=[(r[0].strip().upper(),(r[1] or '')) for r in c.fetchall()]
conn.close()

def cat(res):
    r=res.upper()
    if 'RENAPO' in r: return 'RENAPO_REJECT'
    if 'OPERADOR' in r: return 'NUNCA_ENVIADO'
    if not r: return 'SIN_RESULTADO'
    return 'PASO_RENAPO'
g=Counter(cat(r) for _,r in allrows)
print("CLASIFICACION REAL:")
for k,v in g.most_common(): print("   %-18s %d" % (k,v))

REAL=[cu for cu,r in allrows if cat(r)=='PASO_RENAPO']
print("\nground truth limpio: %d CURPs que SI pasaron RENAPO" % len(REAL))

TAB={"A_10_35_ñMQ":"0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ",
     "B_10_35_ñNO":"0123456789ABCDEFGHIJKLMNOPÑQRSTUVWXYZ",
     "C_10_35_sinñ":"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
     "D_1_26_ñMQ" :"123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ0",
     "E_1_26_ñNO" :"123456789ABCDEFGHIJKLMNOPÑQRSTUVWXYZ0",
     "F_1_26_sinñ":"123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ0",
     "G_L_0_ñMQ" :"ÑABCDEFGHIJKLMNOPQRSTUVWXYZ"}
def mk(t): return {ch:i for i,ch in enumerate(t)}

def digit(pre,tab,ws,met,dsum):
    v=[tab.get(ch,0)*w for ch,w in zip(pre,ws)]
    if dsum: v=[x//10+x%10 for x in v]
    s=sum(v)
    if met=='mod10': return s%10
    r=s%11; return 0 if r==10 else r

res=[]
for tn,t in TAB.items():
    tab=mk(t)
    for kind,ws in [('alt_21',[2 if i%2==0 else 1 for i in range(16)]),
                    ('alt_12',[1 if i%2==0 else 2 for i in range(16)]),
                    ('c1',[1]*16),('c2',[2]*16)]:
        for dsum in (False,True):
            for met in ('mod10','mod11'):
                for off in range(10):
                    ok=sum(1 for cu in REAL if str(digit(cu[:16],tab,ws,met,dsum))+''==cu[17] or digit(cu[:16],tab,ws,met,dsum)==int(cu[17]))
                    res.append((100.0*ok/len(REAL),tn,kind,'dsum' if dsum else 'raw',met,off))
res.sort(reverse=True)
print("\nTOP 10 sobre el ground truth limpio:")
for pct,tn,kind,ds,met,off in res[:10]:
    print("   %5.1f%%  %-12s %-6s %-5s %-6s off=%d" % (pct,tn,kind,ds,met,off))
print("\n  (azar puro = 10.0%)")
