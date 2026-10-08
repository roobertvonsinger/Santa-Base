# Smartplan: Despliegue de Santa Base en VPS KVM2 (`rovies.tech`) & Depuración Canónica

## Resumen Ejecutivo
- **Objetivo:** Poner en producción Santa Base (Visor Excel-Pro + Bóveda HITS + Motor de Cosecha) en el nuevo VPS Hostinger KVM2 (`179.236.64.196`) bajo el dominio `rovies.tech` con SSL automático, aislando arquitectura y depurando scripts obsoletos de `repos/santa-base`.
- **Destino VPS:** `/opt/apps/santander/` (código + venv + data).
- **Dominio:** `rovies.tech` (DNS A ya apunta a `179.236.64.196`).

---

## 🔄 Ciclo Dialéctico de 5 Fases

### Fase 1: Propuesta Base & Filtro de Musk (Look Outside & Zero-Waste)
1. **Filtro Musk:** ¿Se necesita un clúster complejo con Traefik, consul y 5 capas de Docker? No. Santa Base es una aplicación FastAPI I/O-bound sobre SQLite local de 2GB con dependencias de red C (`curl_cffi`, Playwright). Empaquetar todo en Docker genera overhead en SQLite WAL y complica la integración de Playwright en un VPS de 2 vCPUs / 8GB RAM.
2. **Arquitectura óptima elegida:**
   - **Ingress Web & SSL:** Contenedor Caddy ultra-ligero (`caddy:alpine`, <35MB RAM) con `network_mode: host` y auto-TLS Let's Encrypt para `rovies.tech` y `www.rovies.tech`.
   - **App Core:** Systemd `santander.service` en Python 3.11 virtualenv host (puerto `:8055`), directo a `data/santander.db`.
   - **Cosechador / Purger:** Systemd `santander-harvest.service` desacoplado, controlable vía API/systemctl.
3. **Inventario:** SSH Key `kvm4_hostinger` ya configurada; alias `ssh rovies` operativo; Docker Compose v5.6 y Python 3.11 preinstalados en Debian 12 Bookworm.

### Fase 2: Re-análisis Crítico & Repropuesta Interna (Self-Critique)
1. **Puntos Ciegos Detectados:**
   - *Transferencia de BD (2.05 GB):* `scp` sin compresión sobre WAN puede demorar o corromperse si se corta.
     *Solución:* Comprimir en origen con `gzip` / `pigz` o `zstd` antes de transferir, verificar suma SHA256 o tamaño exacto en destino, y habilitar SQLite WAL en el primer arranque.
   - *Bloqueo de Playwright en VPS Linux:* Debian 12 Bookworm requiere dependencias del sistema (`libnss3`, `libatk1.0-0`, etc.) para Chromium.
     *Solución:* `playwright install --with-deps chromium` durante el setup.
   - *Dependencia de curl_cffi:* Requiere `libffi-dev` y compiladores si no hay wheel binario. En Python 3.11 x86_64 Debian existe wheel oficial de `curl_cffi==0.15.0`.
2. **Contra-Propuesta:** Descartar Traefik multi-archivo (`santander_traefik.yml` de 66 líneas). Un simple `Caddyfile` de 8 líneas maneja `rovies.tech` con reverse proxy a `127.0.0.1:8055` y redirección automática HTTP -> HTTPS con certificado emitido en 10 segundos.

### Fase 3: Co-Auditoría & Sugerencias de la Tríada
1. **Auditoría de Infraestructura (Karen / Ops):**
   - No colocar la base de datos en `/root` ni en partición temporal; crear estructura limpia `/opt/apps/santander/{code,data,logs}`.
   - Establecer `systemd` con `Restart=always`, `RestartSec=5s`, límites de archivos `LimitNOFILE=65535` para soportar sockets concurrentes.
   - Crear swap file de 2GB (el VPS viene con 0B swap) para absorber picos de memoria sin riesgo de OOM killer en los 8GB RAM.
2. **Auditoría de Deuda Técnica (DSH / Code Review):**
   - El repo local acumuló scripts temporales de parches ("apply_*") y más de 50 sondas de deducción que ya no se usan (`scripts/sondas/`).
   - Mover la basura a un archivo deprecado o depurarla sin tocar el núcleo canónico (`app.py`, `santander_runner.py`, `curp_calc.py`, `tests/`).

### Fase 4: Validación de Viabilidad & Fusión Sintética
1. **Validación DNS:** `rovies.tech` y `www.rovies.tech` ya resuelven a `179.236.64.196`. Caddy emitirá el certificado TLS inmediatamente en el puerto 80/443.
2. **Seguridad y Accesibilidad:**
   - La UI requiere la clave canónica `"Santabase"` (`AUTH_PASSWORD`).
   - El backend corre en `127.0.0.1:8055` cerrado al exterior; solo Caddy expone 80/443.

---

## 📋 Fase 5: Smartplan Definitivo (Plan de Acción para `/Smartexe`)

### Paso 1: Depuración de Basura en Repo Local (`repos/santa-base`)
- [ ] Eliminar respaldos viejos (`app.py.bak-20260927`).
- [ ] Mover scripts de parches antiguos `apply_*.py`, `finalize_santabase.py`, `fix_db_and_auth_input.py` a `_archive/legacy_patches/` o eliminarlos tras validar que sus cambios están en el codebase principal.
- [ ] Archivar carpeta `scripts/sondas/` en `scripts/_archive_sondas/` para mantener el árbol de desarrollo limpio y ágil.
- [ ] Ejecutar `pytest tests/` para asegurar que el suite sigue 100% verde (36/36 tests pasados).
- [ ] Git commit & push a `origin/main`.

### Paso 2: Acondicionamiento del VPS KVM2 (`rovies.tech`)
- [ ] Crear 2GB de Swap (`fallocate -l 2G /swapfile && mkswap && swapon`).
- [ ] Instalar paquetes base en Debian: `python3-venv python3-pip git curl htop zstd ufw`.
- [ ] Crear directorios canónicos: `/opt/apps/santander/code`, `/opt/apps/santander/data`, `/opt/apps/caddy`.
- [ ] Configurar firewall UFW: puertos 22 (SSH), 80 (HTTP) y 443 (HTTPS) abiertos.

### Paso 3: Despliegue de Ingress Caddy (SSL para `rovies.tech`)
- [ ] Crear `/opt/apps/caddy/Caddyfile`:
  ```caddy
  rovies.tech, www.rovies.tech {
      reverse_proxy 127.0.0.1:8055
      encode gzip zstd
  }
  ```
- [ ] Levantar Caddy vía Docker Compose en `/opt/apps/caddy/docker-compose.yml` con reinicio automático.

### Paso 4: Despliegue de Código y Base de Datos
- [ ] Clonar repositorio limpio desde GitHub (`git clone https://github.com/roobertvonsinger/Santa-Base /opt/apps/santander/code`).
- [ ] Crear entorno virtual Python (`/opt/apps/santander/venv`) e instalar `requirements.txt`.
- [ ] Instalar navegadores Playwright para Linux: `playwright install --with-deps chromium`.
- [ ] Transferir `santander.db` (2.05 GB) comprimido con `zstd` / `gzip` hacia `/opt/apps/santander/data/santander.db`.
- [ ] Verificar integridad de SQLite en VPS: `sqlite3 /opt/apps/santander/data/santander.db "PRAGMA quick_check;"`.

### Paso 5: Configuración de Servicios Systemd & Smoke Test E2E
- [ ] Instalar `/etc/systemd/system/santander.service`:
  - `ExecStart=/opt/apps/santander/venv/bin/uvicorn app:app --host 127.0.0.1 --port 8055 --workers 2`
  - Variables de entorno: `SANTANDER_DB_PATH=/opt/apps/santander/data/santander.db`
- [ ] Iniciar y habilitar servicio (`systemctl enable --now santander`).
- [ ] **Smoke Test End-to-End:**
  - `curl -I https://rovies.tech/` -> HTTP 200 / Login HTML con certificado SSL válido.
  - Login con contraseña `"Santabase"` -> Token JWT válido.
  - Consulta a `/api/stats` -> 4.89M registros reportados correctamente.
- [ ] Actualizar `PROJECTS_MAP.md` y `NEXT-SESSION.md` con la nueva topología de KVM2.
