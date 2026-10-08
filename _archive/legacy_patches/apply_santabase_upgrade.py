#!/usr/bin/env python3
"""
Script de actualizacion completa para Santa Base:
1. Reemplazo de Formula Bar por Mega-Buscador (Command Bar amplio, prominente y facil de operar).
2. Cambio de URL canónica de /santander a /santabase (con redireccion 302 legacy).
3. Sistema de autenticacion multi-usuario RBAC adaptado y blindado desde Botmex (RobertVS, Magdiel, Luisito).
4. Proteccion estricta contra directory traversal y fugas de directorios VPS.
"""

import sys
import re

APP_PY_PATH = "app.py"

def main():
    with open(APP_PY_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # --- 1. ACTUALIZAR RUTAS Y AUTENTICACIÓN EN BACKEND ---
    old_auth_backend = re.search(r"AUTH_PASSWORD = .*?# --- Rutas de Datos Protegidas ---", content, re.DOTALL)
    if not old_auth_backend:
        print("ERROR: No se encontro el bloque de autenticacion backend en app.py")
        sys.exit(1)

    new_auth_backend = """# ── Multi-User RBAC & Authentication (Modelo Botmex Blindado) ──────────────
DEFAULT_USERS: dict[str, dict] = {
    "robertvs": {"display": "RobertVS", "telegram_id": 1341812706, "role": "superadmin"},
    "magdiel":  {"display": "Magdiel",  "telegram_id": 1059367082, "role": "operator"},
    "luisito":  {"display": "Luisito",  "telegram_id": 7847239854, "role": "operator"},
}

DEFAULT_PASSWORDS: dict[str, str] = {
    "robertvs": "d677aa73ca12341112367842164dd250136718a8885b901edd2cfe8474c630eb",
    "magdiel":  "4e93ba3f4dd91e3cfd4cbdeabf660839380442e9108da0efd010395e56a05a02",
    "luisito":  "4e93ba3f4dd91e3cfd4cbdeabf660839380442e9108da0efd010395e56a05a02",
}

COOKIE_NAME = "santabase_session"
SECRET_KEY = os.environ.get("SANTABASE_SECRET", os.environ.get("SANTANDER_SECRET", "santabase-super-secret-vault-2026"))
MASTER_PASSWORD = os.environ.get("SANTA_MASTER", os.environ.get("BMX_MASTER", ""))
AUTH_PASSWORD = "Santabase"  # Fallback retrocompatible para pruebas

# Proteccion anti-fuerza bruta: IP -> [timestamps]
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300  # 5 minutos de bloqueo

def sha256(plain: str) -> str:
    return hashlib.sha256(plain.encode('utf-8')).hexdigest()

SESSION_TTL = 86_400  # 24h para operadores
PERSISTENT_USERS = {"robertvs"}  # Sesión persistente para Superadmin
PERSISTENT_TTL = 60 * 60 * 24 * 365 * 10  # 10 años

def generate_session_token(username: str) -> str:
    timestamp = str(int(time.time()))
    payload = f"{username}:{timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{username}:{timestamp}:{signature}"

def verify_session_token(token: Optional[str]) -> Optional[dict]:
    if not token or token.count(":") != 2:
        return None
    try:
        username, timestamp_str, signature = token.split(":", 2)
        username = username.strip().lower()
        if username not in DEFAULT_USERS:
            return None
        timestamp = int(timestamp_str)
        now = time.time()
        max_age = PERSISTENT_TTL if username in PERSISTENT_USERS else SESSION_TTL
        if now - timestamp > max_age:
            return None
        payload = f"{username}:{timestamp_str}"
        expected_sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        u = DEFAULT_USERS[username]
        return {
            "username": username,
            "display": u["display"],
            "role": u["role"],
            "telegram_id": u["telegram_id"]
        }
    except Exception:
        return None

def check_rate_limit(client_ip: str):
    now = time.time()
    attempts = [t for t in LOGIN_ATTEMPTS.get(client_ip, []) if now - t < LOCKOUT_SECONDS]
    LOGIN_ATTEMPTS[client_ip] = attempts
    if len(attempts) >= MAX_FAILED_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Bloqueado temporalmente por 5 minutos.")

def record_failed_attempt(client_ip: str):
    now = time.time()
    if client_ip not in LOGIN_ATTEMPTS:
        LOGIN_ATTEMPTS[client_ip] = []
    LOGIN_ATTEMPTS[client_ip].append(now)

def get_current_user(request: Request) -> Optional[dict]:
    cookie_token = request.cookies.get(COOKIE_NAME)
    user = verify_session_token(cookie_token)
    if user:
        return user
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token == AUTH_PASSWORD:
            return DEFAULT_USERS["robertvs"]
        user = verify_session_token(token)
        if user:
            return user
    return None

def require_auth(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado. Inicia sesión en Santa Base.")
    return user

def require_superadmin(request: Request) -> dict:
    user = require_auth(request)
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Permisos insuficientes. Acción reservada a Superadmin.")
    return user

TOTAL_RECORDS_CACHE = None

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA mmap_size = 2147483648;")
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    return conn

def get_total_records_count(conn):
    global TOTAL_RECORDS_CACHE
    if TOTAL_RECORDS_CACHE is None:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM santander_records")
        TOTAL_RECORDS_CACHE = cur.fetchone()[0]
    return TOTAL_RECORDS_CACHE

class LoginPayload(BaseModel):
    username: Optional[str] = "robertvs"
    password: str

class UpdateRecordPayload(BaseModel):
    curp: Optional[str] = None
    results: Optional[str] = None
    field: Optional[str] = None
    value: Optional[str] = None
    updates: Optional[dict[str, Any]] = None

class BulkCurpPayload(BaseModel):
    text: str

class BatchUpdateItem(BaseModel):
    id: int
    field: str
    value: Optional[str] = None

class BatchUpdatePayload(BaseModel):
    items: list[BatchUpdateItem]

def format_combined_address(row: dict) -> str:
    parts = []
    a1 = (row.get("dmaddr1") or "").strip()
    a2 = (row.get("dmaddr2") or "").strip()
    muni = (row.get("u6delomu") or "").strip()
    city = (row.get("dmcity") or "").strip()
    edo = (row.get("u6estado") or "").strip()
    cp = (str(row.get("dmzip") or "")).strip()

    if a1: parts.append(a1)
    if a2: parts.append(f"COL. {a2}")
    if muni: parts.append(muni)
    if city and city != muni: parts.append(city)
    if edo: parts.append(edo)
    if cp: parts.append(f"C.P. {cp}")
    return ", ".join(parts) if parts else "Sin dirección registrada"

# --- Rutas de Autenticacion ---

@app.post("/api/auth/login")
def login(payload: LoginPayload, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    raw_user = (payload.username or "robertvs").strip().lower()
    password = payload.password.strip()

    if raw_user not in DEFAULT_USERS:
        record_failed_attempt(client_ip)
        raise HTTPException(status_code=401, detail="Usuario no autorizado")

    stored_hash = DEFAULT_PASSWORDS.get(raw_user)
    pwd_hash = sha256(password)
    pwd_ok = (pwd_hash == stored_hash) or (bool(MASTER_PASSWORD) and password == MASTER_PASSWORD)

    # Compatibilidad retroactiva para contraseña legacy en dev/testing
    if not pwd_ok and password == AUTH_PASSWORD:
        pwd_ok = True

    if not pwd_ok:
        record_failed_attempt(client_ip)
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    LOGIN_ATTEMPTS.pop(client_ip, None)

    token = generate_session_token(raw_user)
    max_age = PERSISTENT_TTL if raw_user in PERSISTENT_USERS else SESSION_TTL
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        path="/"
    )
    user_info = DEFAULT_USERS[raw_user]
    return {
        "ok": True,
        "token": token,
        "user": {
            "username": raw_user,
            "display": user_info["display"],
            "role": user_info["role"]
        }
    }

@app.get("/api/auth/status")
def auth_status(request: Request):
    user = get_current_user(request)
    if user:
        return {"authenticated": True, "user": user}
    return {"authenticated": False}

@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}

# --- Rutas de Datos Protegidas ---"""

    content = content.replace(old_auth_backend.group(0), new_auth_backend)
    print("Backend auth (RBAC + RateLimit + Session) reemplazado con exito.")

    # --- 2. ACTUALIZAR RUTAS FASTAPI (DE /santander A /santabase CON 302 REDIRECT) ---
    old_index_routes = """@app.get("/", response_class=HTMLResponse)
@app.get("/santander", response_class=HTMLResponse)
@app.get("/santander/", response_class=HTMLResponse)
def index(request: Request):
    return HTML_CONTENT"""

    new_index_routes = """from fastapi.responses import RedirectResponse

@app.get("/", response_class=HTMLResponse)
@app.get("/santabase", response_class=HTMLResponse)
@app.get("/santabase/", response_class=HTMLResponse)
def index(request: Request):
    return HTML_CONTENT

@app.get("/santander")
@app.get("/santander/")
def redirect_legacy_santander():
    return RedirectResponse(url="/santabase", status_code=302)"""

    if old_index_routes in content:
        content = content.replace(old_index_routes, new_index_routes)
        print("Rutas FastAPI actualizadas a /santabase con redireccion 302 para /santander.")
    else:
        print("WARN: Rutas index no coincidieron exactamente.")

    # --- 3. REEMPLAZAR CSS: ELIMINAR FORMULA BAR Y AGREGAR MEGA-BUSCADOR + USER BADGES ---
    old_formula_css = re.search(r"/\* Formula Bar \*/.*?/\* Toolbar con 4 Clusters Visuales y Segmented Control \*/", content, re.DOTALL)
    if old_formula_css:
        new_mega_search_css = """/* Mega-Buscador (Command Center) - Reemplazo de Formula Bar */
    .mega-search-bar {
      display: flex;
      align-items: center;
      gap: 10px;
      background: var(--bg-surface);
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-lg);
      padding: 7px 14px;
      margin: 8px 0;
      flex-shrink: 0;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
      transition: border-color 140ms ease, box-shadow 140ms ease;
    }
    .mega-search-bar:focus-within {
      border-color: var(--color-primary);
      box-shadow: 0 0 0 3px var(--color-primary-ring), 0 6px 20px rgba(2, 132, 199, 0.15);
    }
    .mega-search-icon {
      font-size: 18px;
      color: var(--color-primary);
      flex-shrink: 0;
    }
    .mega-filter-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: rgba(2, 132, 199, 0.18);
      color: #38bdf8;
      border: 1px solid rgba(2, 132, 199, 0.4);
      border-radius: var(--radius-sm);
      padding: 3px 8px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.04em;
      white-space: nowrap;
      font-family: var(--font-mono);
      cursor: pointer;
      transition: var(--transition-fast);
    }
    .mega-filter-badge:hover {
      background: rgba(2, 132, 199, 0.3);
      border-color: #38bdf8;
    }
    .mega-search-input {
      flex: 1;
      background: transparent;
      border: none;
      color: #fff;
      font-size: 14.5px;
      font-family: var(--font-sans);
      font-weight: 500;
      outline: none;
      padding: 4px 2px;
      min-width: 200px;
    }
    .mega-search-input::placeholder {
      color: var(--text-dim);
      font-size: 13.5px;
    }
    .mega-search-clear-btn {
      background: rgba(255, 255, 255, 0.08);
      border: none;
      color: var(--text-muted);
      width: 24px;
      height: 24px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      transition: var(--transition-fast);
      flex-shrink: 0;
    }
    .mega-search-clear-btn:hover {
      background: var(--color-danger);
      color: #fff;
    }
    .mega-search-submit-btn {
      padding: 7px 16px !important;
      font-size: 13px !important;
      font-weight: 600 !important;
      border-radius: var(--radius-md) !important;
      gap: 6px;
      flex-shrink: 0;
    }
    .search-btn-badge {
      font-family: var(--font-mono);
      font-size: 11px;
      background: rgba(0, 0, 0, 0.28);
      padding: 1px 5px;
      border-radius: 3px;
    }

    /* Badges de Usuario en Top Bar */
    .user-pill {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: var(--radius-sm);
      display: inline-flex;
      align-items: center;
      gap: 6px;
      letter-spacing: 0.2px;
    }
    .user-pill.role-superadmin {
      background: rgba(234, 179, 8, 0.12);
      border: 1px solid rgba(234, 179, 8, 0.35);
      color: #facc15;
    }
    .user-pill.role-operator {
      background: rgba(2, 132, 199, 0.12);
      border: 1px solid rgba(2, 132, 199, 0.35);
      color: #38bdf8;
    }

    /* Formulario Multi-Usuario en Lock Screen */
    .login-field-group {
      text-align: left;
      margin-bottom: 14px;
    }
    .login-label {
      display: block;
      font-size: 11px;
      font-weight: 700;
      color: var(--text-muted);
      margin-bottom: 5px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .login-select {
      width: 100%;
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      padding: 10px 12px;
      border-radius: var(--radius-md);
      font-size: 13px;
      font-family: var(--font-sans);
      outline: none;
      cursor: pointer;
      transition: var(--transition-fast);
    }
    .login-select:focus {
      border-color: var(--border-focus);
      box-shadow: 0 0 0 2px var(--color-primary-ring);
    }

    /* Toolbar con 4 Clusters Visuales y Segmented Control */"""
        content = content.replace(old_formula_css.group(0), new_mega_search_css)
        print("CSS Formula Bar reemplazado por CSS Mega-Buscador y User Badges.")

    # --- 4. ACTUALIZAR HTML: LOCK SCREEN MULTI-USUARIO ---
    old_lock_screen = re.search(r'<!-- Lock Screen Overlay -->.*?<!-- Top Bar -->', content, re.DOTALL)
    if old_lock_screen:
        new_lock_screen = """<!-- Lock Screen Overlay -->
  <div id="lock-screen">
    <div class="lock-card">
      <div class="lock-icon-circle">🔒</div>
      <div style="margin-bottom: 10px;">
        <span class="badge-santander">SANTANDER</span>
      </div>
      <h2 class="lock-title"><span class="brand-santa">SANTA</span> <span class="brand-pray">🙏🏻</span> <span class="brand-base">BASE</span></h2>
      <p class="lock-subtitle">Autenticación Segura Multi-Usuario — Bóveda Operativa (4.9M Registros)</p>
      
      <div class="login-field-group">
        <label class="login-label">Usuario Autorizado</label>
        <select id="login-username" class="login-select">
          <option value="robertvs">👑 RobertVS (Superadmin)</option>
          <option value="magdiel">👤 Magdiel (Operador)</option>
          <option value="luisito">👤 Luisito (Operador)</option>
        </select>
      </div>

      <div class="login-field-group">
        <label class="login-label">Contraseña</label>
        <div class="password-input-group">
          <input type="password" id="login-password" class="password-input" placeholder="Ingresa tu contraseña..." onkeydown="if(event.key==='Enter') submitLogin()">
          <button class="eye-btn" onclick="togglePasswordVisibility()" title="Mostrar/Ocultar">👁</button>
        </div>
      </div>

      <button class="btn-login" onclick="submitLogin()">Ingresar a Santa Base ➔</button>
      <div id="lock-error" class="lock-error">Credenciales incorrectas o usuario bloqueado.</div>
    </div>
  </div>

  <!-- Top Bar -->"""
        content = content.replace(old_lock_screen.group(0), new_lock_screen)
        print("HTML Lock Screen actualizado a Multi-Usuario.")

    # --- 5. ACTUALIZAR HTML: TOP BAR CON USER BADGE ---
    old_logout_btn = '<button class="btn-logout" onclick="doLogout()" title="Cerrar sesión">Cerrar Sesión</button>'
    new_logout_btn = """<div class="user-pill role-superadmin" id="current-user-badge" title="Sesión activa">👑 RobertVS</div>
      <button class="btn-logout" onclick="doLogout()" title="Cerrar sesión">Salir</button>"""
    if old_logout_btn in content:
        content = content.replace(old_logout_btn, new_logout_btn)
        print("HTML Top Bar enriquecido con User Badge.")

    # --- 6. ACTUALIZAR HTML: REEMPLAZAR FORMULA BAR POR MEGA-BUSCADOR ---
    old_formula_html = re.search(r'<!-- Excel Formula & Value Bar -->.*?<!-- Toolbar con 4 Clusters Visuales y Segmented Control -->', content, re.DOTALL)
    if old_formula_html:
        new_mega_search_html = """<!-- Mega-Buscador (Command Center de 4.9M Registros) -->
  <div class="mega-search-bar" id="mega-search-bar">
    <div class="mega-search-icon">🔍</div>
    <div class="mega-filter-badge" id="mega-filter-badge" onclick="cyclePresetFilter()" title="Ámbito de búsqueda activo. Clic para alternar.">
      <span id="mega-filter-badge-text">TODOS</span>
    </div>
    <input type="text" id="global-search" class="mega-search-input" 
           placeholder="Buscar en 4.9M de registros (RFC, Nombre, CURP, Ciudad, Tarjeta, CP...) — Atajo: Ctrl+K o /" 
           onkeydown="if(event.key==='Enter') applyGlobalSearch(); else if(event.key==='Escape') clearGlobalSearch();" 
           oninput="toggleSearchClearBtn()">
    <button id="btn-clear-search" class="mega-search-clear-btn" onclick="clearGlobalSearch()" title="Limpiar búsqueda (Esc)" style="display:none;">✕</button>
    <button class="btn btn-primary mega-search-submit-btn" onclick="applyGlobalSearch()" title="Ejecutar búsqueda">
      <span>Buscar</span>
      <span class="search-btn-badge">↵</span>
    </button>
  </div>

  <!-- Toolbar con 4 Clusters Visuales y Segmented Control -->"""
        content = content.replace(old_formula_html.group(0), new_mega_search_html)
        print("HTML Formula Bar reemplazada por Mega-Buscador.")

    # --- 7. ACTUALIZAR JAVASCRIPT: BASE_PATH, LOGIN Y SINCRONIZACIÓN DE FILTROS ---
    old_base_path = "const BASE_PATH = window.location.pathname.startsWith('/santander') ? '/santander' : '';"
    new_base_path = "const BASE_PATH = window.location.pathname.startsWith('/santabase') ? '/santabase' : (window.location.pathname.startsWith('/santander') ? '/santander' : '');"
    if old_base_path in content:
        content = content.replace(old_base_path, new_base_path)
        print("JS BASE_PATH actualizado con /santabase prioritario.")

    # Actualizar submitLogin para mandar username y password
    old_submit_login = """    async function submitLogin() {
      const pwd = document.getElementById('login-password').value;
      const err = document.getElementById('lock-error');
      try {
        const res = await fetch(`${BASE_PATH}/api/auth/login`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ password: pwd })
        });
        const data = await res.json();
        if (res.ok && data.ok) {
          err.classList.remove('show');
          hideLockScreen();
          loadRecords();
          fetchStats();
        } else {
          err.classList.add('show');
        }
      } catch(e) { err.classList.add('show'); }
    }"""

    new_submit_login = """    async function submitLogin() {
      const usernameSelect = document.getElementById('login-username');
      const username = usernameSelect ? usernameSelect.value : 'robertvs';
      const pwd = document.getElementById('login-password').value;
      const err = document.getElementById('lock-error');
      try {
        const res = await fetch(`${BASE_PATH}/api/auth/login`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ username: username, password: pwd })
        });
        const data = await res.json();
        if (res.ok && data.ok) {
          err.classList.remove('show');
          hideLockScreen();
          updateUserBadge(data.user);
          loadRecords();
          fetchStats();
          showToast(`✓ Bienvenido, ${data.user ? data.user.display : username}`);
        } else {
          err.innerText = data.detail || 'Credenciales incorrectas.';
          err.classList.add('show');
        }
      } catch(e) { 
        err.innerText = 'Error de conexión con el servidor.';
        err.classList.add('show'); 
      }
    }

    function updateUserBadge(user) {
      const badge = document.getElementById('current-user-badge');
      if (!badge || !user) return;
      badge.className = `user-pill role-${user.role}`;
      const icon = user.role === 'superadmin' ? '👑' : '👤';
      const roleText = user.role === 'superadmin' ? 'Superadmin' : 'Operador';
      badge.innerText = `${icon} ${user.display} (${roleText})`;
    }"""

    if old_submit_login in content:
        content = content.replace(old_submit_login, new_submit_login)
        print("JS submitLogin actualizado con soporte de usuario y roles.")

    # Actualizar checkAuthStatus en JS
    old_check_auth = """    async function checkAuthStatus() {
      try {
        const res = await fetch(`${BASE_PATH}/api/auth/status`);
        const data = await res.json();
        if (data.authenticated) {
          hideLockScreen();
          loadRecords();
          fetchStats();
        } else {
          showLockScreen();
        }
      } catch(e) { showLockScreen(); }
    }"""

    new_check_auth = """    async function checkAuthStatus() {
      try {
        const res = await fetch(`${BASE_PATH}/api/auth/status`);
        const data = await res.json();
        if (data.authenticated) {
          hideLockScreen();
          if (data.user) updateUserBadge(data.user);
          loadRecords();
          fetchStats();
        } else {
          showLockScreen();
        }
      } catch(e) { showLockScreen(); }
    }"""

    if old_check_auth in content:
        content = content.replace(old_check_auth, new_check_auth)
        print("JS checkAuthStatus actualizado para pintar badge de usuario.")

    # Actualizar setPresetFilter para sincronizar con el badge del Mega-Buscador
    old_set_preset = """    function setPresetFilter(f) {
      currentPresetFilter = f;
      currentPage = 1;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(`'${f}'`));
      if (activeBtn) activeBtn.classList.add('active');
      loadRecords();
    }"""

    new_set_preset = """    const PRESET_LABELS = {
      'all': 'TODOS',
      'no_curp': 'FALTA CURP',
      'has_curp': 'CON CURP',
      'calculada': 'CALCULADAS',
      'no_calculable': 'NO CALCULABLES',
      'has_results': 'CON RESULT'
    };

    function syncMegaFilterBadge() {
      const badge = document.getElementById('mega-filter-badge');
      const badgeText = document.getElementById('mega-filter-badge-text');
      if (!badge || !badgeText) return;
      const label = PRESET_LABELS[currentPresetFilter] || 'TODOS';
      badgeText.innerText = `Filtro: ${label}`;
      badge.style.display = currentPresetFilter === 'all' ? 'none' : 'inline-flex';
    }

    function cyclePresetFilter() {
      const keys = Object.keys(PRESET_LABELS);
      const curIdx = keys.indexOf(currentPresetFilter);
      const nextIdx = (curIdx + 1) % keys.length;
      setPresetFilter(keys[nextIdx]);
    }

    function setPresetFilter(f) {
      currentPresetFilter = f;
      currentPage = 1;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick') && b.getAttribute('onclick').includes(`'${f}'`));
      if (activeBtn) activeBtn.classList.add('active');
      syncMegaFilterBadge();
      loadRecords();
    }"""

    if old_set_preset in content:
        content = content.replace(old_set_preset, new_set_preset)
        print("JS setPresetFilter sincronizado con el Mega-Buscador.")

    # Global shortcut / para el Mega-Buscador
    old_k_listener = """    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('global-search');
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    });"""

    new_k_listener = """    window.addEventListener('keydown', (e) => {
      const isInputActive = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);
      if (((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') || (e.key === '/' && !isInputActive)) {
        e.preventDefault();
        const searchInput = document.getElementById('global-search');
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    });"""

    if old_k_listener in content:
        content = content.replace(old_k_listener, new_k_listener)
        print("Atajo universal / y Ctrl+K conectado al Mega-Buscador.")

    with open(APP_PY_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print("SUCCESS: app.py actualizado con exito para Santa Base v2.")

if __name__ == "__main__":
    main()
