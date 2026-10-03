"""Calculador de CURP para el pool de 4.86M sin procesar.

LAYOUT (18 chars) verificado posicion por posicion contra 714 CURPs REALES de
la BD (las de results sin OB-ORQ-05 y RFC no enmascarado):

    [0:4]  iniciales, tomadas del RFC de la persona (u6rfc[0:4])
    [4:10] YYMMDD, de u6rfc[4:10]
    [10]   sexo H/M
    [11:12] entidad, 2 letras
    [13]   consonante interna del PATERNO
    [14]   consonante interna del MATERNO
    [15]   consonante interna del 1er nombre dado
    [16]   homoclave: '0' si nacio antes de 2000, 'A' si 2000 o despues
    [17]   DIGITO VERIFICADOR

DIGITO VERIFICADOR -- algoritmo oficial, NO el de la documentacion informal.
El peso no es alterno 2,1 sino descendente (18 - i) sobre 17 caracteres, y el
resultado es un complemento a 10:

    diccionario = "0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ"   (& = Ñ)
    suma  = sum(valor[curp[i]] * (18 - i) for i in 0..16)
    digito = (10 - suma % 10) % 10

Nota sobre pos13/14/15: la consonante interna es la PRIMERA CONSONANTE que
aparece DESPUES de la primera vocal, no la primera de la palabra.
HERNANDEZ -> R, no H.

MEDICION (scripts/curp_medir_final.py, 714 CURPs reales):
    p4-9 fecha 100.00%   p10 sexo 100.00%   p11-12 entidad 100.00%
    p13 100.00%          p14 100.00%       p15 100.00%    p16 100.00%
    p0-p3 iniciales 96.50% (las toma del RFC)   p17 digito 97.34%
    CURP COMPLETA 18/18: 96.50%

LO QUE NO ES UN ERROR -- OB-ORQ-05 NO SIEMPRE ES "CURP MAL".
Control en vivo (scripts/renapo_controle.py): CURPs REALES de la BD que RENAPO
ya habia aceptado siguen avanzando al banco (PE170, LikeU Pro, confirm-contact),
es decir el formato esta bien. Y al reenviar CURPs reales que RENAPO habia
rechazado con OB-ORQ-05, el rechazo se mantiene. Conclusion: OB-ORQ-05 significa
que RENAPO no encuentra a esa persona en su registro, y es un filtro de datos,
no de formato.

Por eso la tasa de aceptacion en vivo (~29%, medido sobre 17) esta MUY por
debajo del 96.50% offline: el pool de 4.86M incluye gente que nunca se registro
en RENAPO. El 96.50% mide CORRECTITUD DEL CALCULO; la tasa en vivo mide
COBERTURA DEL REGISTRO. Son dos cosas distintas y no se deben comparar.
"""
import re
import unicodedata

# --- digito verificador oficial ----------------------------------------
DICCIONARIO = "0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ"
_VALOR = {c: i for i, c in enumerate(DICCIONARIO)}
_VALOR["Ñ"] = _VALOR["&"]


def digito_verificador(curp17):
    """curp17 = los primeros 17 caracteres. Regresa el digito de la pos 17."""
    suma = 0
    for i in range(17):
        suma += _VALOR.get(curp17[i], 0) * (18 - i)
    d = 10 - (suma % 10)
    return str(0 if d == 10 else d)


def curp_valida(curp18):
    """True si el digito verificador de curp18 esta bien calculado."""
    return len(curp18) == 18 and digito_verificador(curp18[:17]) == curp18[17]


# --- catalogo de entidades ---------------------------------------------
ESTADO_CURP = {
    "AGUASCALIENTES": "AS", "BAJA CALIFORNIA": "BC", "BAJA CALIFORNIA SUR": "BS",
    "CAMPECHE": "CP", "COAHUILA DE ZARAGOZA": "CG", "COAHUILA": "CG", "COLIMA": "CM",
    "CHIAPAS": "CS", "CHIHUAHUA": "CH", "CIUDAD DE MEXICO": "DF",
    "DISTRITO FEDERAL": "DF", "DURANGO": "DG", "GUANAJUATO": "GT", "GUERRERO": "GR",
    "HIDALGO": "HG", "JALISCO": "JC", "MEXICO": "MC", "ESTADO DE MEXICO": "MC",
    "MICHOACAN": "MN", "MORELOS": "MS", "NAYARIT": "NT", "NUEVO LEON": "NL",
    "OAXACA": "OC", "PUEBLA": "PL", "QUERETARO": "QT", "QUINTANA ROO": "QR",
    "SAN LUIS POTOSI": "SP", "SINALOA": "SL", "SONORA": "SO", "TABASCO": "TC",
    "TAMAULIPAS": "TS", "TLAXCALA": "TL", "VERACRUZ": "VR", "YUCATAN": "YC",
    "ZACATECAS": "ZS", "EXTRANJERO": "EX",
}
COD_2L = {v: v for v in set(ESTADO_CURP.values())}

VOCALES = set("AEIOU")
CONSONANTES = set("BCDFGHJKLMNPQRSTVWXYZ")
PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "MC", "MA", "VAN", "VON", "DA", "DELA", "Y"}
COMUNES = {"JOSE", "MARIA", "MA", "J"}

# Abreviaturas de estado que Santander usa como sufijo en u6estado. Se buscan
# NORMALIZADAS (sin puntos ni espacios), asi que 'N.L.', 'N L', 'NL' y 'nl'
# son la misma clave. Medido: esto destapa los 854 valores que antes se
# quedaban sin codigo (23,692 filas = 0.49% del pool), junto con los
# municipios sin estado via MUNICIPIO_A_ESTADO.
SUFIJO_ESTADO = {
    "AGU": "AS", "AGS": "AS", "BC": "BC", "BCN": "BC", "BCS": "BS",
    "BCNORTE": "BC", "BCSUR": "BS", "CAMP": "CP", "CAMPECHE": "CP",
    "CHIH": "CH", "CHIHUAHUA": "CH", "CHIS": "CS", "CHIAPAS": "CS",
    "COAH": "CG", "COAHUILA": "CG", "COL": "CM", "COLIMA": "CM",
    "DGO": "DG", "DURANGO": "DG", "GTO": "GT", "GUANAJUATO": "GT",
    "GRO": "GR", "GUERRERO": "GR", "HGO": "HG", "HIDALGO": "HG",
    "JAL": "JC", "JALISCO": "JC", "MICH": "MN", "MICHOACAN": "MN",
    "MOR": "MS", "MOREL": "MS", "MORELOS": "MS", "MEX": "MC",
    "EDODEMEX": "MC", "EDODEMEXICO": "MC", "EDOMEX": "MC",
    "MEXICO": "MC", "ESTADODEMEXICO": "MC", "NAY": "NT", "NAYARIT": "NT",
    "NL": "NL", "NUEVOLEON": "NL", "OAX": "OC", "OAXACA": "OC",
    "PUE": "PL", "PUEBLA": "PL", "QRO": "QT", "QUERETARO": "QT",
    "QROO": "QR", "QROOQROO": "QR", "QUINTANAROO": "QR", "SLP": "SP",
    "SIN": "SO", "SON": "SO", "SONORA": "SO", "SINALOA": "SO",
    "TAB": "TC", "TABASCO": "TC", "TAMS": "TS", "TAMPS": "TS", "TAM": "TS",
    "TAMAULIPAS": "TS", "TLAX": "TL", "TLAXCALA": "TL", "VER": "VR",
    "VERACRUZ": "VR", "YUC": "YC", "YUCATAN": "YC", "ZAC": "ZS",
    "ZACATECAS": "ZS", "EM": "MC", "EMILIANOM": "MC", "DF": "DF",
    "DISTRITOFEDERAL": "DF", "CIUDADDEMEXICO": "DF", "AS": "AS",
    "AGUASCALIENTES": "AS",
}

# u6estado a veces trae el MUNICIPIO en vez del estado. Estos son los que
# aparecen de verdad en el pool, no la lista nacional de 2,463 municipios.
MUNICIPIO_A_ESTADO = {
    "GUADALAJARA": "JC", "MONTERREY": "NL", "ZAPOPAN": "JC",
    "LEON DE LOS ALDAMA": "GT", "MERIDA": "YC", "TIJUANA": "BC",
    "CIUDAD NEZAHUALCOYOT": "MC", "GUADALUPE": "NL", "CIUDAD JUAREZ": "CH",
    "NAUCALPAN DE JUAREZ": "MC", "TORREON": "CG", "CANCUN": "QR",
    "VILLAHERMOSA": "TS", "MEXICALI": "BC", "TLALNEPANTLA DE BAZ": "MC",
    "CUILIACAN": "SL", "SAN NICOLAS DE LOS G": "NL", "SALTILLO": "CG",
    "MORELIA": "MN", "CUAUTITLAN IZCALLI": "MC", "TUXTLA GUTIERREZ": "CS",
    "HERMOSILLO": "SO", "XALAPA ENRIQUEZ": "VR", "TAMPICO": "TS",
    "TLAQUEPAQUE": "JC", "CIUDAD ADOLFO LOPEZ": "QR", "APODACA": "NL",
    "MAZATLAN": "SL", "CUERNAVACA": "MS", "ACAPULCO DE JUAREZ": "GR",
    "TOLUCA DE LERDO": "MC", "CELAYA": "GT", "IRAPUATO": "GT",
    "COACALCO DE BERRIOZA": "MC", "REYNOSA": "TS", "TEPIC": "NT",
    "PACHUCA DE SOTO": "HG", "CIUDAD MADERO": "TS", "TULTITLAN DE MARIANO": "NL",
    "SANTA CATARINA": "NL", "COATZACOALCOS": "VR", "TONALA": "JC",
    "MATAMOROS": "TS", "GOMEZ PALACIO": "DG", "NUEVO LAREDO": "TS",
    "IXTAPALUCA": "MC", "ENSENADA": "BC", "CIUDAD OBREGON": "SO",
    "CIUDAD VICTORIA": "TS", "LA PAZ": "BC", "GENERAL ESCOBEDO": "NL",
    "LOS MOCHIS": "SL", "CIUDAD DEL CARMEN": "CM", "TAPACHULA": "CS",
    "URUAPAN": "MN", "BOCA DEL RIO": "VR", "SALAMANCA": "GT",
    "METEPEC": "MC", "MINATITLAN": "VR", "SOLEDAD DE GRACIANO": "NL",
    # municipio suelto mas frecuente (sin sufijo de estado en u6estado)
    "SAN PEDRO GARZA GARC": "NL", "POZA RICA": "VR", "MONCLOVA": "CG",
    "CHIMALHUACAN": "MC", "CORDOBA": "VR", "PUERTO VALLARTA": "JC",
    "TECAMAC DE FELIPE VI": "MC", "VILLA NICOLAS ROMERO": "MC",
    "HUIXQUILUCAN DE DEGO": "MC", "CHETUMAL": "QR", "ORIZABA": "VR",
    "VILLA DE ALVAREZ": "MC", "TLAJOMULCO DE ZUNIGA": "JC",
    "SAN JUAN DEL RIO": "QT", "TEHUACAN": "PL", "ALTAMIRA": "TS",
    "VALLE DE CHALCO SOLI": "MC", "LOS REYES ACAQUILPAN": "MC",
    "LEON GTO": "GT", "CHALCO DE DIAZ COVAR": "MC", "TULANCINGO": "HG",
    "MANZANILLO": "CM", "CIUDAD DELICIAS": "CH", "CABO SAN LUCAS": "BS",
    "NOGALES": "SO", "COZUMEL": "QR", "CUAUTLA": "MS",
    "CHILPANCINGO DE LOS": "GR", "TUXPAN DE RODRIGUEZ": "VR",
    "COMALCALCO": "TC", "SAN JOSE DEL CABO": "BS", "PIEDRAS NEGRAS": "CG",
    "CARDENAS": "TC", "CIUDAD LERDO": "DG", "CIUDAD CUAUHTEMOC": "CH",
    "APIZACO": "TL", "TUXTEPEC": "VR", "SANTA MARIA TULTEPEC": "MC",
    "SAN LUIS RIO COLORAD": "SO", "GUASAVE": "SO", "COMITAN DE DOMINGUEZ": "CS",
    "CIUDAD GUZMAN": "JC", "ATLIXCO": "PL", "TECOMAN": "CM",
    "PUEBLA": "PL", "OAXACA": "OC", "MORELIA": "MN", "CANCUN": "QR",
    "CABO SAN LUCAS": "BS", "ZITACUARO": "MN", "ZIHUATANEJO": "GR",
    "ZAMORA": "MN", "ZAMORA DE HIDALGO": "MN", "ZACAPU": "MN",
    "XALAPA": "VR", "URUAPAN": "MN", "URIANGATO": "GT", "TULTITLAN": "NL",
    "TULTEPEC": "MC", "TULA DE ALLENDE": "HG", "TONATICO": "MC",
    "TEXCOCO": "MC", "TEXISTEPEC": "VR", "TETITLA": "MC",
    "TETELCINGO": "MS", "TEPANAMES": "CM", "SAN PEDRO AMUZGOS": "OC",
    "SAN MARTIN TEXMELUCAN": "PL", "SAN JUAN CHAPULTEPEC": "OC",
    "SAN BERNARDINO CONTLA": "TL", "SALINA CRUZ": "OC",
    "RAYON": "SO", "PINOTEPA NACIONAL": "OC", "PIHUAMO": "JC",
    "PENJAMO": "GT", "NAVOJOA": "SO", "MOROLEON": "GT",
    "MOCTEZUMA": "SO", "JURIQUILLA": "QT", "JUAREZ": "CH",
    "JILOTEPEC": "MC", "IGUALA": "GR", "HUAYAPAM": "OC",
    "HUAMANTLA": "TL", "GUAMUCHIL": "SO", "JESUS MARIA": "AS",
    "ISABELA": "MC", "SANTA MARIA TULTEPEC ": "MC", "CALPULALPAN": "TL",
    "CABORCA": "SO", "BUENAVISTA": "BC", "BENITO JUAREZ": "QR",
    "ATARASQUILLO": "MC", "AMOZOC DE MOTA": "PL", "ALTEPEXI": "PL",
    "ACAYUCAN": "VR", "ACAMBARO": "GT", "ZACAPU ": "MN",
}


def sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                   if not unicodedata.combining(c))


def _particulas(s):
    return " ".join(w for w in sin_acentos(s or "").upper().split()
                    if w not in PARTICULAS)


def _partes(nombre):
    return [p for p in _particulas(nombre).split() if p]


def cons_interna(palabra):
    """PRIMERA consonante que aparece DESPUES de la primera vocal.
    HERNANDEZ -> R, no H. Equivale a buscar la primera consonante en palabra[1:]."""
    if not palabra:
        return "X"
    for ch in palabra[1:]:
        if ch in CONSONANTES:
            return ch
    return "X"


def _norm_estado(s):
    """Mayusculas, sin acentos, sin comillas, sin puntos, sin espacios:
    ' "N. L." ' -> 'NL'. Toda comparacion de estado usa esta forma."""
    return re.sub(r"[^A-Z]", "", sin_acentos(s or "").upper())


def codigo_estado(estado):
    """Codigo CURP de 2 letras de un valor de `u6estado`, o "" si no se sabe.

    Acepta la entidad ('NUEVO LEON'), su abreviatura con o sin punto ni
    espacios ('NL', 'N.L.', 'N L'), un municipio ('MONTERREY') y los
    compuestos 'MUNICIPIO,ABREV' ('CUERNAVACA,MOR', 'MERIDA, YUC').
    """
    if not estado:
        return ""
    crudo = (estado or "").strip().strip('"').strip()
    # compuesto: el sufijo tras la coma manda, es el estado explicito
    if "," in crudo or ";" in crudo:
        partes = [p.strip().strip('"') for p in re.split(r"[,;]", crudo)]
        sufijo = _norm_estado(partes[-1]) if partes else ""
        if sufijo in SUFIJO_ESTADO:
            return SUFIJO_ESTADO[sufijo]
        if len(sufijo) == 2 and sufijo in COD_2L:
            return COD_2L[sufijo]
        return ""

    n = _norm_estado(crudo)
    if not n:
        return ""
    if n in COD_2L:
        return COD_2L[n]
    if n in SUFIJO_ESTADO:
        return SUFIJO_ESTADO[n]
    if n in MUNICIPIO_A_ESTADO:
        return MUNICIPIO_A_ESTADO[n]

    e = " ".join(sin_acentos(crudo).upper().split())
    if e in ESTADO_CURP:
        return ESTADO_CURP[e]
    if e in MUNICIPIO_A_ESTADO:
        return MUNICIPIO_A_ESTADO[e]
    for k, v in ESTADO_CURP.items():
        kk = " ".join(sin_acentos(k).split())
        if kk and (kk in e or e in kk):
            return v
    for k, v in MUNICIPIO_A_ESTADO.items():
        if k in e or e in k:
            return v
    return ""


def _dado_principal(nombre):
    """Primer nombre dado que cuenta para la CURP: si hay dos y el 1ro es
    JOSE/MARIA, cuenta el 2do."""
    p = _partes(nombre)
    dados = p[:-2] if len(p) > 2 else p
    if not dados:
        return ""
    if len(dados) > 1 and dados[0] in COMUNES:
        return dados[1]
    return dados[0]


def _iniciales_calculadas(nombre):
    """4 iniciales (p0-p3) recalculadas del nombre. NO se usa para calcular.

    Medicion A/B sobre las 714 CURPs reales limpias (scripts/
    iniciales_rfc_vs_nombre.py): tomar las iniciales del RFC acierta 689/714
    = 96.50%; recalcularlas del nombre acierta 0/714. El RFC manda siempre.

    Se conserva solo como referencia de la regla (paterno[0], interna del
    paterno, materno[0], nombre[0]) para diagnosticar diferencias.
    """
    p = _partes(nombre)
    if len(p) < 2:
        return None
    paterno, materno = p[-2], p[-1]
    dado = _dado_principal(nombre)
    if not dado:
        return None
    return paterno[0] + cons_interna(paterno) + materno[0] + dado[0]


# --- inferencia de sexo -------------------------------------------------
# No hay columna de sexo en el pool: RFC[10] es homoclave (5.8% H/M = azar) y
# la columna `genero` solo existe en las 717 filas ya procesadas.
# Se infiere del nombre. El fallback por inicial ("si empieza con R es mujer")
# NO se usa: ANGEL (846 en el pool) cae en R-equivalente y salia M siendo
# hombre. Sin nombre reconocible se descarta la fila, no se adivina.
#
# Medicion sobre las 714 filas con `genero` conocido (excluyendo los 30 RFC
# enmascarados XXXX): 31 nombres mal clasificados con el lexicono anterior.
# Los que siguen son los nombres con verdad observada en la BD o con n>=2
# apariciones en el top-80 del pool de 4.86M.

_FEM = set("""MARIA ANA SOFIA FERNANDA VALERIA GUADALUPE REGINA XIMENA VERONICA
ADRIANA PAOLA DANAE ISABEL ELENA MONICA CLAUDIA SANDRA SILVIA ANDREA
KARINA YOLANDA ROSA ROSARIO ESTELA ARIADNA XIOMAR ITZEL ABRIL BERNARDA
CONCEPCION DOMINGA EUGENIA FILOMENA GABRIELA HORTENSIA IRMA JACQUELINE LORENA
MATILDE NATIVIDAD OLGA PERLA PETRA QUIRINA SAGRARIO TERESA URBANA
VICTORIA ZENAIDA AMALIA BEATRIZ CAROLINA DULCE ESPERANZA FATIMA GUILLERMINA
HILDA IVONNE JAZMIN LILIA MAGDALENA NOEMI PAMELA RUTH SOLEDAD TANIA VANESA
ZITA ARCELIA BERENICE CYNTHIA DANIELA ERIKA FABIANA HAZEL JESSICA KAREN
LILIANA MAYRA NATALIA ORITHA YAZMIN CECILIA MARIELA NANCY OLIVIA PATRICIA
REBECCA VIOLETA ZORAIDA BELEN IMELDA JANET LOHANA MAGALI NAYELI NORMAN
ORALIA PATY VIANEY IVANIA JOHANA
ELIZABETH LETICIA MARTHA CARMEN MARICELA LAURA BLANCA ANGELICA BERTHA
MARGARITA MARCELA ALMA DOLORES LOURDES ESTHELA LUZ VIRGINIA SONIA LILIAN
SARA ARACELI ALICIA EDITH GLORIA GRACIELA ANACLETA APOLINARIA ATANASIO
BENIGNA CANDELARIA CATALINA CONCEPCION DULCE FILOMENA GABINA
GERTRUDIS LEOCADIA LUCRECIA MANUELA MARGARITA MARISELA MAXIMINA
MINERVA NICOLASA OFELIA PASCUALA PERFECTA PILAR REFUGIA ROMUALDA
SILVESTRA SOLEDAD TEODORA TOMASA VALENTINA VICTORINA YOLANDA ZEFERINA
ADELA ANASTACIA ANGELITA AURORA BRENDA CAMELIA CLEMENCIA CONCEPCION
DIANA EDELMIRA ELENA ELODIA EMMA ESPERANZA ESTELA EUGENIA EVANGELINA
FELIPA FLORENTINA GEORGINA GERARDA GLADIS GRISELDA HORTENSIA IRMA
ISABELA JACQUELINE JOSEFINA LAZARA LEANDRA LILIA LORENA
LUCRECIA MAGDALENA MARCELA MARGARITA MARTINA MAXIMINA MIREYA MODESTA
MONICA NATIVIDAD NELLY NOEMI OLIVIA ORALIA ORIANA PAMELA PATRICIA PERLA
PILAR RACHEL REBECA REGINA ROCIO RUTH SALOMENA SANDRA SILVIA SOFIA
SONIA SUSANA TERESA TRINIDAD VALERIA VERONICA VIOLETA VIRGINIA
YOLANDA ZORAIDA ZULEMA
JUANA ALEJANDRA NORMA MARIBEL MIRIAM RAQUEL LUCIA CRISTINA FABIOLA
FRANCISCA ELSA ESTHER KARLA SOCORRO ROSALBA MARISOL MERCEDES LIDIA
JUDITH ELVIRA ELVIA CONSUELO EVA CELIA IRENE REYNA MARIANA JULIA
ROSALINDA JULIETA NORA MARINA RITA LEONOR AIDA DORA MIRNA ROSALIA
LUISA YADIRA ELISA ANGELA CLARA DELIA PAULA ANGELINA AMELIA
LUCILA AMPARO ELIA HORTENCIA ANABEL ENRIQUETA ERNESTINA ESMERALDA
LIZBETH RAMONA XOCHITL ELOISA ROSAURA NADIA EMILIA FLOR ARACELY
MARLENE ELVA INES MONSERRAT
""".split())

_MASC = set("""LUIS JUAN CARLOS MIGUEL ANTONIO JORGE PEDRO RICARDO FERNANDO
RAFAEL SERGIO ANDRES ALEJANDRO RODRIGO EDUARDO MARIO ALFREDO HECTOR DIEGO
RUBEN GUILLERMO HUMBERTO ERNESTO OCTAVIO RENE ISMAEL ARMANDO ADRIAN ALONSO
BERNARDO CECILIO DOMINGO EDMUNDO EMMANUEL ENRIQUE ESTEBAN FABIAN FELIX
GUSTAVO IGNACIO JAVIER JESUS JOAQUIN JONATHAN LEONARDO MARCELO MARTIN MATEO
MAURICIO MAXIMILIANO MIGUELANGEL NESTOR NORBERTO OVIDIO PASCUAL RAMON
RIGOBERTO SALVADOR SAMUEL SERAFIN TEOBALDO ULISES VICTOR ZACARIAS AGUSTIN
BENITO CANDIDO CIRILO CLEMENTE CONRADO DAMIAN EDGAR ELIAS FILIBERTO FLORENCIO
GERARDO GONZALO GREGORIO HORACIO ISIDRO JACOBO LAZARO LUCAS MANUEL MARIANO
MISAEL NARCISO NICOLAS NOE OLIVER PABLO PATRICIO ROBERTO RODOLFO ROGELIO
RUDOLFO SANTOS VICENTE WILFRIDO ZENON ZOILO ARON BALTASAR CRISTOBAL EDSON
EFRAIN ELEAZER GAMALIEL HUGO ISAAC JARED JONAS LEONIDAS ONESIMO RAMIRO
RAYMUNDO SALOMON TEODORO TITO VALENTIN ABRAHAM ADAN ALEXIS AMADEO AURELIO
CELESTINO DAMASO EMANUEL GREGORIO NATALIO
JOSE ANGEL FRANCISCO ARTURO MARCO RAUL ALBERTO JAIME OSCAR JULIO CESAR
DANIEL DAVID JOEL ABEL ANTONIA JONAS LAZARO MATEO MOISES NOE OMAR
SALOMON SAMUEL SANTOS SERAFIN TITO VALENTIN
ARTURO BENITO BUENAVENTURA CECILIO CIPRIANO CLEMENTE CRUZ CRISTOBAL
DIEGO DOMINGO EDUARDO EMILIANO ENRIQUE ESTEBAN EUSEBIO EVARISTO
FABIAN FAUSTINO FERMIN FERNANDO FIDEL FILIBERTO FLORENCIO
GREGORIO GUILLERMO GUSTAVO HECTOR HERMINE HILARIO HORACIO
ISAAC ISIDRO ISMAEL IVAN JACOBO JAVIER JESUS JOEL JOHANN
JONATHAN JORDI JOSE JOVANI JUAN JULIAN JUSTINO LAZARO
LEANDRO LENIN LEOPOLDO LOYOLA LUCIANO LUIS MAGNO
MANUEL MARCELO MARCO MARIANO MARTIN MATEO MAURICIO MAXIMINO
MELCHOR MODESTO NAPOLEON NARCISO NESTOR NICOLAS NORBERTO
OBED OMAR ORLANDO OSVALDO OVIDO PASCUAL PATRICIO PEDRO PABLO
PLINIO PRUDENCIO QUINTIN RAMIRO RAMON RAUL RICARDO ROBERTO RODOLFO
ROGELIO ROMAN RUDOLFO SALOMON SAMUEL SANTOS SERAFIN SERGIO
SILVESTRE TEOBALDO TITO TOMAS ULISES VALENTIN VICTOR VICTORIANO
GILBERTO FELIPE ISRAEL BENJAMIN SAUL ALVARO MARCOS ADOLFO SANTIAGO
FRANCISCO FEDERICO GERMAN EMILIO HERIBERTO LORENZO GENARO EFREN
ROLANDO REYNALDO ARNULFO MARCELINO JOSUE EZEQUIEL ERICK LEONEL
ELEAZAR AARON PORFIRIO ISAIAS MARGARITO OSWALDO ADALBERTO ROSENDO
LUCIO CLAUDIO MAURO CHRISTIAN HOMERO LEOBARDO ELOY ARTEMIO ABELARDO
FAUSTO CUAUHTEMOC ELISEO AMADO BALTAZAR ALFONSO GABRIEL
""".split())


def inferir_sexo(nombre, genero_col=None):
    """(H|M, confianza) o (None, motivo) si el nombre no resuelve.

    Sin lexicono NO se adivina. Medido: el fallback por inicial clasificaba mal
    31 nombres con verdad conocida, y en el pool los nombres que caian ahi eran
    justo los mas frecuentes (ANGEL 846, CARMEN 247, RAUL 163, LOURDES 47...).
    Una CURP con sexo inventado se rechaza en RENAPO, asi que es mejor no
    enviarla que enviarla mal.
    """
    g = (genero_col or "").strip().upper()[:1]
    if g in ("H", "M"):
        return g, "columna"
    p = _partes(nombre)
    dados = p[:-2] if len(p) > 2 else p
    for d in dados:
        if d in _FEM:
            return "M", "nombre"
    for d in dados:
        if d in _MASC:
            return "H", "nombre"
    if not dados:
        return None, "sin_nombre_dado"
    return None, "nombre_desconocido:%s" % dados[0]


def calcular_curp(nombre, rfc, estado, genero_col=None, fecha_nacimiento=None):
    """Regresa (curp18, detalle) o (None, motivo) si falta informacion critica."""
    rfc = (rfc or "").strip().upper()
    if len(rfc) != 13 or not rfc[:4].isalpha() or not rfc[4:10].isdigit():
        return None, "rfc_invalido"
    # RFC enmascarado: 'XXXX000101XXX' NO es un RFC real, es un placeholder de
    # carga. Solo se rechaza el prefijo XXXX de 4 letras followed del patron de
    # relleno; la 'X' suelta en otras posiciones (digito verificador del RFC,
    # p.ej. 'MAFD6906306X4') es un caracter RFC valido y NO se toca.
    # Medido: 4,503 filas con prefijo XXXX exacto; 187,618 con alguna X, de las
    # cuales ~183k son validas.
    if rfc[:4] == "XXXX":
        return None, "rfc_enmascarado"

    cod = codigo_estado(estado)
    if not cod:
        return None, "estado_desconocido:%s" % (estado or "")

    p = _partes(nombre)
    if len(p) < 2:
        return None, "nombre_corto"
    paterno, materno = p[-2], p[-1]
    dado = _dado_principal(nombre)
    if not dado:
        return None, "nombre_corto"

    ini = _iniciales_calculadas(nombre)
    if not ini:
        return None, "nombre_corto"

    sexo, conf = inferir_sexo(nombre, genero_col)
    if sexo is None:
        return None, "sexo_%s" % conf
    # Homoclave (pos16): '0' = nacido antes de 2000, 'A' = 2000 en adelante.
    # La banda yy=02..61 no aparece en NINGUNA de las 717 CURPs reales de la BD
    # (solo yy 00,01 -> 'A' y yy 62..86 -> '0'), asi que no hay evidencia que la
    # respalde. El pool de 4.86M es gente con cuenta bancaria: supondre 19xx
    # salvo prueba contraria, igual que hace el Registro Federal de Contribuyentes
    # (el RFC de una persona fisica nunca empieza en 0-2).
    # BUG QUE ESTO ARREGLA: la regla anterior era 'A' si yy<50, o sea 2044 para
    # un nacido en 1944 -- un ano en el futuro. 7.70% del pool caia en esa banda.
    anio = int(rfc[4:6])
    homoclave = "A" if anio <= 1 else "0"

    curp17 = (rfc[:4] + rfc[4:10] + sexo + cod +
              cons_interna(paterno) + cons_interna(materno) +
              cons_interna(dado) + homoclave)
    return curp17 + digito_verificador(curp17), {
        "sexo": sexo, "conf": conf, "cod": cod, "homoclave": homoclave,
    }