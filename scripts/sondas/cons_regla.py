"""Por que fallan las 4 que RENAPO rechazo con OB-ORQ-05?

Ninguna llego al banco, asi que el error es de CURP. Se comparan las 4
calculadas (OB-ORQ-05) contra las 2 que pasaron (ON) y contra las 332 CURPs
verificadas de la BD, buscando que posicion las separa.

Los nombres fallidos:
  SANCHEZ TEJEDA       -> SATD490608MMNNJRA9    pos13,14,15 = M N N
  PACHECO SANDOVAL     -> PASA620727MCSCNN03    pos13,14,15 = C S N
  HERNANDEZ DIAZ       -> HEDV440323HASRZCA0    pos13,14,15 = A S R
  SOTO RODRIGUEZ       -> SORA580131HSLTDL01    pos13,14,15 = S L T
Y los que pasaron:
  ARRIOLA VILCHIS      -> AIVM590310HDFRLG03    pos13,14,15 = R L G
  ORTIZ MENESES        -> OIMR700114HGRRNG01    pos13,14,15 = R N G

Misma regla pos13/14/15 en ambos grupos (interna de paterno, materno, nombre),
pero los que pasan tienen el RFC con 4 iniciales que SI cuadran con el nombre
(AIVM=ARRIOLA-VILCHIS-MIGUEL, OIMR=ORTIZ-MENESES-ROGELIO) y los que fallan
tienen 4 iniciales que cuadran a medias:
  SATD = SANCHEZ+TEJEDA+?  -> las iniciales S,A,T,D vs S,A,?,D  'T' no es de MARIA
  HEDV = HERNANDEZ+?  -> H,E,D,V: V no es de VICTOR
  SORA = SOTO+RODRIGUEZ+?  -> S,O,R,A
La hipotesis: el error esta en las INICIALES (pos0-3), no en pos13-15, porque
el nombre trae prefijos que el RFC no considera (DE LOURDES, DE LOS ANGELES).
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curp_calc import (_partes, _particulas, cons_interna, _dado_principal,
                       codigo_estado)  # noqa: E402

CASOS = [
    # (curp_calc, nombre, resultado)
    ("AIVM590310HDFRLG03", "MIGUEL ANGEL ARRIOLA VILCHIS", "ON"),
    ("OIMR700114HGRRNG01", "ROGELIO ORTIZ MENESES", "ON"),
    ("TECP810524HPLRVB09", "PABLO TREVINO CUEVAS", "OFF LikeU"),
    ("MEOR640429HMNLRB07", "ROBERTO MELGAREJO ORTIZ", "OFF LikeU"),
    ("SATD490608MMNNJRA9", "MARIA DE LOURDES SANCHEZ TEJEDA", "OFF RENAPO"),
    ("PASA620727MCSCNN03", "MARIA DE LOS ANGELES PACHECO SANDOVAL", "OFF RENAPO"),
    ("HEDV440323HASRZCA0", "VICTOR HERNANDEZ DIAZ", "OFF RENAPO"),
    ("SORA580131HSLTDL01", "ALMA EVANGELINA SOTO RODRIGUEZ", "OFF RENAPO"),
]

print("%-20s %-42s %-16s" % ("CURP", "NOMBRE", "RESULTADO"))
print("-" * 84)
for curp, nom, res in CASOS:
    print("%-20s %-42s %-16s" % (curp, nom, res))
print()

print("DESGLOSE por posicion (que produce mi calculador y de donde lo saca):")
print("-" * 84)
for curp, nom, res in CASOS:
    p = _partes(nom)
    p_crudo = (nom or "").upper().split()
    # RFC real de la BD
    ini = curp[:4]
    paterno = p[-2] if len(p) > 1 else "?"
    materno = p[-1] if len(p) > 0 else "?"
    dado = _dado_principal(nom)
    print("   %s  %s" % (curp, res))
    print("      ini        = %s   <- viene del RFC" % ini)
    print("      partes     = %s" % p)
    print("      crudo      = %s" % p_crudo)
    print("      pos10 sexo = %s" % curp[10])
    print("      pos11-12   = %s" % curp[11:13])
    print("      pos13 int.pat  = %s   <- %s -> %s" % (curp[13], paterno, cons_interna(paterno)))
    print("      pos14 int.mat  = %s   <- %s -> %s" % (curp[14], materno, cons_interna(materno)))
    print("      pos15 int.nom  = %s   <- %s -> %s" % (curp[15], dado, cons_interna(dado)))
    print()

# Comparacion con las 332 verificadas: cuantas veces falla el RFC en iniciales
DB = r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT u6rfc, dmname, curp, results FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp))=18""")
rows = c.fetchall()
conn.close()

print("=" * 84)
print("En las 717 de la BD: cuando el RFC[0:4] NO cuadra con el nombre, que pasa")
print("=" * 84)
n_part = 0
n_doble = 0
for rfc, nom, curp, res in rows:
    real = curp.strip().upper()
    p = _partes(nom)
    if len(p) < 3:
        continue
    crudo = (nom or "").upper().split()
    if len(crudo) != len(p):
        n_part += 1
    if len(p) > 2 and len(set(p[-2][:1] for _ in [1])) == 1:
        n_doble += 1
print("   nombres donde la limpieza cambio el conteo de palabras: %d" % n_part)
print()

# prefijos que NO son iniciales validas del nombre
print("Casos donde RFC[0:4] trae una letra que no es inicial de ninguna palabra:")
n = 0
for rfc, nom, curp, res in rows:
    real = curp.strip().upper()
    p = _partes(nom)
    if len(p) < 3:
        continue
    inis = set(w[0] for w in p)
    letras = set(rfc[:4])
    extra = letras - inis
    if extra and n < 10:
        print("   %-38s rfc=%s real=%s  sobran=%s  palabras=%s"
              % ((nom or "")[:38], rfc[:4], real[:4], extra, p))
        n += 1