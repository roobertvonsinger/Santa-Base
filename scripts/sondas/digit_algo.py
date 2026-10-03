"""
El digito verificador SI importa (probado en vivo contra RENAPO: de 0-9 solo paso
el real). Mi algoritmo anterior estaba mal. Se brute-forcean variantes hasta dar con
la que reproduce las 717 CURPs conocidas.
"""
import sqlite3

TABLAS = {
    "A": "0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ",      # Ñ entre M y Q
    "B": "0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ".replace("MÑQ", "MNÑO"),
    "C": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",      # sin Ñ
    "D": "ABCDEFGHIJKLMNÑOPQRSTUVWXYZ0123456789",      # letras primero, Ñ entre N y O
}


def digito(curp16, tabla, patron, metodo):
    d = {c: i for i, c in enumerate(tabla)}
    suma = 0
    for i, ch in enumerate(curp16):
        v = d.get(ch, 0) * patron(i)
        if metodo == "suma_directa":
            suma += v
        else:                      # suma de digitos del producto (metodo oficial RENAPO)
            suma += (v // 10) + (v % 10)
    return str(suma % 10)


conn = sqlite3.connect(r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
c = conn.cursor()
c.execute("""SELECT curp FROM santander_records
             WHERE curp IS NOT NULL AND LENGTH(TRIM(curp)) = 18""")
rows = [r[0].strip().upper() for r in c.fetchall()]
conn.close()
print("Muestra: %d CURPs, digito verificador real de las primeras: %s"
      % (len(rows), "".join(r[17] for r in rows[:20])))
print()

patrones = {
    "2,1,2,1... (2 en indice par)": lambda i: 2 if i % 2 == 0 else 1,
    "1,2,1,2... (2 en indice impar)": lambda i: 1 if i % 2 == 0 else 2,
}

mejores = []
for nombre_t, tabla in TABLAS.items():
    for nombre_p, patron in patrones.items():
        for metodo in ("suma_directa", "suma_digitos"):
            ok = sum(1 for r in rows
                     if digito(r[:16], tabla, patron, metodo) == r[17])
            pct = 100.0 * ok / len(rows)
            mejores.append((pct, nombre_t, nombre_p, metodo))
            print("tabla %s | peso %-28s | %-13s -> %4d/%d  (%.1f%%)"
                  % (nombre_t, nombre_p, metodo, ok, len(rows), pct))

mejores.sort(reverse=True)
print()
print("MEJOR: %.1f%%  tabla=%s  peso=%s  metodo=%s" % mejores[0])
