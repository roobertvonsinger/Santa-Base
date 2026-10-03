"""Por que 5 de 17 CURPs bien calculadas las rechaza RENAPO con OB-ORQ-05?

La linea base offline dice 96.50% de acierto sobre 714 CURPs reales, pero los
5 rechazos en vivo contradicen eso. Se extrae la fila COMPLETA de cada uno de
la BD (estado, direccion, ciudad, acct) para ver si hay un dato que el calculo
no esta usando, sobre todo la entidad (p11-12) y el nombre.

Los 5 rechazados:
  NUAJ711222HBCNLN08  JUAN MANUEL NUNEZ ALFONSO
  SIAA740304HCGFLR04  ARTURO SIFUENTES ALANIS
  CACC550501MNLMSN05  CONCEPCION CAMACHO CASTRO
  AUAM620717MCGRLR09  MARTHA ALICIA ARGUMEDO ALMANZA
  GULB660929MMNRPL07  BLANCA ORALIA GUERRERO LOPEZ
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import curp_calc as cc  # noqa: E402

DB = os.environ.get("SANTANDER_DB",
                    r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')

FALLOS = [
    ("NUAJ711222HBCNLN08", "JUAN MANUEL NUNEZ ALFONSO"),
    ("SIAA740304HCGFLR04", "ARTURO SIFUENTES ALANIS"),
    ("CACC550501MNLMSN05", "CONCEPCION CAMACHO CASTRO"),
    ("AUAM620717MCGRLR09", "MARTHA ALICIA ARGUMEDO ALMANZA"),
    ("GULB660929MMNRPL07", "BLANCA ORALIA GUERRERO LOPEZ"),
]

conn = sqlite3.connect(DB)
c = conn.cursor()
for curp, nom in FALLOS:
    c.execute("""SELECT id, u6rfc, dmname, u6estado, dmcity, dmzip, dmaddr1, u6acct
                 FROM santander_records WHERE dmname = ? LIMIT 1""", (nom,))
    r = c.fetchone()
    if not r:
        print("NO ENCONTRADO: %s" % nom)
        continue
    id_, rfc, nombre, est, city, cp, addr, acct = r
    p = cc._partes(nombre)
    print("=" * 74)
    print("%s   ->  OB-ORQ-05" % curp)
    print("   id=%s  rfc=%s" % (id_, rfc))
    print("   nombre  = %r" % nombre)
    print("   partes  = %s" % p)
    print("   u6estado= %r  -> codigo = %r" % (est, cc.codigo_estado(est)))
    print("   dmcity  = %r   dmzip = %r" % (city, cp))
    print("   direcc  = %r" % addr)
    print("   acct    = %s" % acct)
    print("   ini RFC = %s   calculated = %s" % (rfc[:4], curp[:4]))
    pat = p[-2] if len(p) > 1 else "?"
    mat = p[-1] if p else "?"
    dado = cc._dado_principal(nombre)
    print("   p13 int.pat (%s) = %s   real=%s" % (pat, cc.cons_interna(pat), curp[13]))
    print("   p14 int.mat (%s) = %s   real=%s" % (mat, cc.cons_interna(mat), curp[14]))
    print("   p15 int.nom (%s) = %s   real=%s" % (dado, cc.cons_interna(dado), curp[15]))
    print("   p10 sexo = %s" % curp[10])
    print("   p16 homoclave = %s" % curp[16])
conn.close()