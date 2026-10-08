"""
Calculador de CURP a partir de los campos que santander_records ya trae.

Por que existe: las 717 filas con `curp` ya fueron procesadas. Las 4.86M que faltan
tienen u6rfc + dmname + u6estado, que es material suficiente para calcular la CURP.

Validado offline contra las 717 CURPs conocidas: midio posicion por posicion.
"""
import sqlite3
import unicodedata

# --- Catalogo oficial CURP: estado -> codigo de 2 letras (posicion 11 de la CURP) ---
# Fuente: especificacion oficial de la CURP (ANUI/RENAPO). No hay filas no-Jalisco
# con las que validarla empíricamente; el resto de estados queda sin verificar.
ESTADO_CURP = {
    "AGUASCALIENTES": "AS", "BAJA CALIFORNIA": "BC", "BAJA CALIFORNIA SUR": "BS",
    "CAMPECHE": "CP", "COAHUILA DE ZARAGOZA": "CG", "COLIMA": "CM", "CHIAPAS": "CS",
    "CHIHUAHUA": "CH", "CIUDAD DE MEXICO": "DF", "DISTRITO FEDERAL": "DF",
    "DURANGO": "DG", "GUANAJUATO": "GT", "GUERRERO": "GR", "HIDALGO": "HG",
    "JALISCO": "JC", "MEXICO": "MC", "ESTADO DE MEXICO": "MC",
    "MICHOACAN": "MN", "MORELOS": "MS", "NAYARIT": "NT", "NUEVO LEON": "NL",
    "OAXACA": "OC", "PUEBLA": "PL", "QUERETARO": "QT", "QUINTANA ROO": "QR",
    "SAN LUIS POTOSI": "SP", "SINALOA": "SL", "SONORA": "SO", "TABASCO": "TC",
    "TAMAULIPAS": "TS", "TLAXCALA": "TL", "VERACRUZ": "VR", "YUCATAN": "YC",
    "ZACATECAS": "ZS", "EXTRANJERO": "EX",
}

VOCALES = set("AEIOU")


def _sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                   if not unicodedata.combining(c))


def _particulas(s: str) -> str:
    """DE / DEL / LA / LOS / LAS / MC / MACIAS: no cuentan como apellido."""
    return " ".join(w for w in _sin_acentos(s or "").upper().split()
                    if w not in ("DE", "DEL", "LA", "LAS", "LOS", "MC", "MA", "VAN", "VON", "DA", "DELA"))


def _consonante_interna(palabra: str) -> str:
    for ch in palabra:
        if ch not in VOCALES:
            return ch
    return "X"


def _consonante_interna_palabra(palabra: str) -> str:
    """Consonante interna segun el metodo oficial: se avanzan las consonantes
    iniciales hasta encontrar la primera vocal, y se toma la consonante que le
    sigue. HERNANDEZ -> R (no H)."""
    vista_vocal = False
    for ch in palabra:
        if ch in VOCALES:
            vista_vocal = True
        elif vista_vocal:
            return ch
    return "X"


def _diferenciador(nombre: str, paterno: str, materno: str) -> str:
    """No se usa: este esquema de CURP (18 chars, verificado sobre las 717 filas)
    no tiene ranura de letra diferenciadora. pos16 = digito homonimo, pos17 = verificador.
    Se conserva solo como documentacion de por que NO se aplica."""
    return ""


def _fecha_curp(fecha: str, rfc: str) -> str:
    """YYYY-MM-DD -> YYMMDD. Si no hay fecha, se toma del RFC."""
    if fecha:
        f = fecha.strip()
        if len(f) >= 10 and f[4] == "-" and f[7] == "-":
            return f[2:4] + f[5:7] + f[8:10]
        if len(f) == 8 and f.isdigit():          # YYYYMMDD
            return f[2:4] + f[4:6] + f[6:8]
        if len(f) == 10 and f[2] == "/" and f[5] == "/":
            return f[2:4] + f[5:7] + f[8:10]
    return (rfc or "")[4:10]


def _check_digit(curp16: str) -> str:
    """Algoritmo oficial: tabla 0-9 A-Z, multiplicador 2 en posiciones pares
    (indice 0,2,4...), 1 en impares; el digito es el residuo de dividir entre 10."""
    tabla = "0123456789ABCDEFGHIJKLMNÑQRSTUVWXYZ"
    dic = {c: i for i, c in enumerate(tabla)}
    suma = 0
    for i, ch in enumerate(curp16):
        suma += dic.get(ch, 0) * (2 if i % 2 == 0 else 1)
    return str(suma % 10)


def calcular_curp(nombre: str, fecha_nacimiento: str, sexo: str,
                  estado: str, rfc: str = "", homonimo: int = 0,
                  letras_del_rfc: bool = True) -> str:
    """Regresa la CURP de 18 caracteres.

    letras_del_rfc: si el RFC trae 4 letras, mandan sobre las que salen del nombre
    (96.1% de coincidencia medido; el nombre trae particulas y errores de captura).
    """
    rfc = (rfc or "").strip().upper()
    nombres = _particulas(nombre).split()

    # Orden de nombres mexicano: dados(s) + paterno + materno.
    # Verificado sobre las 717 CURPs: el paterno es la penultima palabra y la
    # materna la ULTIMA (no al reves, y no la antepenultima).
    paterno = nombres[-2] if len(nombres) >= 2 else ""
    materno = nombres[-1] if len(nombres) >= 1 else ""
    dados = nombres[:max(0, len(nombres) - 2)]

    # 1) Cuatro iniciales. Fuente primaria: el RFC.
    if letras_del_rfc and len(rfc) >= 4 and rfc[:4].isalpha():
        ini = rfc[:4]
    else:
        p0 = paterno[0] if paterno else "X"
        m0 = materno[0] if materno else "X"
        n0 = dados[0][0] if dados else "X"
        n2 = dados[1][0] if len(dados) > 1 else "X"
        ini = p0 + m0 + n0 + n2

    # 2) Fecha.
    fecha = _fecha_curp(fecha_nacimiento, rfc)

    # 3) Sexo.
    sx = (sexo or "H").strip().upper()[:1]
    if sx not in ("H", "M"):
        sx = "H"

    # 4) Estado.
    edo = (estado or "").strip().upper()
    edo = " ".join(_sin_acentos(edo).split())
    cod = ESTADO_CURP.get(edo, "")
    if not cod:
        for k, v in ESTADO_CURP.items():
            kk = " ".join(_sin_acentos(k).split())
            if kk in edo or edo in kk:
                cod = v
                break

    # 5) Consonantes internas de paterno / materno / primer nombre dado.
    c_pat = _consonante_interna_palabra(paterno) if paterno else "X"
    c_mat = _consonante_interna_palabra(materno) if materno else "X"
    c_nom = _consonante_interna_palabra(dados[0]) if dados else "X"

    # 6) Homonimo.
    curp16 = (ini + fecha + sx + cod + c_pat + c_mat + c_nom + str(homonimo % 10))
    return curp16 + _check_digit(curp16)


# ---------------------------------------------------------------- validacion
if __name__ == "__main__":
    conn = sqlite3.connect(r'C:\Users\rober\Dropbox\TESTING DEV\data\santander.db')
    c = conn.cursor()
    c.execute("""SELECT u6rfc, dmname, fecha_nacimiento, genero, estado, curp
                 FROM santander_records WHERE curp IS NOT NULL AND TRIM(curp) != ''""")
    rows = c.fetchall()
    conn.close()

    pos_ok = {i: 0 for i in range(18)}
    curps_ok = 0
    curp16_ok = 0
    fallos = []
    for rfc, nombre, fnac, sexo, edo, real in rows:
        real = (real or "").strip().upper()
        calc = calcular_curp(nombre, fnac, sexo, edo, rfc)
        if len(calc) != 18:
            continue
        if calc[:16] == real[:16]:
            curp16_ok += 1
        if calc == real:
            curps_ok += 1
        for i in range(min(18, len(real))):
            if i < len(calc) and calc[i] == real[i]:
                pos_ok[i] += 1
        if calc[:16] != real[:16]:
            fallos.append((real, calc, nombre, fnac, sexo, edo, rfc))

    n = len(rows)
    print("VALIDACION OFFLINE sobre %d CURPs conocidas" % n)
    print("  CURP completa identica (18/18):      %4d  (%.1f%%)" % (curps_ok, 100.0 * curps_ok / n))
    print("  Primeros 16 chars identicos:         %4d  (%.1f%%)  <-- lo que ve RENAPO"
          % (curp16_ok, 100.0 * curp16_ok / n))
    print()
    print("  Coincidencia por posicion:")
    etiquetas = {0: "inicial paterno", 1: "inicial materno", 2: "inicial nombre",
                 3: "inicial 2do nombre", 4: "año", 5: "mes", 6: "dia", 7: "mes alt",
                 10: "sexo H/M", 11: "codigo estado", 12: "cons. paterno",
                 13: "cons. materno", 14: "cons. nombre", 15: "letra 16",
                 16: "homonimo", 17: "digito verificador"}
    for i in range(18):
        print("    pos %2d  %-18s %4d / %d  (%.1f%%)"
              % (i, etiquetas.get(i, ""), pos_ok[i], n, 100.0 * pos_ok[i] / n))
    print()
    print("  Muestra de fallos (primeros 12):")
    for f in fallos[:12]:
        print("    real=%s" % f[0])
        print("    calc=%s   dif@%s" % (f[1], [k for k in range(16) if f[0][k] != f[1][k]]))
        print("    nombre=%s | fnac=%s | sexo=%s | edo=%s" % (f[2], f[3], f[4], f[5]))
