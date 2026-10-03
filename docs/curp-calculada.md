# Cálculo de CURP — cómo funciona y qué está medido

Módulo: `scripts/curp_calc.py`. Es la pieza que hace posible alimentar el
purger: sin `curp` calculada en la columna, `santander_purger.build_segment_query`
no devuelve ninguna fila y la bóveda de hits queda vacía.

## Layout (18 caracteres)

| Posición | Contenido | Fuente |
|---|---|---|
| `[0:4]` | iniciales | **RFC de la persona** (`u6rfc[0:4]`) |
| `[4:10]` | `YYMMDD` | `u6rfc[4:10]` |
| `[10]` | sexo `H`/`M` | léxico de nombres |
| `[11:12]` | entidad, 2 letras | `u6estado` |
| `[13]` | consonante interna del paterno | `dmname` |
| `[14]` | consonante interna del materno | `dmname` |
| `[15]` | consonante interna del nombre dado | `dmname` |
| `[16]` | homoclave (`0` pre-2000, `A` 2000+) | `u6rfc[4:6]` |
| `[17]` | dígito verificador | algoritmo oficial |

**Las 4 iniciales salen del RFC, no del nombre.** Decidido por medición, no por
suposición (`scripts/initiales_rfc_vs_nombre.py`): tomar las iniciales del RFC
acierta 689/714 = **96.50%**; recalcularlas del nombre acierta **0/714**. El RFC
de la persona es la fuente de verdad.

**La consonante interna** es la primera consonante *después* de la primera vocal:
`HERNANDEZ → R`, no `H`.

**`COMUNES`** = `{JOSE, MARIA, MA, J}`: si el primer nombre dado es uno de esos,
el nombre que cuenta es el siguiente. `MARIA DE LOURDES SANCHEZ TEJEDA` → `p3=D`
(DE), `p15=R` (LOURDES). Verificado al 100% en los 142,313 casos del pool que
esta regla decide (`scripts/regla_comunes.py`).

## Dígito verificador — algoritmo oficial

Extraído del propio JavaScript de la calculadora oficial de RENAPO
(`docs/evidencia-curp/curp.js`). No es el de la documentación informal:

```
diccionario = "0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ"   (& = Ñ)
suma  = sum(valor[curp[i]] * (18 - i) for i in 0..16)
digito = (10 - suma % 10) % 10
```

El peso es **descendente 18..2**, no alterno 2/1, y es **complemento a 10**.
El diccionario incluye `Ñ` como `&`; el punto cuidado de no omitir `O` y `P`.

Validado: **576/576** CURPs reproducen el dígito correcto, en ambos sentidos
(las aceptadas y las rechazadas por RENAPO).

## Qué mide el acierto, y qué NO

Son dos cosas distintas y no se comparan:

- **96.50%** (offline, `scripts/curp_medir_final.py`): corrección del cálculo,
  contra 714 CURPs reales de la BD. Por posición: fecha, sexo, entidad, las tres
  consonantes internas, homoclave y dígito verificador = **100.00%**. Las
  4 iniciales del RFC = 96.50%. Es el techo real del cálculo.
- **~29%** (en vivo, `scripts/renapo_controle.py`): CURPs calculadas que RENAPO
  acepta.

### Por qué el en vivo es tan bajo: `OB-ORQ-05` no es "CURP mal"

Prueba de control con 3 grupos, mismos pipeline:

| Grupo | Qué es | Resultado |
|---|---|---|
| A | CURPs **reales** que RENAPO ya había aceptado | 8/8 avanzan al banco (`PE170`, `PE160`, LikeU Pro, preexistente) — **cero `OB-ORQ-05`** |
| B | CURPs **reales** que RENAPO ya había rechazado | 8/8 rechazadas otra vez, idéntico |
| C | CURPs **calculadas** por este módulo | 2 pasan, 2 LikeU Pro, 4 `OB-ORQ-05` |

El grupo A prueba que el formato es correcto. El grupo B prueba que el rechazo se
reproduce sobre CURPs que la propia base guarda como reales. **Conclusión:
`OB-ORQ-05` significa que RENAPO no encuentra a esa persona en su registro.** Es
un filtro de datos del registro, no un defecto de formato. La tasa en vivo mide
cobertura del registro RENAPO, no calidad del cálculo.

## Cobertura del pool

`scripts/curp_medir_final.py`, sobre 200,000 filas de 4.86M:

```
CALCULABLES                        91.23%
sexo_nombre_desconocido             8.57%
rfc_enmascarado                     0.15%
estado_desconocido                  0.05%
digito verificador mal formado      0.00%
```

Un nombre no reconocido en el léxico **se descarta, no se adivina**: una CURP con
el sexo inventado se rechaza igual en RENAPO y además quema una llamada.

## Bugs corregidos (todos medidos antes de tocar código)

1. **Homoclave invertido** — `'A' si anio < 50` producía "nació 2044" para un
   nacido en 1944. **7.70% del pool** (374,373 filas). Ahora `'A'` solo para
   `yy <= 01`.
2. **RFC `XXXX` enmascarado** — `"XXXX".isalpha()` es `True`, así que el validador
   lo aceptaba. 4,503 filas de basura, y contaminaba la línea base de medición.
   Solo se rechaza el prefijo `XXXX` exacto: la `X` suelta es el dígito
   verificador RFC válido (`MAFD6906306X4`) y no se toca.
3. **Sexo inventado por inicial** — el fallback `"si empieza con R es mujer"`
   clasificaba mal 31 nombres con verdad conocida, y los nombres que caían ahí
   eran los más frecuentes del pool (`ANGEL` 846 → salía `M` siendo hombre).
   Eliminado. `p10` subió a **100.00%**.
4. **854 valores de `u6estado` sin código** — municipios (`MONTERREY`) y
   abreviaturas con punto (`N.L.`, `MICH.`, `B.C.NORTE`). Resueltos por
   normalización. Descarte por estado: 0.63% → 0.05%.
5. **`GABRIEL` dentro de `_FEM`** — typo al copiar la lista.

## Uso

```bash
# Poblar el pool (el purger no ve nada sin esto)
python scripts/curp_sync.py --dry --limit 50000     # simular
python scripts/curp_sync.py --limit 100000 --lotes 100

# Medir contra las CURPs reales
python scripts/curp_medir_final.py

# A/B de iniciales RFC vs nombre
python scripts/initiales_rfc_vs_nombre.py

# Prueba en vivo contra RENAPO
python scripts/renapo_live_test.py --n 20 --offset 400
python scripts/renapo_controle.py --n 8             # el control de 3 grupos
```

`scripts/sondas/` contiene las 51 sondas de diagnóstico que se usaron para
encontrar cada bug. No son parte del pipeline; se conservan como evidencia de
cómo se llegó a cada corrección.