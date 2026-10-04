"""Umbral de nacimiento compartido por las sondas.

Existe porque las sondas ya contours (contaron 491 filas que el purger nunca
tocaba) por hardcodear un corte de edad distinto al que el purger usa de verdad.
Tres sondas tenian '600101' (1960-01-01) pegado a mano mientras el argparse y el
unit systemd corren con 1963-01-01. El numero de "material disponible" era
mentira y nadie lo noto porque el conteo crudo seguia dando 491 clavado.

La regla: el umbral de edad se lee de UNA sola fuente, el modulo que el purger
tiene como default, y las sondas lo importan. Si el purger cambia `--born-after`,
estas sondas ya no pueden mentir.

`born_after_YYYYMMDD("1963-01-01")` -> '630101'
`born_after_sql("1963-01-01")` -> "SUBSTR(u6rfc, 5, 6) >= '630101'"

Nota sobre el RFC: `u6rfc[4:10]` es YYMMDD, y el corpus usa prefijo de siglo >= 30
para los nacidos antes de 2000, asi que comparar los 6 chars como texto ordena
bien la cohorte. Mismo criterio que `build_segment_query` en santander_purger.py.
"""

import os
import sys

# El default canonico vive en santander_purger.py (--born-after). Importarlo de
# ahi es lo que evita que las sondas y el purger se separen otra vez.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
try:
    from santander_purger import BORN_AFTER_DEFAULT as BORN_AFTER
except ImportError:  # pragma: no cover - fallback si el modulo no importa limpio
    BORN_AFTER = "1963-01-01"


def born_after_YYYYMMDD(fecha: str = None) -> str:
    """'1963-01-01' -> '630101'. Es lo que espera el SUBSTR del RFC."""
    fecha = fecha or BORN_AFTER
    return fecha[2:4] + fecha[5:7] + fecha[8:10]


def born_after_sql(fecha: str = None) -> str:
    """Fragmento SQL parametrizable... no: literal, porque el valor viene del
    modulo y no de input de usuario. Devuelve el predicado completo."""
    return "SUBSTR(u6rfc, 5, 6) >= '%s'" % born_after_YYYYMMDD(fecha)


def config_efectiva_purger() -> str:
    """El mismo corte, pero contandolo de las dos formas para poder comparar."""
    return ">= '%s'  (--born-after %s)" % (born_after_YYYYMMDD(), BORN_AFTER)