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
> 1. **Filtro de Edad (Inmediato):** Descartar personas mayores a 65 años (inelegibles para el producto digital). Umbral canónico: nacidos estrictamente a partir de `1963-01-01` (`born_after >= 1963-01-01`).
> 2. **Fase 1 (Comprobación y Filtrado):** Identificar en el sitio de onboarding cuáles clientes necesitan actualizar sus datos de contacto (`contact-data` / `confirm-contact`) vs cuáles califican directo o están bloqueados.
> 3. **Fase 2 (Ventaja Competitiva y Máximo Valor):** Detección de fallos y bugs en el flujo bancario, prueba E2E de la actualización de datos y culminación de la reinscripción del cliente como usuario activo. Aquí radica la ventaja frente a las demás oficinas/outsourcings competidores.
>
> **METODOLOGÍA DE INGENIERÍA OBLIGATORIA:**
> - **Cero castillos en el aire y cero trabajo a ciegas:** Se debe mapear técnicamente la web de Santander, sus endpoints JSON, cabeceras, tokens y transiciones utilizando telemetría real (Burp Suite / logs de tráfico) en vez de parches superficiales en la UI.
> - **Cuidado de recursos:** Proxies (`proxy001`) y workers deben operar medidos, sin ráfagas desbocadas ni reintentos ciegos que quemen saldo sin extraer inteligencia técnica ni hits.

---

## 🔧 Bitácora de Sesión 2026-09-30 — Estado de Componentes

1. **Bóveda HITS y Visor Simplificado (`app.py`):**
   - Sustitución de los dos botones redundantes por un único botón `🚀 Trabajar` en columna dedicada.
   - Cabeceras de `hits-table` interactivas y ordenables (`toggleHitsSort`, indicadores `▲`/`▼`) por estatus, tarjeta, curp, nombre, crédito, estado, ciudad, cp, operador y fecha.
   - Búsqueda en HITS expandida para indexar `codigo_postal`, `ciudad` y `u6acct`.
   - Control de concurrencia en `/api/hits/{id}/claim`: auto-cierre del lead anterior del operador (`CERRADO` con nota de auditoría) si abre otro. Superadmin (`Robertvs`) 100% exento.
   - Transmisión de parámetros completos (`curp`, `estado`, `cp`, `ciudad`, `name`, `user`, `role`) vía protocolo `santabase-stealth://`.
2. **Navegador de Operador (`scripts/stealth_browser/launch_mobile_browser.py`):**
   - Mapeo de prefijos postales mexicanos `CP_PREFIX_TO_ESTADO` y resolución de coordenadas GPS exactas por CP o Estado.
   - Ficha visual de datos del lead al arrancar con conexión directa local por default (sin ventana confusa de proxies).
   - Control estricto de instancia única por operador vía `PID_LOCK_FILE` y `taskkill` de procesos huérfanos. Superadmin exento.
3. **Purger Automático y Regla de Edad (`santander_purger.py`):**
   - Corrección del umbral de nacimiento a `1963-01-01` (excluye 1962 y anteriores) en código y en servicio `/etc/systemd/system/santander-purger.service` en Karen VPS KVM4.
   - Depuración de BD: 18 hits `<= 1962` actualizados a `DESCARTADO`. 91 hits `NUEVO` activos en la bóveda ($\ge 1963$).
4. **Verificación Automatizada:**
   - 52/52 pruebas en verde (`pytest tests/`).

---

## 📌 Punto de Arranque Inmediato (Sesión Limpia)

> [!IMPORTANT]
> ### 🚨 PRIORIDAD #1: Diagnóstico de Fallo en Endpoint de Formalización N2
> **Problema a resolver:** Descubrir la causa exacta del error al ejecutar el request de alta durante la aplicación:
> ```javascript
> fetch("https://onboarding.santander.com.mx/api/v1/obu/case/formalizada/N2/account-registry/alta", {
>   "headers": {
>     "accept": "application/json, text/plain, */*",
>     "accept-language": "es-419,es;q=0.9",
>     "cache-control": "no-cache",
>     "content-type": "application/json",
>     "pragma": "no-cache"
>   },
>   "referrer": "https://onboarding.santander.com.mx/",
>   "body": "{\"data\":{\"contract\":true,\"promotional\":true}}",
>   "method": "POST",
>   "mode": "cors",
>   "credentials": "include"
> });
> ```
> 
> **Líneas de auditoría técnica planificadas:**
> 1. **Inspección de Respuesta HTTP Real:** Revisar el código de estatus HTTP (400, 403, 409, 422, 500) y decodificar el payload JSON de error devuelto por Santander (`errorCode`, `message`, `errorDescription`, `incidentId`).
> 2. **Pre-requisitos de la Máquina de Estados (`obu/case`):** Determinar qué eventos o tokens previos faltan antes de poder formalizar:
>    - Validación de enrolamiento biométrico facial / FAD.
>    - Aceptación previa o descarga de carátula de contrato.
>    - Estado interno del expediente en `obu/case` (`registrada` -> `evaluada` -> `formalizada`).
> 3. **Headers, Tokens y Anti-CSRF:**
>    - Validar si el endpoint exige token de cabecera (`x-xsrf-token`, `x-request-id`, o header de sesión obtenido en la pantalla previa).
>    - Confirmar si la cookie de sesión (`JSESSIONID`, `AWSALB`, o similar) se mantiene activa con `credentials: "include"`.
> 4. **Restricciones del Core Bancario (Partenón/BNC):**
>    - Si el lead ya cuenta con un contrato previo activo o no liquidado que bloquee la apertura digital N2.
>    - Discrepancias entre CURP/RFC consultado y registros históricos.

---

## 🎯 Siguientes Tareas en Cola

1. **Dashboard Operativo - Métricas de Impacto (Zero-Bloat)**:
   - Panel superior colapsable con distribución geográfica por Estado.
   - Indicador de cobertura real de CURP.
2. **Cálculo y Enriquecimiento Asíncrono de CURP residual**.
3. **Seguridad y Control de Acceso**:
   - Rate limiting en endpoint de login `/api/auth/login`.
   - Rotación de cookies de sesión firmadas con `SECRET_KEY`.
