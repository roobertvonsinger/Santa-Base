import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Ensure `app = FastAPI(...)` and middleware are present
app_def = '''# ── Inicialización FastAPI & Middlewares de Seguridad ─────────────────────
app = FastAPI(
    title="Santa Base — Santander DB Pro Grid",
    description="Motor soberano de consulta y gestión para 4.9M de registros",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

@app.middleware("http")
async def security_and_routing_middleware(request: Request, call_next):
    path = request.url.path
    # 1. Blindaje anti-directory-traversal y bypass de subdirectorios
    if ".." in path or "//" in path or "\\\\" in path or "/." in path:
        return RawResponse(content="Acceso denegado: ruta no permitida", status_code=400)
    
    # 2. Reescritura transparente de /santabase/api/ -> /api/
    if path.startswith("/santabase/api/"):
        request.scope["path"] = path.replace("/santabase", "", 1)
        
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

'''

if "app = FastAPI" not in content:
    content = content.replace(
        '# ── Multi-User RBAC & Authentication (Modelo Botmex Blindado) ──────────────',
        app_def + '# ── Multi-User RBAC & Authentication (Modelo Botmex Blindado) ──────────────'
    )

# 2. Fix token == AUTH_PASSWORD in get_current_user
old_token_auth = '''        if token == AUTH_PASSWORD:
            return DEFAULT_USERS["robertvs"]'''
new_token_auth = '''        if token == AUTH_PASSWORD:
            return {"username": "robertvs", **DEFAULT_USERS["robertvs"]}'''
content = content.replace(old_token_auth, new_token_auth)

# 3. Remove duplicate small search bar inside .toolbar
old_toolbar_search = '''      <div class="search-input-wrap">
        <input type="text" id="global-search" class="global-search" placeholder="🔍 Buscar RFC, Nombre... (Ctrl+K)" onkeydown="if(event.key==='Enter') applyGlobalSearch()" oninput="toggleSearchClearBtn()">
        <button id="btn-clear-search" class="search-clear-btn" onclick="clearGlobalSearch()" title="Limpiar búsqueda" style="display:none;">✕</button>
      </div>
      <button class="btn btn-primary" onclick="applyGlobalSearch()">Buscar</button>'''

if old_toolbar_search in content:
    content = content.replace(old_toolbar_search, '')

# Also remove comment reference if present
content = content.replace(
    '<!-- 1. Búsqueda y Filtros Predefinidos (Segmented Control) -->',
    '<!-- 1. Filtros Predefinidos (Segmented Control) -->'
)

# 4. JS: Replace checkSession, submitLogin, doLogout, updateUserBadge, syncMegaFilterBadge
old_auth_js = '''    checkSession();

    async function checkSession() {
      try {
        const res = await fetch(`${BASE_PATH}/api/auth/status`);
        const data = await res.json();
        if (data.authenticated) {
          hideLockScreen();
          initApp();
        } else {
          showLockScreen();
        }
      } catch(e) {
        showLockScreen();
      }
    }

    function showLockScreen() {
      document.getElementById('lock-screen').classList.remove('hidden');
      setTimeout(() => document.getElementById('login-password')?.focus(), 100);
    }

    function hideLockScreen() {
      document.getElementById('lock-screen').classList.add('hidden');
    }

    function togglePasswordVisibility() {
      const input = document.getElementById('login-password');
      input.type = input.type === 'password' ? 'text' : 'password';
    }

    async function submitLogin() {
      const pass = document.getElementById('login-password').value.trim();
      const errElem = document.getElementById('lock-error');
      errElem.classList.remove('show');

      if (!pass) {
        errElem.innerText = 'Ingresa la contraseña';
        errElem.classList.add('show');
        return;
      }

      try {
        const res = await fetch(`${BASE_PATH}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: pass })
        });
        if (res.ok) {
          hideLockScreen();
          initApp();
          showToast('¡Bóveda desbloqueada con éxito!');
        } else {
          errElem.innerText = 'Contraseña incorrecta';
          errElem.classList.add('show');
          document.getElementById('login-password').select();
        }
      } catch(e) {
        errElem.innerText = 'Error de conexión con el servidor';
        errElem.classList.add('show');
      }
    }

    async function doLogout() {
      await fetch(`${BASE_PATH}/api/auth/logout`, { method: 'POST' });
      document.getElementById('login-password').value = '';
      showLockScreen();
    }'''

new_auth_js = '''    let currentUser = null;

    function updateUserBadge(user) {
      const badge = document.getElementById('current-user-badge');
      if (!badge) return;
      if (!user) {
        badge.style.display = 'none';
        return;
      }
      badge.style.display = 'inline-flex';
      const roleClass = user.role === 'superadmin' ? 'role-superadmin' : 'role-operator';
      badge.className = `user-pill ${roleClass}`;
      const icon = user.role === 'superadmin' ? '👑' : '👤';
      badge.innerHTML = `${icon} ${user.display || user.username}`;
      badge.title = `Sesión activa: ${user.display || user.username} (${(user.role || 'usuario').toUpperCase()})`;
    }

    checkSession();

    async function checkSession() {
      try {
        const res = await fetch(`${BASE_PATH}/api/auth/status`);
        const data = await res.json();
        if (data.authenticated) {
          currentUser = data.user;
          updateUserBadge(currentUser);
          hideLockScreen();
          initApp();
        } else {
          showLockScreen();
        }
      } catch(e) {
        showLockScreen();
      }
    }

    function showLockScreen() {
      document.getElementById('lock-screen').classList.remove('hidden');
      setTimeout(() => document.getElementById('login-password')?.focus(), 100);
    }

    function hideLockScreen() {
      document.getElementById('lock-screen').classList.add('hidden');
    }

    function togglePasswordVisibility() {
      const input = document.getElementById('login-password');
      input.type = input.type === 'password' ? 'text' : 'password';
    }

    async function submitLogin() {
      const username = document.getElementById('login-username')?.value || 'robertvs';
      const pass = document.getElementById('login-password').value.trim();
      const errElem = document.getElementById('lock-error');
      errElem.classList.remove('show');

      if (!pass) {
        errElem.innerText = 'Ingresa la contraseña';
        errElem.classList.add('show');
        return;
      }

      try {
        const res = await fetch(`${BASE_PATH}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: username, password: pass })
        });
        const data = await res.json();
        if (res.ok && data.authenticated) {
          currentUser = data.user;
          updateUserBadge(currentUser);
          hideLockScreen();
          initApp();
          showToast(`¡Bóveda desbloqueada como ${data.user?.display || username}!`);
        } else {
          errElem.innerText = data.detail || data.error || 'Credenciales incorrectas o usuario bloqueado';
          errElem.classList.add('show');
          document.getElementById('login-password').select();
        }
      } catch(e) {
        errElem.innerText = 'Error de conexión con el servidor';
        errElem.classList.add('show');
      }
    }

    async function doLogout() {
      await fetch(`${BASE_PATH}/api/auth/logout`, { method: 'POST' });
      currentUser = null;
      updateUserBadge(null);
      document.getElementById('login-password').value = '';
      showLockScreen();
    }'''

content = content.replace(old_auth_js, new_auth_js)

# 5. Fix formula input null safety
old_active_cell = '''      const coordBox = document.getElementById('cell-coord');
      coordBox.innerText = `${col.letter}${activeRowIndex + 1} (${col.label})`;

      const formulaInput = document.getElementById('formula-input');
      formulaInput.value = rawVal;

      if (col.editable) {
        formulaInput.readOnly = false;
        formulaInput.classList.remove('readonly');
        formulaInput.placeholder = "Editar CURP y presionar Enter...";
      } else {
        formulaInput.readOnly = true;
        formulaInput.classList.add('readonly');
        formulaInput.placeholder = "🔒 Campo de solo lectura";
      }'''

new_active_cell = '''      const coordBox = document.getElementById('cell-coord');
      if (coordBox) coordBox.innerText = `${col.letter}${activeRowIndex + 1} (${col.label})`;

      const formulaInput = document.getElementById('formula-input');
      if (formulaInput) {
        formulaInput.value = rawVal;
        if (col.editable) {
          formulaInput.readOnly = false;
          formulaInput.classList.remove('readonly');
          formulaInput.placeholder = "Editar CURP y presionar Enter...";
        } else {
          formulaInput.readOnly = true;
          formulaInput.classList.add('readonly');
          formulaInput.placeholder = "🔒 Campo de solo lectura";
        }
      }'''

content = content.replace(old_active_cell, new_active_cell)

old_formula_setup = '''    function setupFormulaBarListener() {
      const formulaInput = document.getElementById('formula-input');
      formulaInput.addEventListener('keydown', (e) => {'''

new_formula_setup = '''    function setupFormulaBarListener() {
      const formulaInput = document.getElementById('formula-input');
      if (!formulaInput) return;
      formulaInput.addEventListener('keydown', (e) => {'''

content = content.replace(old_formula_setup, new_formula_setup)

content = content.replace(
    "document.getElementById('formula-input').value = newVal;",
    "const fInput = document.getElementById('formula-input'); if (fInput) fInput.value = newVal;"
)

# 6. Filter tabs and Mega-search sync
old_preset_filter = '''    function setPresetFilter(f) {
      currentPresetFilter = f;
      currentPage = 1;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      event.target.classList.add('active');
      loadRecords();
    }'''

new_preset_filter = '''    const PRESET_LABELS = {
      'all': 'TODOS',
      'no_curp': 'FALTA CURP',
      'has_curp': 'CON CURP',
      'calculada': 'CALCULADAS',
      'no_calculable': 'NO CALCULABLES',
      'has_results': 'CON RESULT'
    };
    const PRESET_KEYS = ['all', 'no_curp', 'has_curp', 'calculada', 'no_calculable', 'has_results'];

    function syncMegaFilterBadge() {
      const badgeText = document.getElementById('mega-filter-badge-text');
      if (badgeText) {
        badgeText.textContent = PRESET_LABELS[currentPresetFilter] || currentPresetFilter.toUpperCase();
      }
    }

    function cyclePresetFilter() {
      const idx = PRESET_KEYS.indexOf(currentPresetFilter);
      const nextIdx = (idx + 1) % PRESET_KEYS.length;
      setPresetFilter(PRESET_KEYS[nextIdx]);
    }

    function setPresetFilter(f) {
      currentPresetFilter = f;
      currentPage = 1;
      document.querySelectorAll('.tab-btn').forEach(b => {
        if (b.getAttribute('onclick')?.includes(`'${f}'`)) {
          b.classList.add('active');
        } else {
          b.classList.remove('active');
        }
      });
      syncMegaFilterBadge();
      loadRecords();
    }'''

content = content.replace(old_preset_filter, new_preset_filter)

# In initApp, add syncMegaFilterBadge()
content = content.replace(
    'buildHeaderRow();\n      fetchStats();',
    'syncMegaFilterBadge();\n      buildHeaderRow();\n      fetchStats();'
)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("[✓] app.py actualizado exitosamente!")
