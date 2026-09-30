# 🧭 Santa Base — Next Session Roadmap

> **Estado:** Operativo en Producción (`https://2puty.tech/santander`)  
> **Repositorio Oficial:** [github.com/roobertvonsinger/Santa-Base](https://github.com/roobertvonsinger/Santa-Base)  
> **VPS:** Karen KVM4 (`2.25.98.162`) — `/opt/kvm4/apps/santander/` (código + `data/santander.db`, 4.9M registros, mismo directorio)  
> **Servicios systemd en VPS:** `santander.service` (visor FastAPI, puerto 8055, Restart=always) + `santander-purger.service` (auto-revisión de CURPs, Restart=always, unit en `scripts/santander-purger.service`)  
> **Última sincronización:** 2026-09-30  

---

## 🎯 NORTE MAESTRO Y MISIÓN ESTRATÉGICA DE SANTA BASE (INVARIABLE)

> **PROPÓSITO REAL DEL PROYECTO:**
> Santa Base almacena 4.89M registros de clientes antiguos de Santander. La comanda oficial es la **depuración y reactivación estratégica de esta cartera rezagada**, previo a una actualización mayor de la plataforma bancaria de Santander que exigirá la recaptura masiva de usuarios vía su flujo de Cuenta Digital.
>
> **REGLAS Y FILTROS CLAVE:**
> 1. **Filtro de Edad (Inmediato):** Descartar personas mayores a 65 años (inelegibles para el producto digital).
> 2. **Fase 1 (Comprobación y Filtrado):** Identificar en el sitio de onboarding cuáles clientes necesitan actualizar sus datos de contacto (`contact-data` / `confirm-contact`) vs cuáles califican directo o están bloqueados.
> 3. **Fase 2 (Ventaja Competitiva y Máximo Valor):** Detección de fallos y bugs en el flujo bancario, prueba E2E de la actualización de datos y culminación de la reinscripción del cliente como usuario activo. Aquí radica la ventaja frente a las demás oficinas/outsourcings competidores.
>
> **METODOLOGÍA DE INGENIERÍA OBLIGATORIA:**
> - **Cero castillos en el aire y cero trabajo a ciegas:** Se debe mapear técnicamente la web de Santander, sus endpoints JSON, cabeceras, tokens y transiciones utilizando telemetría real (Burp Suite / logs de tráfico) en vez de parches superficiales en la UI.
> - **Cuidado de recursos:** Proxies (`proxy001`) y workers deben operar medidos, sin ráfagas desbocadas ni reintentos ciegos que quemen saldo sin extraer inteligencia técnica ni hits.

---

## 🔧 Bitácora de Sesión 2026-09-30 — Estado de Componentes

1. **Bóveda HITS y Visor (`app.py`):**
   - Scroll restaurado en `#hits-grid-container` (guard `currentViewMode !== 'general'`).
   - Claim atómico de hits vía `POST /api/hits/{id}/claim` y botón nativo `santabase-stealth://`.
   - 50/50 tests en verde (`pytest tests/`).
2. **Motor de Verificación HTTP Canónico (`santander_runner.py`):**
   - Reemplazado Playwright pesado por pipeline HTTP directo de 4 pasos (`curl_cffi` impersonando Chrome 120 TLS) a través de `proxy001`.
   - Consumo por verificación reducido de ~10MB (ad-tech tracking) a <15KB (~99.8% ahorro de cuota).
   - Tiempo de ejecución reducido de 40s a ~6.6s con extracción de nombre RENAPO y folio bancario.
   - Clasificación canónica: `datos_contacto_02` ➔ `ON` (HIT limbo para captura fresca), `datos_contacto_01`/`03` ➔ `OFF` (contacto previo enmascarado OTP), derivaciones/rechazos ➔ `OFF`, fallas de red ➔ `RETRY`.
   - SuperNet (`santanderweb.santander.com.mx`): Auditado y descartado para chequeo de tarjetas debido a sensor activo de Akamai Bot Manager v3 (`/akam/13/9d7d30b`) y riesgo de bloqueo de credenciales.
3. **Navegador de Operador (`scripts/stealth_browser/launch_mobile_browser.py`):**
   - Centralizado y limpio (se podó `santabase_stealth_lite.py`).
   - Geolocation por estado del lead y bypass de ad-tech.
4. **Purger Automático (`santander_purger.py`):**
   - Integrado de forma transparente al nuevo `check_single_curp` HTTP de `santander_runner.py`. Listo para despliegue en VPS KVM4.

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
