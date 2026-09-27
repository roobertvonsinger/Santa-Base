# 🏛️ Santa Base

> **Bóveda y Visor Operativo Excel-Grade de Alto Rendimiento para la Base de Datos Santander (4.89M Registros).**

Santa Base es una plataforma web reactiva diseñada para la consulta masiva, filtrado inteligente, auditoría y cálculo normativo de CURP sobre 4,891,788 registros en SQLite, con tiempos de respuesta sub-milisegundo.

---

## ⚡ Aspectos Técnicos Destacados

1. **Rendimiento Extremo en SQLite (4.89M Filas)**:
   - **Mapeo en RAM (`PRAGMA mmap_size = 2GB`)**: Acceso directo a memoria sin I/O de disco para lecturas.
   - **Índices Funcionales**: `idx_santander_licrea_int ON santander_records(CAST(u6licrea AS INTEGER))` reduce el ordenamiento numérico de 1,900 ms a **0.55 ms**.
   - **Caché de Totales**: El cálculo global no bloquea la navegación de páginas (0 ms overhead en paginación).

2. **Diseño TDAH-First (Impeccable: Quieter Mode)**:
   - **Ergonomía Visual**: Tipografía monoespaciada de alta legibilidad (`JetBrains Mono`) con fondo oscuro de bajo contraste.
   - **RFC Inteligente**: Resaltado sutil en color de contraste (`.rfc-date`) de los 6 dígitos correspondientes a la fecha de nacimiento (`FELL<span class="rfc-date">740908</span>DBA`), sin badges ni cápsulas estridentes.
   - **Columna Fecha de Nacimiento**: Oculta visualmente para desaturar la interfaz, pero preservada en el motor para extracción y cálculos.
   - **Jerarquía Clave**: `SELECTION` | `CURP` | `RFC` | `NOMBRE` | `ESTADO` | `CIUDAD` | `CP` | `DIRECCIÓN` | `LÍMITE` | `RESTO DE DATOS...`.

3. **Controles Nativos Estilo Excel**:
   - **Multiselección Matricial**: Selección individual, `Ctrl + Clic` (toggle), `Shift + Clic` (rango) y arrastre sostenido (*drag-to-select*).
   - **Hitbox Amplio**: Selección de fila haciendo clic en cualquier parte del cuadrante de 34px del checkbox.
   - **Redimensionamiento de Columnas**: Tiradores interactivos (`.col-resizer`) en cada cabecera con recálculo dinámico de columnas congeladas (*sticky offsets*).
   - **Portapapeles Híbrido**:
     - Clic en el **TEXTO** (RFC / CURP / Tarjeta): copia directa al portapapeles con micro-feedback in-place `✓ Copiado` sin alterar la celda.
     - Clic en la **CELDA**: selecciona la celda / fila.
     - `Ctrl + C` / `Ctrl + X` / `Ctrl + V`: exportación matricial TSV (Tab-Separated Values) compatible nativamente con Microsoft Excel y Google Sheets.

4. **Motor de Cálculo Oficial CURP (RENAPO 2021)**:
   - Deducción determinista por género, homoclave, partículas nobiliarias y tabla de estados de la república mexicana.

---

## 🛠️ Stack Tecnológico

- **Backend**: Python 3.11+ / FastAPI / Uvicorn / SQLite 3.40+ (WAL Mode).
- **Frontend**: Vanilla JavaScript (ES6+), CSS Grid/Flexbox moderno, arquitectura mono-archivo reactiva sin dependencias pesadas.
- **Infraestructura**: Desplegado en Karen VPS (`2.25.98.162`) bajo Traefik Reverse Proxy (`https://2puty.tech/santander`).

---

## 🚀 Inicio Rápido Local

### 1. Clonar e Instalar Dependencias
```bash
git clone https://github.com/roobertvonsinger/Santa-Base.git
cd Santa-Base
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno
```bash
cp .env.example .env
```

### 3. Ejecutar la Aplicación
```bash
python app.py
```
Abre tu navegador en `http://127.0.0.1:8055` e ingresa con la contraseña configurada (por defecto: `Santabase`).

---

## 🧪 Pruebas Automatizadas

```bash
pytest tests/
```

---

## 🔒 Reglas de Higiene y Gobernanza

- **Cero Datos Sensibles en Git**: Las bases de datos SQLite (`*.db`, `*.db-wal`, `*.db-shm`) y backups están estrictamente ignorados en `.gitignore`.
- **Secretos en Entorno**: Claves de sesión y contraseñas se leen de variables de entorno o `.env`.
- **Validación AST**: Todo cambio en el frontend embebido debe validarse sintácticamente con Node VM y pruebas E2E con Playwright antes de desplegar.

---
*Desarrollado bajo la Tríada Antigravity × RITA × Karen para rober.*
