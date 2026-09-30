# Stealth Mobile Browser — Santa Base

Navegador móvil nativo (Tkinter + Playwright, visible, no headless) para que un operador trabaje
en vivo un hit de la bóveda con el cliente por teléfono. Fuente canónica del
`StealthMobileBrowser.exe` que se distribuye a los operadores.

## Qué hace

- Emula Pixel 7 / Android 14, con `playwright-stealth` para evadir detección de bot.
- CSP-bypass necesario contra `onboarding.santander.com.mx` (sin esto, Chromium tira
  `net::ERR_RESPONSE_HEADERS_TRUNCATED` — verificado 2026-09-30).
- Hasta 10 proxies residenciales cargados al inicio, o **conexión directa (IP local del
  operador)** — recomendado cuando el operador ya está físicamente en el mismo estado que el
  cliente (evita pagar proxy y es la señal más "limpia" posible).
- **Agregar/cambiar proxy en caliente** desde el panel flotante sin cerrar el navegador — la
  sesión (cookies, `storage_state`) se preserva entre cambios.
- Pista visible de a qué estado pertenece el hit (`--estado=`), para que el operador sepa qué
  proxy pegar o si le conviene usar su IP local.
- Recuerda la última sesión (útil si Santander tira al cliente a medio flujo).

## Uso manual (operador)

```bash
python launch_mobile_browser.py --curp=XXXX... --estado="JALISCO"
```

O corriendo el `.exe` compilado — el diálogo de arranque pide lo mismo por GUI.

`--operator-estado="Jalisco"` (o guardarlo una vez en el diálogo de arranque) hace que el
navegador sugiera automáticamente "Conexión Directa" cuando el hit es del mismo estado del
operador.

## Compilar el .exe (PyInstaller)

```bash
pip install -r requirements.txt pyinstaller
playwright install chromium   # solo si no se usa Chrome/Edge del sistema
pyinstaller --onefile --windowed --name StealthMobileBrowser launch_mobile_browser.py
```

El `.exe` queda en `dist/StealthMobileBrowser.exe`. Redistribuir a cada operador manualmente
(no hay pipeline automático de distribución todavía).

## Estado de proxies (2026-09-30)

- `DEFAULT_PROXIES` se deja **vacío a propósito** — el proxy NodeMaven que traía hardcodeado
  antes está sin saldo (402 Payment Required).
- NodeMaven es el único proveedor confirmado con targeting real por estado/región
  (`region-jalisco`, `region-oaxaca`, etc. en el username) — pendiente de refondeo.
- `proxy001` (el que usa el purger automático) **no soporta targeting por estado/ciudad en
  ningún producto suyo**, verificado con curl contra varios formatos de username y contra su
  API `getIPlist` (esa API además regresa IPs de datacenter en EE.UU., no residenciales MX —
  no usar para esto).

## Pendiente (no resuelto en esta sesión)

- Wiring de un clic desde la bóveda de hits (`/santabase` → botón Onboarding) hacia este
  navegador nativo. El navegador del operador no puede lanzar un `.exe` directamente por
  seguridad — falta decidir el mecanismo (protocolo custom `santabase-stealth://` registrado
  una vez por PC de operador, vs. copiar CURP+proxy sugerido al portapapeles). Ver
  `NEXT-SESSION.md`.
