import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Define DB_COLUMNS
db_columns_def = '''# ── Definición Canónica de Columnas de Base de Datos ─────────────────────
DB_COLUMNS = [
    "id", "u6rfc", "curp", "curp_status", "curp_falta", "dmname", "genero", "fecha_nacimiento",
    "ciudad", "estado", "codigo_postal", "results", "u6acct", "u6cvereg", "u6numcto",
    "dmssnum", "dmaddr1", "dmaddr2", "u6delomu", "u6estado", "dmcity", "dmzip",
    "u6ladte1", "u6tel1", "u6ladte2", "u6tel2", "u6licrea"
]

'''

if "DB_COLUMNS = [" not in content:
    content = content.replace(
        '# ── Multi-User RBAC & Authentication (Modelo Botmex Blindado) ──────────────',
        db_columns_def + '# ── Multi-User RBAC & Authentication (Modelo Botmex Blindado) ──────────────'
    )

# 2. Update DEFAULT_USERS & DEFAULT_PASSWORDS to Case-Sensitive Capitalized Keys
old_users = '''DEFAULT_USERS: dict[str, dict] = {
    "robertvs": {"display": "RobertVS", "telegram_id": 1341812706, "role": "superadmin"},
    "magdiel":  {"display": "Magdiel",  "telegram_id": 1059367082, "role": "operator"},
    "luisito":  {"display": "Luisito",  "telegram_id": 7847239854, "role": "operator"},
}

DEFAULT_PASSWORDS: dict[str, str] = {
    "robertvs": "d677aa73ca12341112367842164dd250136718a8885b901edd2cfe8474c630eb",
    "magdiel":  "4e93ba3f4dd91e3cfd4cbdeabf660839380442e9108da0efd010395e56a05a02",
    "luisito":  "4e93ba3f4dd91e3cfd4cbdeabf660839380442e9108da0efd010395e56a05a02",
}'''

new_users = '''DEFAULT_USERS: dict[str, dict] = {
    "Robertvs": {"display": "RobertVS", "telegram_id": 1341812706, "role": "superadmin"},
    "Magdiel":  {"display": "Magdiel",  "telegram_id": 1059367082, "role": "operator"},
    "Luisito":  {"display": "Luisito",  "telegram_id": 7847239854, "role": "operator"},
}

DEFAULT_PASSWORDS: dict[str, str] = {
    "Robertvs": "d677aa73ca12341112367842164dd250136718a8885b901edd2cfe8474c630eb",
    "Magdiel":  "4e93ba3f4dd91e3cfd4cbdeabf660839380442e9108da0efd010395e56a05a02",
    "Luisito":  "4e93ba3f4dd91e3cfd4cbdeabf660839380442e9108da0efd010395e56a05a02",
}'''

content = content.replace(old_users, new_users)

content = content.replace('PERSISTENT_USERS = {"robertvs"}', 'PERSISTENT_USERS = {"Robertvs"}')

# 3. Update verify_session_token (remove .lower())
old_verify = '''        username, timestamp_str, signature = token.split(":", 2)
        username = username.strip().lower()
        if username not in DEFAULT_USERS:'''

new_verify = '''        username, timestamp_str, signature = token.split(":", 2)
        username = username.strip()
        if username not in DEFAULT_USERS:'''

content = content.replace(old_verify, new_verify)

# Update get_current_user fallback
content = content.replace(
    'return {"username": "robertvs", **DEFAULT_USERS["robertvs"]}',
    'return {"username": "Robertvs", **DEFAULT_USERS["Robertvs"]}'
)

# 4. Update LoginPayload and login endpoint
old_payload = '''class LoginPayload(BaseModel):
    username: Optional[str] = "robertvs"
    password: str'''

new_payload = '''class LoginPayload(BaseModel):
    username: Optional[str] = None
    password: str'''

content = content.replace(old_payload, new_payload)

old_login_func = '''@app.post("/api/auth/login")
def login(payload: LoginPayload, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    raw_user = (payload.username or "robertvs").strip().lower()
    password = payload.password.strip()

    if raw_user not in DEFAULT_USERS:
        record_failed_attempt(client_ip)
        raise HTTPException(status_code=401, detail="Usuario no autorizado")'''

new_login_func = '''@app.post("/api/auth/login")
def login(payload: LoginPayload, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    raw_user = (payload.username or "").strip()
    password = payload.password.strip()

    if not raw_user:
        record_failed_attempt(client_ip)
        raise HTTPException(status_code=400, detail="Debes escribir tu nombre de usuario")

    # Validación estricta: primera letra obligatoriamente mayúscula y case-sensitive
    if not raw_user[0].isupper():
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=400,
            detail="La primera letra del usuario debe ser mayúscula obligatoriamente (ej. Robertvs, Magdiel, Luisito)"
        )

    if raw_user not in DEFAULT_USERS:
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=401,
            detail="Usuario no autorizado o formato incorrecto (sensible a mayúsculas/minúsculas)"
        )'''

content = content.replace(old_login_func, new_login_func)

# 5. Lock Screen CSS: styling for .login-input and .login-hint
old_login_css = '''    /* Formulario Multi-Usuario en Lock Screen */
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
    }'''

new_login_css = '''    /* Formulario Multi-Usuario en Lock Screen (Input de Texto Estricto) */
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
    .login-input {
      width: 100%;
      background: #09090e;
      border: 1px solid var(--border-strong);
      color: #ffffff;
      padding: 10px 14px;
      border-radius: var(--radius-md);
      font-size: 13.5px;
      font-family: var(--font-sans);
      font-weight: 500;
      outline: none;
      transition: all 180ms ease;
      box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.4);
    }
    .login-input:focus {
      border-color: var(--color-primary);
      box-shadow: 0 0 0 2px var(--color-primary-ring), inset 0 2px 4px rgba(0, 0, 0, 0.4);
    }
    .login-hint {
      display: block;
      font-size: 10.5px;
      color: var(--text-dim);
      margin-top: 5px;
      font-family: var(--font-mono);
      letter-spacing: 0.02em;
    }'''

content = content.replace(old_login_css, new_login_css)

# 6. Lock Screen HTML: Replace <select> with <input>
old_lock_select = '''      <div class="login-field-group">
        <label class="login-label">Usuario Autorizado</label>
        <select id="login-username" class="login-select">
          <option value="robertvs">👑 RobertVS (Superadmin)</option>
          <option value="magdiel">👤 Magdiel (Operador)</option>
          <option value="luisito">👤 Luisito (Operador)</option>
        </select>
      </div>'''

new_lock_input = '''      <div class="login-field-group">
        <label class="login-label">Usuario</label>
        <input type="text" id="login-username" class="login-input" 
               placeholder="Escribe tu usuario (ej. Robertvs)..." 
               autocomplete="username" autocapitalize="words" spellcheck="false"
               onkeydown="if(event.key==='Enter') document.getElementById('login-password')?.focus()">
        <span class="login-hint">🔒 Sensible a mayúsculas. La 1ra letra debe ser Mayúscula.</span>
      </div>'''

content = content.replace(old_lock_select, new_lock_input)

# 7. JavaScript: Update submitLogin, showLockScreen, doLogout
old_submit_login = '''    async function submitLogin() {
      const username = document.getElementById('login-username')?.value || 'robertvs';
      const pass = document.getElementById('login-password').value.trim();
      const errElem = document.getElementById('lock-error');
      errElem.classList.remove('show');

      if (!pass) {
        errElem.innerText = 'Ingresa la contraseña';
        errElem.classList.add('show');
        return;
      }'''

new_submit_login = '''    async function submitLogin() {
      const usernameInput = document.getElementById('login-username');
      const username = usernameInput ? usernameInput.value.trim() : '';
      const pass = document.getElementById('login-password').value.trim();
      const errElem = document.getElementById('lock-error');
      errElem.classList.remove('show');

      if (!username) {
        errElem.innerText = 'Escribe tu usuario';
        errElem.classList.add('show');
        usernameInput?.focus();
        return;
      }

      if (!/^[A-ZÁÉÍÓÚÑ]/.test(username)) {
        errElem.innerText = 'La primera letra del usuario DEBE ser Mayúscula (ej. Robertvs)';
        errElem.classList.add('show');
        usernameInput?.focus();
        return;
      }

      if (!pass) {
        errElem.innerText = 'Ingresa la contraseña';
        errElem.classList.add('show');
        document.getElementById('login-password')?.focus();
        return;
      }'''

content = content.replace(old_submit_login, new_submit_login)

content = content.replace(
    "setTimeout(() => document.getElementById('login-password')?.focus(), 100);",
    "setTimeout(() => document.getElementById('login-username')?.focus(), 100);"
)

content = content.replace(
    "document.getElementById('login-password').value = '';\n      showLockScreen();",
    "if (document.getElementById('login-password')) document.getElementById('login-password').value = '';\n      if (document.getElementById('login-username')) document.getElementById('login-username').value = '';\n      showLockScreen();"
)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] app.py updated with DB_COLUMNS and Strict Capitalized Username Input!")
