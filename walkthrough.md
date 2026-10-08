# Walkthrough: Despliegue de Santa Base en KVM2 (`rovies.tech`)

## 1. Resumen de la Ejecución
Se desplegó con éxito la infraestructura y el servicio completo de **Santa Base** en la nueva VPS KVM2 (`179.236.64.196`) bajo el dominio **`rovies.tech`** con certificado SSL automático de Let's Encrypt.

## 2. Acciones y Cambios Realizados

### A. Depuración Local del Repositorio (`Santa-Base`)
- **Archivos deprecados:** Se movieron parches one-off (`apply_ui_tokens.py`, `apply_phase2_improvements.py`, `apply_santabase_upgrade.py`, `finalize_santabase.py`, `apply_red_black_design.py`, `fix_db_and_auth_input.py`) a `_archive/legacy_patches/`.
- **Sondas experimentales:** Se archivaron más de 50 sondas de deducción de CURP en `scripts/_archive_sondas/`.
- **Residuos:** Se eliminó `app.py.bak-20260927`.
- **Suite de Pruebas:** 36/36 tests ejecutados en verde (`pytest tests/`).
- **Sincronización:** Commits `a44ca62` y `b5960d7` pusheados a `origin/main`.

### B. Acondicionamiento de la VPS KVM2 (`179.236.64.196`)
- **Configuración SSH:** Alias `ssh rovies` y `ssh kvm2` habilitados con llave `kvm4_hostinger` (sin contraseña).
- **Memoria & Swap:** Activados 2GB de Swap (`/swapfile`) persistentes en `/etc/fstab`.
- **Seguridad UFW:** Puertos 22 (SSH), 80 (HTTP) y 443 (HTTPS) abiertos.
- **Estructura canónica:**
  - Ingress: `/opt/apps/caddy/`
  - Aplicación: `/opt/apps/santander/code/`
  - Base de Datos: `/opt/apps/santander/data/`
  - Logs: `/opt/apps/santander/logs/`

### C. Ingress y Certificados SSL (`rovies.tech`)
- Desplegado contenedor Caddy (`caddy:2-alpine`) con `network_mode: host`.
- Certificados TLS emitidos por Let's Encrypt para `rovies.tech` y `www.rovies.tech`.
- Redirección automática HTTP -> HTTPS con compresión `gzip` y `zstd`.

### D. Base de Datos y Dependencias
- Entorno virtual en `/opt/apps/santander/venv` con `requirements.txt` y Playwright Chromium.
- Transferencia comprimida de `santander.db` (2.05 GB).
- Integridad SQLite validada con `PRAGMA quick_check;` (QuickCheck: `ok`).
- Conteo de registros verificado:
  - `santander_records`: **4,891,788**
  - `santander_hits`: **10**
  - `santander_prepool`: **194**

### E. Servicio Systemd (`santander.service`)
- Servicio activo y habilitado en arranque:
  ```bash
  systemctl status santander
  ```
- Corre en `127.0.0.1:8055` con 2 workers Uvicorn.

## 3. Verificación y Evidencia de Funcionamiento

Prueba directa contra endpoint público:
```python
POST https://rovies.tech/api/auth/login -> 200 OK (JWT Token emitido)
GET  https://rovies.tech/api/stats      -> 200 OK
{
  "total": 4891788,
  "with_curp": 4556301,
  "curp_existente": 4556301,
  "hits_total": 10,
  "hits_active": 5
}
```

URL de acceso: **`https://rovies.tech/`** (Contraseña: `Santabase`)
