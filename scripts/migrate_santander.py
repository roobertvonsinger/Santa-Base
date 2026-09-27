#!/usr/bin/env python3
"""
Migración y Cálculo Oficial de CURP para la BD Santander (4,891,788 registros).
Implementa Instructivo Normativo RENAPO vigente (DOF 18/10/2021).
Reglas:
1. CIUDAD, ESTADO, CP parseados de DIRECCIÓN COMPLETA.
2. FECHA_NACIMIENTO extraída de RFC (13 chars persona física) con regla de siglo relativa a hoy (2026-09-27).
3. GÉNERO deducido del nombre (regla JOSE/MARIA + segundo nombre, terminación O=H, A=M, overrides exhaustivos).
4. CURP_STATUS: existente | calculada | no_calculable.
5. CURP_FALTA: sin_fecha | sin_genero | sin_estado | sin_nombre | rfc_invalido.
"""

import sys
import os
import sqlite3
import re
import unicodedata
import datetime
import time

TODAY = datetime.date(2026, 9, 27)

RENAPO_CHARS = '0123456789ABCDEFGHIJKLMNÑOPQRSTUVWXYZ'
_CURP_VOWELS = "AEIOU"
_CURP_CONS = "BCDFGHJKLMNPQRSTVWXYZ"

_CURP_BAD_WORDS = {
    'BACA', 'BAKA', 'BUEI', 'BUEY', 'CACA', 'CACO', 'CAGA', 'CAGO', 'CAKA', 'CAKO',
    'COGE', 'COGI', 'COJA', 'COJE', 'COJI', 'COJO', 'CULO', 'FALO', 'FETO', 'GETA',
    'GUEI', 'GUEY', 'JETA', 'JOTO', 'KACA', 'KACO', 'KAGA', 'KAGO', 'KOGE', 'KOGI',
    'KOJA', 'KOJE', 'KOJI', 'KOJO', 'KULO', 'MAME', 'MAMO', 'MEAR', 'MEAS', 'MEON',
    'MIAR', 'MION', 'MOCO', 'MOKO', 'MULA', 'PEDA', 'PEDO', 'PENE', 'PIPI', 'PITO',
    'POPO', 'PUTA', 'PUTO', 'QULO', 'RATA', 'ROBA', 'ROBE', 'ROBO', 'RUIN', 'SENO',
    'TETA', 'VACA', 'VAGA', 'VAGO', 'VAKA', 'VUEI', 'VUEY', 'WUEI', 'WUEY'
}

CANONICAL_STATES = {
    'AGUASCALIENTES': ('AGUASCALIENTES', 'AS'),
    'AGS': ('AGUASCALIENTES', 'AS'),
    'AS': ('AGUASCALIENTES', 'AS'),
    'BAJA CALIFORNIA': ('BAJA CALIFORNIA', 'BC'),
    'BC': ('BAJA CALIFORNIA', 'BC'),
    'BCN': ('BAJA CALIFORNIA', 'BC'),
    'BAJA CALIFORNIA SUR': ('BAJA CALIFORNIA SUR', 'BS'),
    'BCS': ('BAJA CALIFORNIA SUR', 'BS'),
    'BS': ('BAJA CALIFORNIA SUR', 'BS'),
    'CAMPECHE': ('CAMPECHE', 'CC'),
    'CAMP': ('CAMPECHE', 'CC'),
    'CC': ('CAMPECHE', 'CC'),
    'COAHUILA': ('COAHUILA', 'CL'),
    'COAHUILA DE ZARAGOZA': ('COAHUILA', 'CL'),
    'COAH': ('COAHUILA', 'CL'),
    'CL': ('COAHUILA', 'CL'),
    'COLIMA': ('COLIMA', 'CM'),
    'COL': ('COLIMA', 'CM'),
    'CM': ('COLIMA', 'CM'),
    'CHIAPAS': ('CHIAPAS', 'CS'),
    'CHIS': ('CHIAPAS', 'CS'),
    'CS': ('CHIAPAS', 'CS'),
    'CHIHUAHUA': ('CHIHUAHUA', 'CH'),
    'CHIH': ('CHIHUAHUA', 'CH'),
    'CH': ('CHIHUAHUA', 'CH'),
    'CIUDAD DE MEXICO': ('CIUDAD DE MEXICO', 'DF'),
    'DISTRITO FEDERAL': ('CIUDAD DE MEXICO', 'DF'),
    'CDMX': ('CIUDAD DE MEXICO', 'DF'),
    'DF': ('CIUDAD DE MEXICO', 'DF'),
    'D.F.': ('CIUDAD DE MEXICO', 'DF'),
    'DURANGO': ('DURANGO', 'DG'),
    'DGO': ('DURANGO', 'DG'),
    'DG': ('DURANGO', 'DG'),
    'GUANAJUATO': ('GUANAJUATO', 'GT'),
    'GTO': ('GUANAJUATO', 'GT'),
    'GT': ('GUANAJUATO', 'GT'),
    'GUERRERO': ('GUERRERO', 'GR'),
    'GRO': ('GUERRERO', 'GR'),
    'GR': ('GUERRERO', 'GR'),
    'HIDALGO': ('HIDALGO', 'HG'),
    'HGO': ('HIDALGO', 'HG'),
    'HG': ('HIDALGO', 'HG'),
    'JALISCO': ('JALISCO', 'JC'),
    'JAL': ('JALISCO', 'JC'),
    'JC': ('JALISCO', 'JC'),
    'ESTADO DE MEXICO': ('ESTADO DE MEXICO', 'MC'),
    'EDOMEX': ('ESTADO DE MEXICO', 'MC'),
    'EDO MEX': ('ESTADO DE MEXICO', 'MC'),
    'EDO. MEX.': ('ESTADO DE MEXICO', 'MC'),
    'EDO DE MEXICO': ('ESTADO DE MEXICO', 'MC'),
    'MEXICO': ('ESTADO DE MEXICO', 'MC'),
    'MEX': ('ESTADO DE MEXICO', 'MC'),
    'MC': ('ESTADO DE MEXICO', 'MC'),
    'MICHOACAN': ('MICHOACAN', 'MN'),
    'MICHOACAN DE OCAMPO': ('MICHOACAN', 'MN'),
    'MICH': ('MICHOACAN', 'MN'),
    'MN': ('MICHOACAN', 'MN'),
    'MORELOS': ('MORELOS', 'MS'),
    'MOR': ('MORELOS', 'MS'),
    'MS': ('MORELOS', 'MS'),
    'NAYARIT': ('NAYARIT', 'NT'),
    'NAY': ('NAYARIT', 'NT'),
    'NT': ('NAYARIT', 'NT'),
    'NUEVO LEON': ('NUEVO LEON', 'NL'),
    'N.L.': ('NUEVO LEON', 'NL'),
    'NL': ('NUEVO LEON', 'NL'),
    'OAXACA': ('OAXACA', 'OC'),
    'OAX': ('OAXACA', 'OC'),
    'OC': ('OAXACA', 'OC'),
    'PUEBLA': ('PUEBLA', 'PL'),
    'PUE': ('PUEBLA', 'PL'),
    'PL': ('PUEBLA', 'PL'),
    'QUERETARO': ('QUERETARO', 'QT'),
    'QUERETARO DE ARTEAGA': ('QUERETARO', 'QT'),
    'QRO': ('QUERETARO', 'QT'),
    'QT': ('QUERETARO', 'QT'),
    'QUINTANA ROO': ('QUINTANA ROO', 'QR'),
    'Q ROO': ('QUINTANA ROO', 'QR'),
    'Q. ROO': ('QUINTANA ROO', 'QR'),
    'QROO': ('QUINTANA ROO', 'QR'),
    'QR': ('QUINTANA ROO', 'QR'),
    'SAN LUIS POTOSI': ('SAN LUIS POTOSI', 'SP'),
    'SLP': ('SAN LUIS POTOSI', 'SP'),
    'S.L.P.': ('SAN LUIS POTOSI', 'SP'),
    'SP': ('SAN LUIS POTOSI', 'SP'),
    'SINALOA': ('SINALOA', 'SL'),
    'SIN': ('SINALOA', 'SL'),
    'SL': ('SINALOA', 'SL'),
    'SONORA': ('SONORA', 'SR'),
    'SON': ('SONORA', 'SR'),
    'SR': ('SONORA', 'SR'),
    'TABASCO': ('TABASCO', 'TC'),
    'TAB': ('TABASCO', 'TC'),
    'TC': ('TABASCO', 'TC'),
    'TAMAULIPAS': ('TAMAULIPAS', 'TS'),
    'TAMPS': ('TAMAULIPAS', 'TS'),
    'TAMS': ('TAMAULIPAS', 'TS'),
    'TS': ('TAMAULIPAS', 'TS'),
    'TLAXCALA': ('TLAXCALA', 'TL'),
    'TLAX': ('TLAXCALA', 'TL'),
    'TL': ('TLAXCALA', 'TL'),
    'VERACRUZ': ('VERACRUZ', 'VZ'),
    'VERACRUZ DE IGNACIO DE LA LLAVE': ('VERACRUZ', 'VZ'),
    'VER': ('VERACRUZ', 'VZ'),
    'VZ': ('VERACRUZ', 'VZ'),
    'YUCATAN': ('YUCATAN', 'YN'),
    'YUC': ('YUCATAN', 'YN'),
    'YN': ('YUCATAN', 'YN'),
    'ZACATECAS': ('ZACATECAS', 'ZS'),
    'ZAC': ('ZACATECAS', 'ZS'),
    'ZS': ('ZACATECAS', 'ZS'),
    'EXTRANJERO': ('NACIDO EN EL EXTRANJERO', 'NE'),
    'NACIDO EN EL EXTRANJERO': ('NACIDO EN EL EXTRANJERO', 'NE'),
    'NE': ('NACIDO EN EL EXTRANJERO', 'NE')
}

_CURP_PARTICLES = {'DA', 'DAS', 'DE', 'DEL', 'DER', 'DI', 'DIE', 'DD', 'EL', 'LA', 'LAS', 'LE', 'LES', 'LO', 'LOS', 'MAC', 'MC', 'VAN', 'VON', 'Y'}
_CURP_FIRST_NAME_SKIP = {'JOSE', 'MARIA', 'MA.', 'MA', 'J.', 'J'}

MALE_NAMES = {
    'JOSE', 'JESUS', 'MANUEL', 'MIGUEL', 'ANGEL', 'JAVIER', 'RAFAEL', 'CARLOS',
    'LUIS', 'JORGE', 'RAUL', 'GABRIEL', 'VICTOR', 'CESAR', 'HECTOR', 'DAVID',
    'OSCAR', 'DANIEL', 'SAMUEL', 'RUBEN', 'MARTIN', 'AGUSTIN', 'JOAQUIN',
    'CRISTIAN', 'CRISTOBAL', 'SEBASTIAN', 'ADRIAN', 'JULIAN', 'FABIAN', 'GERMAN',
    'EFRAIN', 'ISMAEL', 'NOE', 'RENE', 'JAIME', 'FELIPE', 'VICENTE', 'ENRIQUE',
    'SALVADOR', 'ABRAHAM', 'ARTURO', 'MOISES', 'ELIAS', 'TOMAS', 'MARCOS',
    'LUCAS', 'ANDRES', 'ALEXIS', 'FELIX', 'ALEX', 'MAX', 'AXEL', 'ALAN',
    'KEVIN', 'BRYAN', 'BRAYAN', 'BRANDON', 'EDGAR', 'OMAR', 'IVAN', 'JONATHAN',
    'CHRISTIAN', 'IAN', 'GAEL', 'LEONEL', 'ABEL', 'URIEL', 'ERICK', 'JAIR',
    'JAHIR', 'SAUL', 'ISAAC', 'JOSHUA', 'LIAM', 'DYLAN', 'DAMIAN', 'MATIAS',
    'NICOLAS', 'MISAEL', 'JOSUE', 'EZEQUIEL', 'ARIEL', 'GILDARDO', 'EDGARDO',
    'LEOPOLDO', 'FERNANDO', 'RICARDO', 'ALEJANDRO', 'ROBERTO', 'EDUARDO',
    'SERGIO', 'FRANCISCO', 'JUAN', 'PEDRO', 'PABLO', 'ANTONIO', 'MARIO',
    'ARMANDO', 'ALBERTO', 'ALFREDO', 'RODOLFO', 'MARCO', 'MAURICIO', 'RAMON',
    'GERARDO', 'GUILLERMO', 'GUSTAVO', 'JACOBO', 'IGNACIO', 'ESTEBAN', 'BERNARDO',
    'ADOLFO', 'ALFONSO', 'ALONSO', 'AMADO', 'ANSELMO', 'APOLINAR', 'ARNULFO',
    'AURELIO', 'BALDOMERO', 'BARTOLOME', 'BENIGNO', 'BENITO', 'BRAULIO', 'CAMILO',
    'CANDIDO', 'CASIMIRO', 'CECILIO', 'CELESTINO', 'CIRILO', 'CLEMENTE', 'CORPUS',
    'CRISPIN', 'CUAUHTEMOC', 'DARIO', 'DELFINO', 'DESIDERIO', 'DIONISIO',
    'DOMINGO', 'DONATO', 'ELEUTERIO', 'ELIGIO', 'ELISEO', 'EMILIANO', 'EMILIO',
    'ENEMESIO', 'EPIFANIO', 'ERASMO', 'ERNESTO', 'ESMERALDO', 'EUGENIO', 'EUSEBIO',
    'EUSTAQUIO', 'EVARISTO', 'EXPEDITO', 'EZEQUIAS', 'FAUSTINO', 'FAUSTO', 'FEDERICO',
    'FIDEL', 'FILEMON', 'FLAVIO', 'FLORENCIO', 'FORTINO', 'FROILAN', 'FULGENCIO',
    'GASPAR', 'GENARO', 'GILBERTO', 'GONZALO', 'GREGORIO', 'GUMERCINDO', 'HERIBERTO',
    'HERLINDO', 'HERMENEGILDO', 'HERMINIO', 'HILARIO', 'HIPOLITO', 'HOMERO', 'HORACIO',
    'HUMBERTO', 'ISIDORO', 'ISIDRO', 'ISRAEL', 'JACINTO', 'JERONIMO', 'JESSIE',
    'JOEL', 'JONAS', 'JUSTINO', 'JUSTO', 'LAZARO', 'LEANDRO', 'LEOBARDO', 'LEONARDO',
    'LEONCIO', 'LINO', 'LORENZO', 'LUCIO', 'MACARIO', 'MARCELINO', 'MARCELO',
    'MARCIANO', 'MARGARITO', 'MAXIMILIANO', 'MAXIMINO', 'MELCHOR', 'MODESTO',
    'NARCISO', 'NATALIO', 'NAZARIO', 'NESTOR', 'NICANOR', 'NORBERTO', 'OCTAVIO',
    'ODILON', 'OLIVERIO', 'ORLANDO', 'OTILIO', 'PATRICIO', 'PLACIDO', 'PORFIRIO',
    'PRISCILIANO', 'PROCORO', 'QUINTIN', 'RAMIRO', 'RAYMUNDO', 'REFUGIO', 'REGINO',
    'REYNALDO', 'RIGOBERTO', 'RODRIGO', 'ROGELIO', 'ROLANDO', 'ROMAN', 'ROMEO',
    'ROMULO', 'ROQUE', 'ROSENDO', 'RUFINO', 'RUPERTO', 'SABINO', 'SALOMON',
    'SANTIAGO', 'SANTOS', 'SATURNINO', 'SAULO', 'SEVERIANO', 'SILVESTRE', 'SIMON',
    'SIXTO', 'TEODORO', 'TEOFILO', 'TIBURCIO', 'TIMOTEO', 'TITO', 'TRINIDAD',
    'URBANO', 'VALENTIN', 'VALERIANO', 'VALERIO', 'VENANCIO', 'WENCESLAO', 'WILFRIDO',
    'XAVIER', 'ZENON', 'AGAPITO', 'ALBARO', 'AMADOR', 'AMBROSIO', 'ANASTACIO',
    'ARISTEO', 'ARNOLDO', 'ASUNCION', 'AUDOMARO', 'BALTAZAR', 'BARTOLO', 'BASILIO',
    'BONIFACIO', 'CALIXTO', 'CARMELO', 'CAYETANO', 'CESAREO', 'CIPRIANO', 'CIRO',
    'CLISERIO', 'CONRADO', 'CONSTANTINO', 'CORNELIO', 'CRESCENCIO', 'CRISOFORO',
    'CRISTINO', 'DAGOBERTO', 'DAMASO', 'DEMETRIO', 'DONACIANO', 'EDMUNDO', 'EFREN',
    'EGIDIO', 'ELPIDIO', 'EMETERIO', 'ENGELBERTO', 'ESTANISLAO', 'ETELBERTO',
    'EUCLIDES', 'EULALIO', 'EUFEMIO', 'EUTIMIO', 'EVERARDO', 'FELICIANO', 'FERMIN',
    'FLORENTINO', 'FORTUNATO', 'FRUMENCIO', 'GABINO', 'GALDINO', 'GAUDENCIO',
    'GASTON', 'LEON', 'GIL', 'HELIODORO', 'HONORIO', 'ILDEFONSO', 'INOCENCIO', 'IRINEO', 'JUVENTINO',
    'LADISLAO', 'LEOCADIO', 'LIBORIO', 'LUDOVICO', 'MACEDONIO', 'MAMERTO', 'MANLIO',
    'MARDONIO', 'MARDOQUEO', 'MAURILIO', 'MAXIMIANO', 'MAYOLO', 'MELITON', 'NEMESIO',
    'NICODEMOS', 'NOEL', 'OCTAVIANO', 'ONESIMO', 'ONOFRE', 'PACIANO', 'PANTALEON',
    'PASCUAL', 'PASTOR', 'PAULINO', 'PETRONILO', 'POMPEYO', 'PRIMITIVO', 'PROSPERO',
    'RADAMES', 'RAMSES', 'RANULFO', 'REVERIANO', 'REY', 'REYES', 'ROBUSTIANO',
    'ROMUALDO', 'ROSALIO', 'RUBICEL', 'RUTILO', 'SABAS', 'SALUSTIO', 'SEGUNDO',
    'SERVANDO', 'SILVERIO', 'SOCRATES', 'TARSICIO', 'TELMO', 'TEMISTOCLES', 'TEODULO',
    'TIRSO', 'TORIBIO', 'ULISES', 'VALENTE', 'VIRGILIO', 'WALDEMAR', 'YAIR', 'ZACARIAS',
    'ZENEN', 'ZEFERINO'
}

FEMALE_NAMES = {
    'MARIA', 'MA', 'MA.', 'CARMEN', 'ANA', 'LUISA', 'SOFIA', 'ISABEL', 'LAURA',
    'PATRICIA', 'ROSA', 'MARTHA', 'ADRIANA', 'ALICIA', 'LETICIA', 'VERONICA',
    'GUADALUPE', 'CLAUDIA', 'SILVIA', 'ELIZABETH', 'GABRIELA', 'MONICA', 'TERESA',
    'BEATRIZ', 'YOLANDA', 'SABRINA', 'DANIELA', 'ANDREA', 'PAOLA', 'FERNANDA',
    'ALEJANDRA', 'VANESSA', 'BRENDA', 'KARLA', 'DIANA', 'JESSICA', 'CYNTHIA',
    'NATALIA', 'VALERIA', 'CAMILA', 'JIMENA', 'REBECA', 'LUZ', 'RAQUEL', 'MARISOL',
    'ROCIO', 'ROSARIO', 'CONCEPCION', 'ASUNCION', 'DOLORES', 'MERCEDES', 'PILAR',
    'CONSUELO', 'SOCORRO', 'AMPARO', 'INES', 'ESTER', 'ESTHER', 'RUTH', 'MIRIAM',
    'MYRIAM', 'ABIGAIL', 'BELEN', 'ITZEL', 'XOCHITL', 'CITLALLI', 'CITLALI',
    'YANET', 'JANET', 'YANETH', 'JANETH', 'LIZBETH', 'LISBETH', 'NAYELI', 'NAYELY',
    'ARACELI', 'ARACELY', 'ARELI', 'ARELY', 'FLOR', 'EDITH', 'JUDITH', 'LILIAN',
    'JACQUELINE', 'JAQUELINE', 'MONSERRAT', 'MONTSERRAT', 'EVELYN', 'EVELIN',
    'ASTRID', 'BERENICE', 'DULCE', 'MARICRUZ', 'YAZMIN', 'JAZMIN', 'AIDEE', 'HAYDEE',
    'NOEMI', 'BELIA', 'CELIA', 'DELIA', 'ELIA', 'IRMA', 'NORMA', 'ALBA', 'BERTHA',
    'BLANCA', 'CATALINA', 'CECILIA', 'ELENA', 'EMMA', 'ESPERANZA', 'ESTELA',
    'EVA', 'GLORIA', 'GRACIELA', 'GUILLERMINA', 'HILDA', 'JOSEFINA', 'JUANA',
    'LILIA', 'LORENA', 'LUCIA', 'MAGDALENA', 'MARGARITA', 'MARISELA', 'OFELIA',
    'OLGA', 'PETRA', 'SARA', 'SUSANA', 'VIRGINIA', 'ANGELICA', 'ANTONIA', 'AURELIA',
    'AURORA', 'CAROLINA', 'CRISTINA', 'ELISA', 'EUGENIA', 'FABIOLA', 'FRANCISCA',
    'GEORGINA', 'HERMELINDA', 'IRENE', 'ISIDRA', 'JACINTA', 'LEONOR', 'LIDIA',
    'LILIANA', 'LUCILA', 'MANUELA', 'MARIBEL', 'MARINA', 'MARITZA', 'MARTA',
    'MATILDE', 'MAYRA', 'MIRNA', 'MYRNA', 'NANCY', 'RAMONA', 'REGINA', 'REYNA',
    'ROSALBA', 'ROSALIA', 'ROSENDA', 'SANDRA', 'SONIA', 'TANIA', 'VICTORIA',
    'WENDY', 'YADIRA', 'YASMIN', 'YENI', 'YENNY', 'YESENIA', 'YESSICA', 'ZORAIDA',
    'ADELA', 'AGUEDA', 'AIDA', 'ALONDRA', 'AMALIA', 'AMELIA', 'ANAHI', 'ANALIDIA',
    'ANITA', 'ANSELMA', 'ARACELIA', 'ARGELIA', 'AZUCENA', 'BETZABE', 'BRIGIDA',
    'CANDELARIA', 'CARITINA', 'CASILDA', 'CLARA', 'CLEMENCIA', 'CLEOTILDE',
    'COLUMBA', 'CORAL', 'CRESCENCIA', 'CRUZ', 'DALILA', 'DOMINGA', 'DORA', 'ELBA',
    'ELEUTERIA', 'ELODIA', 'ELVIRA', 'EMERITA', 'EMILIANA', 'ENEDINA', 'ENGELBERTA',
    'ENRIQUETA', 'EPIFANIA', 'ERNESTINA', 'ETELVINA', 'EUDOXIA', 'EUFEMIA', 'EULALIA',
    'EUSTOLIA', 'EVANGELINA', 'FIDELIA', 'FILOMENA', 'FORTUNATA', 'GABINA', 'GENOVEVA',
    'GREGORIA', 'GUILLERMA', 'GUMERCINDA', 'HERLINDA', 'HERMINIA', 'HILARIA', 'HIPOLITA',
    'HONORIA', 'HORTENCIA', 'IGNACIA', 'ILDEFONSA', 'IMELDA', 'INOCENCIA', 'IRAIS',
    'ISAURA', 'IVONNE', 'JOAQUINA', 'JOSEFA', 'JULIA', 'JULIANA', 'JUSTINA', 'KAREN',
    'KARINA', 'KATIA', 'KATYA', 'LEOCADIA', 'LEONILA', 'LEOPOLDA', 'LIGIA', 'LILA',
    'LINA', 'LORENZA', 'LOURDES', 'LUCINA', 'LUDIVINA', 'LUCRECIA', 'MACARIA', 'MAGALI',
    'MAGALY', 'MAIRA', 'MALENI', 'MARA', 'MARCELA', 'MARCELINA', 'MARIANELA', 'MARICELA',
    'MARIELA', 'MARION', 'MARLENE', 'MARLEN', 'MAURA', 'MAXIMINA', 'MAYELA', 'MELANIA',
    'MELINA', 'MICAELA', 'MINERVA', 'MODESTA', 'NADIA', 'NELIDA', 'NATIVIDAD', 'NIDIA',
    'NIEVES', 'NINFA', 'NORA', 'OCTAVIA', 'OFELIA', 'OLGA', 'OLIVIA', 'PALOMA',
    'PAMELA', 'PASTORA', 'PAULA', 'PAULINA', 'PERLA', 'PIEDAD', 'PRIMITIVA', 'PRISCILA',
    'PURIFICACION', 'REMEDIOS', 'RITA', 'ROBERTA', 'RODOLFA', 'ROMANA', 'ROSALINDA',
    'ROSAURA', 'RUBI', 'RUFINA', 'RUT', 'SABINA', 'SALOME', 'SARAH', 'SATURNINA',
    'SEBASTIANA', 'SECUNDINA', 'SERAFINA', 'SOLEDAD', 'SYLVIA', 'TEODORA', 'TEOFILA',
    'TERESITA', 'TIRSA', 'TOMASA', 'URSULA', 'VALENTINA', 'VENANCIA', 'VIANEY',
    'VILMA', 'VIVIANA', 'XIMENA', 'XIOMARA', 'YAJAIRA', 'YAMILETH', 'YARELI', 'YULIANA',
    'YURIDIA', 'ZAIDA', 'ZAYDA', 'ZENAIDA', 'ZOILA', 'ZULEMA', 'ANGELES', 'ANGELITA'
}

def normalize_text(s: str) -> str:
    if not s: return ""
    s_upper = s.upper()
    res = []
    for ch in s_upper:
        if ch == 'Ñ':
            res.append('X')
        else:
            nfkd = unicodedata.normalize('NFD', ch)
            res.append("".join(c for c in nfkd if unicodedata.category(c) != 'Mn'))
    norm = "".join(res)
    norm = re.sub(r"[^A-Z\s]", " ", norm)
    return re.sub(r"\s+", " ", norm).strip()

def strip_particles(tokens: list[str]) -> str:
    while len(tokens) > 1 and tokens[0] in _CURP_PARTICLES:
        tokens.pop(0)
    return " ".join(tokens)

def split_fullname(fullname: str):
    all_toks = normalize_text(fullname).split()
    if not all_toks:
        return None
    if len(all_toks) == 1:
        return {"nombre": all_toks[0], "ap1": "", "ap2": ""}
    if len(all_toks) == 2:
        return {"nombre": all_toks[0], "ap1": all_toks[1], "ap2": ""}

    i = len(all_toks) - 1
    ap2_end = i
    while i > 0 and all_toks[i - 1] in _CURP_PARTICLES:
        i -= 1
    ap2_tokens = all_toks[i:ap2_end + 1]
    i -= 1

    ap1_end = i
    while i > 0 and all_toks[i - 1] in _CURP_PARTICLES:
        i -= 1
    ap1_tokens = all_toks[i:ap1_end + 1] if i >= 0 else []

    nombre_tokens = all_toks[:i] if i > 0 else []
    # Regla: JOSE o MARIA + segundo nombre -> tomar segundo nombre
    if len(nombre_tokens) > 1 and nombre_tokens[0] in _CURP_FIRST_NAME_SKIP:
        nombre_tokens = nombre_tokens[1:]
    while len(nombre_tokens) > 1 and nombre_tokens[0] in _CURP_PARTICLES:
        nombre_tokens = nombre_tokens[1:]

    return {
        "nombre": nombre_tokens[0] if nombre_tokens else (all_toks[0] if all_toks else ""),
        "ap1": strip_particles(ap1_tokens),
        "ap2": strip_particles(ap2_tokens),
    }

def infer_gender(fullname: str) -> str:
    if not fullname: return ""
    toks = normalize_text(fullname).split()
    if not toks: return ""
    
    first = toks[0]
    target = first
    # Si es JOSE o MARIA y hay segundo nombre, usa el segundo
    if first in ('JOSE', 'MARIA', 'MA', 'J') and len(toks) > 2:
        idx = 1
        while idx < len(toks) - 1 and toks[idx] in _CURP_PARTICLES:
            idx += 1
        if idx < len(toks) - 1:
            target = toks[idx]

    if target in MALE_NAMES:
        return 'H'
    if target in FEMALE_NAMES:
        return 'M'
    if target.endswith('O'):
        return 'H'
    if target.endswith('A'):
        return 'M'
    return ""

def extract_birthdate_from_rfc(rfc: str) -> str:
    if not rfc or len(rfc.strip()) != 13:
        return ""
    rfc = rfc.strip().upper()
    m = re.match(r'^[A-Z&Ñ]{4}(\d{2})(\d{2})(\d{2})[A-Z0-9]{3}$', rfc)
    if not m:
        return ""
    yy_str, mm_str, dd_str = m.groups()
    yy, mm, dd = int(yy_str), int(mm_str), int(dd_str)
    
    cand_year_2000 = 2000 + yy
    cand_year_1900 = 1900 + yy
    
    # Si año de 2 dígitos produce fecha futura respecto a hoy -> 19XX; si no, 20XX
    try:
        cand_date_2000 = datetime.date(cand_year_2000, mm, dd)
        if cand_date_2000 > TODAY:
            final_year = cand_year_1900
        else:
            final_year = cand_year_2000
    except ValueError:
        try:
            datetime.date(cand_year_1900, mm, dd)
            final_year = cand_year_1900
        except ValueError:
            return ""
            
    try:
        valid_date = datetime.date(final_year, mm, dd)
        return valid_date.strftime("%Y-%m-%d")
    except ValueError:
        return ""

def parse_address_fields(a1, a2, muni, city, edo, zip_raw):
    parts = []
    a1_s = (a1 or "").strip()
    a2_s = (a2 or "").strip()
    muni_s = (muni or "").strip()
    city_s = (city or "").strip()
    edo_s = (edo or "").strip()
    cp_s = str(zip_raw or "").strip()

    if a1_s: parts.append(a1_s)
    if a2_s: parts.append(f"COL. {a2_s}")
    if muni_s: parts.append(muni_s)
    if city_s and city_s != muni_s: parts.append(city_s)
    if edo_s: parts.append(edo_s)
    if cp_s: parts.append(f"C.P. {cp_s}")
    
    direccion_completa = ", ".join(parts) if parts else ""
    
    # 1. CP = ultimo bloque de exactamente 5 digitos
    cp_final = ""
    cp_matches = re.findall(r'\b\d{5}\b', direccion_completa)
    if cp_matches:
        cp_final = cp_matches[-1]
    elif re.match(r'^\d{5}$', cp_s):
        cp_final = cp_s
        
    # 2. ESTADO = match contra catalogo de 32 entidades. Normaliza a nombre canonico en mayusculas sin acentos.
    estado_canonico = ""
    estado_code = ""
    norm_edo = normalize_text(edo_s)
    if norm_edo in CANONICAL_STATES:
        estado_canonico, estado_code = CANONICAL_STATES[norm_edo]
    else:
        norm_dir = f" {normalize_text(direccion_completa)} "
        for k, v in CANONICAL_STATES.items():
            if f" {k} " in norm_dir:
                estado_canonico, estado_code = v
                break
                
    # 3. CIUDAD
    ciudad_final = ""
    if city_s:
        ciudad_final = normalize_text(city_s)
    elif muni_s:
        ciudad_final = normalize_text(muni_s)
        
    return ciudad_final, estado_canonico, estado_code, cp_final, direccion_completa

def first_internal_vowel(s: str) -> str:
    if not s: return 'X'
    for ch in s[1:]:
        if ch in _CURP_VOWELS:
            return ch
    return 'X'

def first_internal_consonant(s: str) -> str:
    if not s: return 'X'
    for ch in s[1:]:
        if ch in _CURP_CONS:
            return ch
    return 'X'

def calculate_check_digit(curp17: str) -> str:
    total = sum(RENAPO_CHARS.index(c) * (18 - i) for i, c in enumerate(curp17))
    ver = (10 - (total % 10)) % 10
    return str(ver)

def generarCurp(p1_val: str, p2_val: str, nom_val: str, fecha_nacimiento: str, genero: str, estado_code: str) -> str | None:
    if not p1_val or not nom_val or not fecha_nacimiento or not genero or not estado_code:
        return None
    yyyy, mm, dd = fecha_nacimiento.split('-')
    yy = yyyy[2:]

    c1 = p1_val[0] if p1_val else 'X'
    c2 = first_internal_vowel(p1_val)
    c3 = p2_val[0] if p2_val else 'X'
    c4 = nom_val[0] if nom_val else 'X'

    prefix = c1 + c2 + c3 + c4
    if prefix in _CURP_BAD_WORDS:
        prefix = c1 + 'X' + c3 + c4

    f_str = f"{yy}{mm}{dd}"
    ci1 = first_internal_consonant(p1_val)
    ci2 = first_internal_consonant(p2_val) if p2_val else 'X'
    ci3 = first_internal_consonant(nom_val)

    homo = 'A' if int(yyyy) >= 2000 else '0'
    curp17 = f"{prefix}{f_str}{genero}{estado_code}{ci1}{ci2}{ci3}{homo}"
    c18 = calculate_check_digit(curp17)
    return curp17 + c18

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", type=int, default=0, help="Test limit for rows")
    args = parser.parse_args()

    db_path = "/opt/kvm4/apps/santander/data/santander.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} no existe.")
        return

    print(f"[*] Conectando a {db_path}...")
    conn = sqlite3.connect(db_path, timeout=60.0)
    cur = conn.cursor()
    
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = OFF;")
    conn.execute("PRAGMA cache_size = -128000;")
    conn.execute("PRAGMA temp_store = MEMORY;")

    # Verificar rango de IDs
    cur.execute("SELECT MIN(id), MAX(id), COUNT(*) FROM santander_records")
    min_id, max_id, total_records = cur.fetchone()
    if args.test > 0:
        max_id = min_id + args.test - 1
        total_records = args.test
        print(f"[*] MODO PRUEBA ACTIVO: Procesando {args.test:,} registros (IDs {min_id} a {max_id})")
    else:
        print(f"[*] MODO COMPLETO: {total_records:,} registros (ID min: {min_id}, max: {max_id})")


    batch_size = 50000
    start_id = min_id
    t_start = time.time()
    
    stats = {
        "total": total_records,
        "existente": 0,
        "calculada": 0,
        "no_calculable": 0,
        "motivos": {
            "sin_fecha": 0,
            "sin_genero": 0,
            "sin_estado": 0,
            "sin_nombre": 0,
            "rfc_invalido": 0
        }
    }

    processed = 0

    while start_id <= max_id:
        end_id = min(start_id + batch_size - 1, max_id)
        t_batch_0 = time.time()

        
        cur.execute("""
            SELECT id, u6rfc, curp, dmname, dmaddr1, dmaddr2, u6delomu, u6estado, dmcity, dmzip 
            FROM santander_records 
            WHERE id BETWEEN ? AND ?
        """, (start_id, end_id))
        rows = cur.fetchall()
        
        if not rows:
            start_id = end_id + 1
            continue

        updates = []
        for r in rows:
            rid, rfc, curp_existing, name, a1, a2, muni, edo, city, zip_raw = r
            
            ciudad, estado_canonico, estado_code, cp, _ = parse_address_fields(a1, a2, muni, city, edo, zip_raw)
            f_nac = extract_birthdate_from_rfc(rfc)
            genero = infer_gender(name)
            split = split_fullname(name) if name else None
            
            # CURP logic
            curp_to_save = None
            curp_status = None
            curp_falta = None
            
            if curp_existing and curp_existing.strip():
                curp_status = "existente"
                curp_falta = None
                curp_to_save = curp_existing.strip().upper()
                stats["existente"] += 1
            elif not f_nac:
                curp_status = "no_calculable"
                curp_falta = "sin_fecha"
                stats["no_calculable"] += 1
                stats["motivos"]["sin_fecha"] += 1
            elif not genero:
                curp_status = "no_calculable"
                curp_falta = "sin_genero"
                stats["no_calculable"] += 1
                stats["motivos"]["sin_genero"] += 1
            elif not estado_code:
                curp_status = "no_calculable"
                curp_falta = "sin_estado"
                stats["no_calculable"] += 1
                stats["motivos"]["sin_estado"] += 1
            elif not split or not split["ap1"] or not split["nombre"]:
                curp_status = "no_calculable"
                curp_falta = "sin_nombre"
                stats["no_calculable"] += 1
                stats["motivos"]["sin_nombre"] += 1
            else:
                calc_curp = generarCurp(split["ap1"], split["ap2"], split["nombre"], f_nac, genero, estado_code)
                if calc_curp:
                    curp_status = "calculada"
                    curp_falta = None
                    curp_to_save = calc_curp
                    stats["calculada"] += 1
                else:
                    curp_status = "no_calculable"
                    curp_falta = "rfc_invalido"
                    stats["no_calculable"] += 1
                    stats["motivos"]["rfc_invalido"] += 1
                    
            updates.append((
                ciudad if ciudad else None,
                estado_canonico if estado_canonico else None,
                cp if cp else None,
                f_nac if f_nac else None,
                genero if genero else None,
                curp_status,
                curp_falta,
                curp_to_save,
                rid
            ))

        # Executemany update
        cur.executemany("""
            UPDATE santander_records 
            SET ciudad = ?, estado = ?, codigo_postal = ?, fecha_nacimiento = ?, genero = ?, curp_status = ?, curp_falta = ?,
                curp = CASE WHEN (curp IS NULL OR curp = '') THEN ? ELSE curp END
            WHERE id = ?
        """, updates)
        conn.commit()

        processed += len(rows)
        batch_dur = time.time() - t_batch_0
        total_dur = time.time() - t_start
        rate = processed / total_dur if total_dur > 0 else 0
        pct = (processed / total_records) * 100
        eta = (total_records - processed) / rate if rate > 0 else 0
        
        print(f"[{pct:5.1f}%] IDs {start_id}-{end_id} ({len(rows):,} filas en {batch_dur:.2f}s) | Total: {processed:,}/{total_records:,} | {rate:.0f} f/s | ETA: {eta/60:.1f}m", flush=True)
        
        start_id = end_id + 1

    print("\n[*] Creando índices aceleradores para el dashboard...")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_records_curp_status ON santander_records(curp_status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_records_curp_falta ON santander_records(curp_falta);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_records_genero ON santander_records(genero);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_records_estado ON santander_records(estado);")
    conn.commit()
    conn.close()

    total_time = time.time() - t_start
    print("\n" + "="*60)
    print("REPORTE OFICIAL DE MIGRACIÓN Y CÁLCULO DE CURP — SANTANDER DB")
    print("="*60)
    print(f"Total registros analizados : {stats['total']:,}")
    print(f"CURPs existentes previas   : {stats['existente']:,}")
    print(f"CURPs calculadas con éxito : {stats['calculada']:,} ({stats['calculada']/stats['total']*100:.2f}%)")
    print(f"Registros no calculables   : {stats['no_calculable']:,} ({stats['no_calculable']/stats['total']*100:.2f}%)")
    print("-" * 60)
    print("Desglose de motivos (CURP_FALTA) en orden estricto de prelación:")
    for k in ["sin_fecha", "sin_genero", "sin_estado", "sin_nombre", "rfc_invalido"]:
        cnt = stats["motivos"][k]
        pct = (cnt / stats['total']) * 100
        print(f"  - {k:<15}: {cnt:9,} ({pct:5.2f}%)")
    print("-" * 60)
    print(f"Tiempo total de cómputo    : {total_time:.1f} s ({total_time/60:.2f} min)")
    print("="*60)

if __name__ == "__main__":
    main()
