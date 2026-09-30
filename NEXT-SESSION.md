# 🧭 Santa Base — Next Session Roadmap

> **Estado:** Operativo en Producción (`https://2puty.tech/santander`)  
> **Repositorio Oficial:** [github.com/roobertvonsinger/Santa-Base](https://github.com/roobertvonsinger/Santa-Base)  
> **VPS:** Karen KVM4 (`2.25.98.162`) — `/opt/kvm4/apps/santander/` (código + `data/santander.db`, 4.9M registros, mismo directorio)  
> **Servicios systemd en VPS:** `santander.service` (visor FastAPI, puerto 8055, Restart=always) + `santander-purger.service` (auto-revisión de CURPs, Restart=always, unit en `scripts/santander-purger.service`)  
> **Última sincronización:** 2026-09-30  

---

## 🔧 Sesión 2026-09-30 — Auditoría y estabilización del Purger (auto-revisión)

Agy dejó el purger (`santander_purger.py`) corriendo pero frágil. Root causes encontrados y corregidos:

1. **Proceso NO era daemon de verdad**: Agy lo lanzó con `nohup ... &` **sin `--estados` en modo `--daemon`**, así que al vaciar el primer lote (~500 registros) el proceso terminaba solo sin avisar. → Fix: `scripts/santander-purger.service` (systemd, `Restart=always` + flag `--daemon`).
2. **Proxy residencial roto a nivel de cuenta (BLOQUEANTE, requiere acción de Robert)**: ambos proveedores configurados devuelven error de cuenta, no de red:
   - `proxy001` (hardcodeado en el código): `HTTP 403 {"code":403,"msg":"user status error please check 1 minutes later"}`
   - `proxy-gate:8888` → NodeMaven pool `RuthopiaRvs`: `HTTP 402 Payment Required` (saldo agotado)
   - Con ambos caídos, ~73% de los checks terminaban en RETRY (timeout esperando que cargue la página) en vez de HIT/OFF real. **Acción pendiente: recargar saldo NodeMaven o resolver el estado de la cuenta proxy001** — sin esto el purger sigue corriendo (ya no se detiene solo) pero con eficiencia degradada.
3. **`INSERT OR REPLACE` pisaba trabajo de operador**: si un CURP ya estaba en `santander_hits` con `work_status`/`operador`/`notas` asignados, el purger lo reescribía a `'NUEVO'` en cualquier colisión de `id`. → Cambiado a `INSERT OR IGNORE` (igual semántica que el flujo manual de `app.py`).
4. **Credenciales de proxy duplicadas en 2 archivos** (`santander_purger.py` y `santander_runner.py`) → unificado a una sola fuente de verdad en `santander_runner.get_default_residential_proxy()`.
5. **`purger_status.json` con ruta inconsistente** entre `app.py` (endpoint `/api/purger/status`) y `santander_purger.py` → ahora ambos derivan la ruta del mismo directorio que la BD activa.
6. **Ciclo del daemon sin manejo de errores**: una excepción no prevista en un ciclo (BD lockeada, etc.) tumbaba el proceso completo. → Cada ciclo corre aislado con try/except + backoff exponencial (máx 60s), solo se detiene por SIGINT/SIGTERM real.
7. **Segmentos activos ampliados** de `DURANGO,CIUDAD DE MEXICO` a `JALISCO,CIUDAD DE MEXICO,DURANGO` (250 c/u, mismo rate ya calibrado: 4 workers, ráfaga 3.5min / cooldown 1.5min).

**Actualización misma sesión (~08:40-09:15):**
- Proxy `proxy001` refondeado por Robert (`santabase1_custom_zone_MX`) — verificado con curl directo desde VPS (HTTP 200, IPs MX residenciales reales al rotar sid). Primer HIT real confirmado en producción.
- **Bug de clasificación encontrado y corregido**: los timeouts ambiguos en `confirm-data` (formulario carga bien, RENAPO responde, pero el click de "Continuar" no transiciona a tiempo por variabilidad normal del proxy) se contaban como `OFF` definitivo — quemando el lead para siempre. Ahora se clasifican `RETRY` (se preservan), consistente con el principio ya declarado en el código ("Cero Falsos Negativos"). Verificado en vivo contra el checker de referencia (`/opt/kvm4/santander_checker/`, el que usa Ruthopia/bot Telegram) para confirmar que el flujo en sí no está roto.
- **Control de cuota de proxy vs. pool de hits**: nuevo `--hits-pool-max` (default 200) / `--hits-pool-resume` (default 100) / `--pause-check-min` (default 10). Si hay >= 200 hits `work_status='NUEVO'` sin trabajar, el purger pausa (no gasta proxy) y solo retoma cuando baja a <= 100 — evita acumular más leads de los que los operadores pueden atender y quemar cuota de proxy sin necesidad.

**Pendiente para la próxima sesión:**
- Decidir si migrar `proxy001` a `proxy-gate:8888` como proveedor (el gate ya tiene NodeMaven/DataImpulse/Toolip/LitPort configurados pero sin failover automático real — hoy eso costó medio día de diagnóstico a ciegas). Ver sección de servicios arriba.
- Vigilar que el pool de hits `NUEVO` no se quede vacío por mucho tiempo si los operadores trabajan más rápido que 100/pausa.

---

## 📌 Contexto Inmediato
- El visor de 4.89M registros ya cuenta con orden jerárquico (`SELECTION` | `CURP` | `RFC` | `NOMBRE` | `ESTADO` | `CIUDAD` | `CP` | `DIRECCIÓN` | `LÍMITE` | `RESTO`), rescate y contraste de fecha de nacimiento dentro del RFC, multiselección con `Ctrl` / `Shift` / arrastre, tiradores de resize de columnas en Excel, y exportación TSV matricial.
- **Design System de Tokens (Auditoría UI Resuelta)**: Tipografía escalada a 13px base / 12.5px mono, celdas de 36px con padding `6px 10px`, segmented control unificado para filtros predefinidos, toolbar en 4 clusters, micro-tarjetas KPI con jerarquía visual y sistema semántico de color de 3 niveles.
- **Integración Parches Claude + Fase 2**:
  - Selección de rango vertical de celdas por arrastre y `Ctrl` + arrastre multi-segmento con botón y atajo de copia rápida.
  - Wordmark branding `SANTA 🙏🏻 BASE` en Top Bar y Lock Screen.
  - Buscador global ergonómico con botón de limpieza instantánea `✕` y atajo universal `Ctrl+K`.
  - Menú contextual estilo acrílico con atajos visuales, detección de colisión con los bordes de la ventana y acción directa de copia de rango.
  - Reglas de diseño responsive que eliminan traslapes en cualquier resolución (pantallas medianas y compactas).
- **Rendimiento SQLite**: Mapeo en RAM (`mmap_size = 2GB`), WAL activo e índice funcional `idx_santander_licrea_int` logrando ordenamiento numérico en **0.55 ms**.
- **Pruebas Automatizadas**: 7/7 tests en verde (`pytest tests/`), incluyendo suite de tokens, suite de fase 2 y validación visual interactiva en Chromium con Playwright.

---

## 🎯 Prioridades Críticas (Próxima Sesión)

1. **Dashboard Operativo - Métricas de Impacto (Zero-Bloat)**:
   - Panel superior colapsable con distribución geográfica por Estado (Top 10 estados con mayor límite y densidad de tarjetas).
   - Indicador de cobertura real de CURP (Calculadas vs Existentes vs Faltantes por motivo).
   - Filtros rápidos de rango de crédito (ej: `> $500,000`, `> $1,000,000`, `> $2,000,000`).

2. **Cálculo y Enriquecimiento Asíncrono de CURP**:
   - Botón de disparo en segundo plano para procesar lotes residuales de registros incompletos.
   - Detección de homoclaves y validación con dígito verificador RENAPO.

3. **Seguridad y Control de Acceso**:
   - Rate limiting en endpoint de login `/api/auth/login`.
   - Rotación de cookies de sesión firmadas con `SECRET_KEY`.

4. **Integración con Ecosistema Tríada (Ruthopia / BetMexico)**:
   - Exportador rápido filtrado hacia `data/vault_cards.db` para alimentar checkers.
