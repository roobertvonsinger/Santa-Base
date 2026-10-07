#!/usr/bin/env python3
"""
Visor y Gestor Interactivo Excel-Pro para la Base de Datos Santander (4.9M registros).
- Autenticación por contraseña única (Password: "Santabase").
- Solo el campo 'curp' es editable. Los demás campos son de solo lectura.
- Dirección combinada en "DIRECCIÓN COMPLETA" + Columnas atómicas (CIUDAD, ESTADO, CP).
- Controles de celda interactivos estilo Excel (navegación por teclado, flechas, tab, enter).
- Barra de fórmulas / valor (fx) sincronizada en tiempo real.
- Filtros inteligentes en encabezados de cada columna (búsqueda, texto, vacíos/no vacíos, orden A-Z / Z-A).
- Portapapeles (Ctrl+C, Ctrl+V), menú contextual y exportación CSV.
- Puerto: 8055
"""

import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import subprocess
import time
from typing import Any, Optional
from fastapi import FastAPI, Query, HTTPException, Request, Response, Depends
from fastapi.responses import HTMLResponse, JSONResponse, Response as RawResponse
from pydantic import BaseModel
import uvicorn
from santander_runner import check_single_curp, format_short_reason


DB_PATH = os.environ.get("SANTANDER_DB_PATH") or os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "santander.db"))
if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) < 1000000:
    for c in [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "santander.db")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "santander.db")),
        r"C:\Users\rober\Dropbox\TESTING DEV\data\santander.db",
        "/opt/kvm4/apps/santander/data/santander.db",
    ]:
        if os.path.exists(c) and os.path.getsize(c) > 1000000:
            DB_PATH = c
            break

# ── Inicialización FastAPI & Middlewares de Seguridad ─────────────────────
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
    if ".." in path or "//" in path or "\\" in path or "/." in path:
        return RawResponse(content="Acceso denegado: ruta no permitida", status_code=400)
    
    # 2. Reescritura transparente de /santabase/api/ -> /api/
    if path.startswith("/santabase/api/"):
        request.scope["path"] = path.replace("/santabase", "", 1)
        
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# ── Definición Canónica de Columnas de Base de Datos ─────────────────────
DB_COLUMNS = [
    "id", "u6rfc", "curp", "curp_status", "curp_falta", "dmname", "genero", "fecha_nacimiento",
    "ciudad", "estado", "codigo_postal", "results", "u6acct", "u6cvereg", "u6numcto",
    "dmssnum", "dmaddr1", "dmaddr2", "u6delomu", "u6estado", "dmcity", "dmzip",
    "u6ladte1", "u6tel1", "u6ladte2", "u6tel2", "u6licrea"
]

# ── Multi-User RBAC & Authentication (Modelo Botmex Blindado) ──────────────
DEFAULT_USERS: dict[str, dict] = {
    "Robertvs": {"display": "RobertVS", "telegram_id": 1341812706, "role": "superadmin"},
    "Magdiel":  {"display": "Magdiel",  "telegram_id": 1059367082, "role": "operator"},
    "Luisito":  {"display": "Luisito",  "telegram_id": 7847239854, "role": "operator"},
}

DEFAULT_PASSWORDS: dict[str, str] = {
    "Robertvs": "d677aa73ca12341112367842164dd250136718a8885b901edd2cfe8474c630eb",
    "Magdiel":  "4e93ba3f4dd91e3cfd4cbdeabf660839380442e9108da0efd010395e56a05a02",
    "Luisito":  "4e93ba3f4dd91e3cfd4cbdeabf660839380442e9108da0efd010395e56a05a02",
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
PERSISTENT_USERS = {"Robertvs"}  # Sesión persistente para Superadmin
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
        username = username.strip()
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
            return {"username": "Robertvs", **DEFAULT_USERS["Robertvs"]}
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
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA mmap_size = 2147483648;")
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS santander_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            u6rfc TEXT, curp TEXT, curp_status TEXT, curp_falta TEXT, dmname TEXT,
            genero TEXT, fecha_nacimiento TEXT, ciudad TEXT, estado TEXT, codigo_postal TEXT,
            results TEXT, u6acct TEXT, u6cvereg TEXT, u6numcto TEXT, dmssnum TEXT,
            dmaddr1 TEXT, dmaddr2 TEXT, u6delomu TEXT, u6estado TEXT, dmcity TEXT,
            dmzip TEXT, u6ladte1 TEXT, u6tel1 TEXT, u6ladte2 TEXT, u6tel2 TEXT, u6licrea TEXT
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS santander_hits (
            id INTEGER PRIMARY KEY,
            u6acct TEXT,
            curp TEXT NOT NULL UNIQUE,
            u6rfc TEXT,
            dmname TEXT,
            estado TEXT,
            ciudad TEXT,
            codigo_postal TEXT,
            u6licrea TEXT,
            fecha_nacimiento TEXT,
            genero TEXT,
            direccion TEXT,
            work_status TEXT DEFAULT 'ACTIVE',
            operador TEXT,
            notas TEXT,
            card_verified INTEGER DEFAULT 0,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hits_status ON santander_hits(work_status);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hits_edo ON santander_hits(estado);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hits_checked ON santander_hits(checked_at);")
    return conn

def get_total_records_count(conn):
    global TOTAL_RECORDS_CACHE
    if TOTAL_RECORDS_CACHE is None:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM santander_records")
        TOTAL_RECORDS_CACHE = cur.fetchone()[0]
    return TOTAL_RECORDS_CACHE

class LoginPayload(BaseModel):
    username: Optional[str] = None
    password: str

class UpdateRecordPayload(BaseModel):
    curp: Optional[str] = None
    results: Optional[str] = None
    field: Optional[str] = None
    value: Optional[str] = None
    updates: Optional[dict[str, Any]] = None

class UpdateHitPayload(BaseModel):
    work_status: Optional[str] = None
    operador: Optional[str] = None
    notas: Optional[str] = None

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
        )

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
        "authenticated": True,
        "token": token,
        "user": {
            "username": raw_user,
            "display": user_info["display"],
            "role": user_info["role"]
        }
    }

@app.get("/static/anime.min.js")
def get_anime_js():
    static_file = os.path.join(os.path.dirname(__file__), "static", "anime.min.js")
    if os.path.exists(static_file):
        with open(static_file, "r", encoding="utf-8") as f:
            return RawResponse(content=f.read(), media_type="application/javascript")
    return RawResponse(content="", status_code=404)

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

# --- Rutas de Datos Protegidas ---

@app.get("/api/stats")
def get_stats(_: None = Depends(require_auth)):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM santander_records")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM santander_records WHERE curp IS NOT NULL AND TRIM(curp) != ''")
        with_curp = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM santander_records WHERE curp_status = 'calculada'")
        curp_calculada = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM santander_records WHERE curp_status = 'no_calculable'")
        curp_no_calculable = cur.fetchone()[0]
        curp_existente = with_curp - curp_calculada if with_curp >= curp_calculada else 0
        cur.execute("SELECT COUNT(*) FROM santander_records WHERE results IS NOT NULL AND TRIM(results) != ''")
        with_results = cur.fetchone()[0]
        try:
            cur.execute("SELECT COUNT(*) FROM santander_hits")
            hits_total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM santander_hits WHERE work_status = 'ACTIVE'")
            hits_active = cur.fetchone()[0]
        except Exception:
            hits_total = 0
            hits_active = 0
        return {
            "total": total,
            "with_curp": with_curp,
            "curp_calculada": curp_calculada,
            "curp_existente": curp_existente,
            "curp_no_calculable": curp_no_calculable,
            "with_results": with_results,
            "without_curp": total - with_curp,
            "hits_total": hits_total,
            "hits_active": hits_active
        }
    finally:
        conn.close()

@app.get("/api/records")
def get_records(
    page: int = Query(1, ge=1),
    limit: int = Query(200, ge=10, le=500),
    filter: str = Query("all"),
    search: Optional[str] = None,
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc"),
    col_filters: Optional[str] = None,
    _: None = Depends(require_auth)
):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        where_clauses = []
        params = []
        
        # Filter out records where birth year is before 1963.
        # Aligned with purger BORN_AFTER_DEFAULT = "1963-01-01".
        # Year < 1963 means RFC YY (chars 5-6) is between '27' and '62'.
        where_clauses.append("(SUBSTR(u6rfc, 5, 2) NOT BETWEEN '27' AND '62' OR LENGTH(u6rfc) < 6)")

        if filter == "no_curp":
            where_clauses.append("(curp IS NULL OR TRIM(curp) = '')")
        elif filter == "has_curp":
            where_clauses.append("(curp IS NOT NULL AND TRIM(curp) != '')")
        elif filter == "calculada":
            where_clauses.append("curp_status = 'calculada'")
        elif filter == "no_calculable":
            where_clauses.append("curp_status = 'no_calculable'")
        elif filter == "no_results":
            where_clauses.append("(results IS NULL OR TRIM(results) = '')")
        elif filter == "has_results":
            where_clauses.append("(results IS NOT NULL AND TRIM(results) != '')")
        elif filter == "hits":
            where_clauses.append("results = 'HIT'")

        # Por directiva de depuración y separación estricta:
        # Los registros que ya son HIT están destilados en la Bóveda de HITS; no se mezclan en el explorador general
        if filter != "hits":
            where_clauses.append("(results != 'HIT' OR results IS NULL)")

        if search and search.strip():
            s = f"%{search.strip().upper()}%"
            where_clauses.append("(UPPER(u6rfc) LIKE ? OR UPPER(curp) LIKE ? OR UPPER(dmname) LIKE ? OR UPPER(ciudad) LIKE ? OR UPPER(estado) LIKE ? OR codigo_postal LIKE ? OR u6acct LIKE ? OR UPPER(u6delomu) LIKE ? OR UPPER(dmaddr1) LIKE ?)")
            params.extend([s, s, s, s, s, s, s, s, s])

        if col_filters:
            try:
                filters_dict = json.loads(col_filters)
                for col_name, rule in filters_dict.items():
                    if isinstance(rule, str):
                        rule = {"op": "contains", "val": rule}

                    op = rule.get("op", "contains")
                    val = (rule.get("val") or "").strip()

                    if col_name == "direccion":
                        if op == "empty":
                            where_clauses.append("((dmaddr1 IS NULL OR TRIM(dmaddr1) = '') AND (dmaddr2 IS NULL OR TRIM(dmaddr2) = ''))")
                        elif op == "not_empty":
                            where_clauses.append("((dmaddr1 IS NOT NULL AND TRIM(dmaddr1) != '') OR (dmaddr2 IS NOT NULL AND TRIM(dmaddr2) != ''))")
                        elif val:
                            s_val = f"%{val.upper()}%"
                            where_clauses.append("(UPPER(dmaddr1) LIKE ? OR UPPER(dmaddr2) LIKE ? OR UPPER(u6delomu) LIKE ? OR UPPER(dmcity) LIKE ? OR UPPER(u6estado) LIKE ? OR dmzip LIKE ?)")
                            params.extend([s_val, s_val, s_val, s_val, s_val, s_val])
                        continue

                    if col_name not in DB_COLUMNS:
                        continue

                    if op == "empty":
                        where_clauses.append(f"({col_name} IS NULL OR TRIM({col_name}) = '')")
                    elif op == "not_empty":
                        where_clauses.append(f"({col_name} IS NOT NULL AND TRIM({col_name}) != '')")
                    elif op == "starts_with" and val:
                        where_clauses.append(f"UPPER({col_name}) LIKE ?")
                        params.append(f"{val.upper()}%")
                    elif op == "ends_with" and val:
                        where_clauses.append(f"UPPER({col_name}) LIKE ?")
                        params.append(f"%{val.upper()}")
                    elif op == "equals" and val:
                        where_clauses.append(f"UPPER({col_name}) = ?")
                        params.append(val.upper())
                    elif op == "not_equals" and val:
                        where_clauses.append(f"UPPER({col_name}) != ?")
                        params.append(val.upper())
                    elif op == "contains" and val:
                        where_clauses.append(f"UPPER({col_name}) LIKE ?")
                        params.append(f"%{val.upper()}%")
            except Exception as e:
                print(f"[WARN] Error parseando col_filters: {e}")

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        if sort_by in ("u6licrea", "limite"):
            safe_sort_col = "CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER)"
        elif sort_by == "direccion":
            safe_sort_col = "estado"
        elif sort_by in DB_COLUMNS:
            safe_sort_col = sort_by
        else:
            safe_sort_col = "id"

        safe_sort_dir = "DESC" if str(sort_dir).lower() == "desc" else "ASC"

        if not where_sql:
            total = get_total_records_count(conn)
        else:
            cur.execute(f"SELECT COUNT(*) FROM (SELECT 1 FROM santander_records{where_sql} LIMIT 20001)", params)
            total = cur.fetchone()[0]

        offset = (page - 1) * limit
        cols_sql = ", ".join(DB_COLUMNS)
        query_sql = f"""
            SELECT {cols_sql}
            FROM santander_records
            {where_sql}
            ORDER BY {safe_sort_col} {safe_sort_dir}
            LIMIT ? OFFSET ?
        """
        cur.execute(query_sql, params + [limit, offset])
        rows = [dict(r) for r in cur.fetchall()]

        for r in rows:
            r["direccion"] = format_combined_address(r)

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 1,
            "sort_by": sort_by,
            "sort_dir": safe_sort_dir.lower(),
            "records": rows
        }
    finally:
        conn.close()

@app.patch("/api/record/{record_id}")
@app.put("/api/record/{record_id}")
@app.patch("/api/records/{record_id}")
@app.put("/api/records/{record_id}")
def update_record(record_id: int, payload: UpdateRecordPayload, _: None = Depends(require_auth)):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        updates = []
        params = []

        if payload.field:
            field_name = payload.field.strip()
            if field_name not in ("curp", "results"):
                raise HTTPException(status_code=403, detail="🔒 Solo el campo CURP es editable. Los demás campos están bloqueados.")
            val = payload.value.strip() if payload.value is not None else None
            if field_name == "curp" and val:
                val = val.upper()
            updates.append(f"{field_name} = ?")
            params.append(val if val != "" else None)
            if field_name == "curp":
                if val:
                    updates.append("curp_status = ?")
                    params.append("existente")
                    updates.append("curp_falta = NULL")
                else:
                    updates.append("curp_status = ?")
                    params.append("no_calculable")
                    updates.append("curp_falta = ?")
                    params.append("sin_curp")

        if payload.curp is not None and not payload.field:
            val = payload.curp.strip().upper() if payload.curp.strip() else None
            updates.append("curp = ?")
            params.append(val)
            if val:
                updates.append("curp_status = 'existente'")
                updates.append("curp_falta = NULL")
            else:
                updates.append("curp_status = 'no_calculable'")
                updates.append("curp_falta = 'sin_curp'")

        if payload.results is not None and not payload.field:
            updates.append("results = ?")
            params.append(payload.results.strip() if payload.results.strip() else None)

        if not updates:
            return {"ok": True, "message": "Sin cambios"}

        params.append(record_id)
        cur.execute(f"UPDATE santander_records SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

        cur.execute(f"SELECT {', '.join(DB_COLUMNS)} FROM santander_records WHERE id = ?", (record_id,))
        row = cur.fetchone()
        row_dict = dict(row) if row else None
        if row_dict:
            row_dict["direccion"] = format_combined_address(row_dict)
            if row_dict.get("results") == "HIT" and row_dict.get("curp"):
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO santander_hits
                        (id, u6acct, curp, u6rfc, dmname, estado, ciudad, codigo_postal, u6licrea, fecha_nacimiento, genero, direccion, work_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
                    """, (
                        row_dict.get("id"),
                        row_dict.get("u6acct"),
                        row_dict.get("curp"),
                        row_dict.get("u6rfc"),
                        row_dict.get("dmname"),
                        row_dict.get("estado"),
                        row_dict.get("ciudad"),
                        row_dict.get("codigo_postal"),
                        row_dict.get("u6licrea"),
                        row_dict.get("fecha_nacimiento"),
                        row_dict.get("genero"),
                        row_dict.get("direccion"),
                    ))
                    conn.commit()
                except Exception as hit_err:
                    print(f"[WARN] Error insertando en santander_hits: {hit_err}")

        return {"ok": True, "updated_id": record_id, "record": row_dict}
    finally:
        conn.close()

# ── Endpoints Dedicados de la Bóveda de HITS ─────────────────────────────────

@app.get("/api/hits")
def get_hits(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=10, le=500),
    work_status: Optional[str] = Query(None),
    search: Optional[str] = None,
    sort_by: str = Query("checked_at"),
    sort_dir: str = Query("desc"),
    _: None = Depends(require_auth)
):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        where_clauses = []
        params = []

        if work_status and work_status.strip().upper() not in ("ALL", ""):
            where_clauses.append("work_status = ?")
            params.append(work_status.strip().upper())

        if search and search.strip():
            s = f"%{search.strip().upper()}%"
            where_clauses.append("(UPPER(curp) LIKE ? OR UPPER(u6rfc) LIKE ? OR UPPER(dmname) LIKE ? OR UPPER(estado) LIKE ? OR UPPER(ciudad) LIKE ? OR u6acct LIKE ? OR codigo_postal LIKE ?)")
            params.extend([s, s, s, s, s, s, s])

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Contadores globales por estado
        cur.execute("SELECT work_status, COUNT(*) FROM santander_hits GROUP BY work_status")
        status_counts = dict(cur.fetchall())
        total_hits = sum(status_counts.values())

        # Total con filtros aplicados
        cur.execute(f"SELECT COUNT(*) FROM santander_hits{where_sql}", params)
        total_filtered = cur.fetchone()[0]

        allowed_sorts = {
            "id": "id",
            "checked_at": "checked_at",
            "u6licrea": "CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER)",
            "curp": "curp",
            "dmname": "dmname",
            "estado": "estado",
            "ciudad": "ciudad",
            "codigo_postal": "codigo_postal",
            "u6acct": "u6acct",
            "operador": "operador",
            "work_status": "work_status"
        }
        order_col = allowed_sorts.get(sort_by, "checked_at")
        order_dir = "DESC" if str(sort_dir).lower() == "desc" else "ASC"

        offset = (page - 1) * limit
        query_sql = f"""
            SELECT id, u6acct, curp, u6rfc, dmname, estado, ciudad, codigo_postal,
                   u6licrea, fecha_nacimiento, genero, direccion,
                   work_status, operador, notas, checked_at, updated_at
            FROM santander_hits
            {where_sql}
            ORDER BY {order_col} {order_dir}
            LIMIT ? OFFSET ?
        """
        cur.execute(query_sql, params + [limit, offset])
        rows = [dict(r) for r in cur.fetchall()]

        return {
            "total": total_filtered,
            "page": page,
            "limit": limit,
            "total_pages": (total_filtered + limit - 1) // limit if total_filtered > 0 else 1,
            "hits": rows,
            "stats": {
                "total": total_hits,
                "active": status_counts.get("ACTIVE", 0),
                "success": status_counts.get("SUCCESS", 0),
                "off": status_counts.get("OFF", 0),
            }
        }
    finally:
        conn.close()

@app.patch("/api/hits/{hit_id}")
@app.put("/api/hits/{hit_id}")
def update_hit_endpoint(hit_id: int, payload: UpdateHitPayload, user: dict = Depends(require_auth)):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params = []
        if payload.work_status is not None:
            st = payload.work_status.strip().upper()
            if st not in ("ACTIVE", "SUCCESS", "OFF"):
                raise HTTPException(status_code=400, detail="Estatus no válido. Permitidos: ACTIVE, SUCCESS, OFF")
            updates.append("work_status = ?")
            params.append(st)

        if payload.operador is not None:
            updates.append("operador = ?")
            params.append(payload.operador.strip())
        elif user and "display" in user and payload.work_status is not None:
            updates.append("operador = COALESCE(operador, ?)")
            params.append(user["display"])

        if payload.notas is not None:
            updates.append("notas = ?")
            params.append(payload.notas.strip())

        params.append(hit_id)
        cur.execute(f"UPDATE santander_hits SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

        # Si se marcó OFF, borrar de la bóveda y liberar el registro base.
        # NO se pone results=NULL a propósito: el purger solo toma registros con results IS NULL,
        # así que dejarlo poblo re-encolaría el mismo lead para quemarlo otra vez. Se marca como
        # OFF para que quede constancia en el explorador y nunca vuelva a la cola del purger.
        if payload.work_status and payload.work_status.strip().upper() == "OFF":
            cur.execute("SELECT curp FROM santander_hits WHERE id = ?", (hit_id,))
            row_curp = cur.fetchone()
            cur.execute("DELETE FROM santander_hits WHERE id = ?", (hit_id,))
            if row_curp and row_curp[0]:
                cur.execute(
                    "UPDATE santander_records SET results = ? WHERE curp = ?",
                    (f"OFF: descartado por operador ({user.get('display', 'desconocido')})", row_curp[0]),
                )
            conn.commit()
            return {"ok": True, "deleted": True}

        cur.execute("SELECT * FROM santander_hits WHERE id = ?", (hit_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Hit no encontrado")
        return {"ok": True, "hit": dict(row)}
    finally:
        conn.close()

@app.post("/api/hits/{hit_id}/claim")
def claim_hit_endpoint(hit_id: int, user: dict = Depends(require_auth)):
    """Reclama atómicamente un hit y lo asigna al operador que lo está trabajando.
    Solo registra QUIÉN lo tomó (columna operador); el estatus sigue siendo ACTIVE hasta que
    el operador lo marque SUCCESS u OFF explícitamente."""
    display = (user or {}).get("display")
    role = (user or {}).get("role", "operator")
    username = (user or {}).get("username", "")
    is_superadmin = (role == "superadmin" or username == "Robertvs")

    if not display:
        raise HTTPException(status_code=400, detail="Usuario no identificado")
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # UPDATE condicional atómico: solo si está libre o ya es del mismo operador (o superadmin)
        cur.execute("""
            UPDATE santander_hits
            SET operador = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND (operador IS NULL OR TRIM(operador) = '' OR operador = ? OR ?)
        """, (display, hit_id, display, is_superadmin))
        conn.commit()

        cur.execute("SELECT id, curp, work_status, operador FROM santander_hits WHERE id = ?", (hit_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Hit no encontrado")
        row_dict = dict(row)
        claimed = (row_dict.get("operador") == display)
        return {
            "ok": True,
            "claimed": claimed,
            "hit": row_dict,
            "closed_previous_id": None
        }
    finally:
        conn.close()

@app.get("/api/hits/export")
def export_hits_csv(work_status: Optional[str] = None, _: None = Depends(require_auth)):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        where_sql = ""
        params = []
        if work_status and work_status.strip().upper() not in ("ALL", ""):
            where_sql = " WHERE work_status = ?"
            params.append(work_status.strip().upper())

        cur.execute(f"""
            SELECT id, u6acct, curp, u6rfc, dmname, u6licrea, estado, ciudad,
                   codigo_postal, direccion, work_status, operador, notas, checked_at
            FROM santander_hits
            {where_sql}
            ORDER BY checked_at DESC
        """, params)
        rows = [dict(r) for r in cur.fetchall()]

        headers = [
            "id", "u6acct", "curp", "u6rfc", "dmname", "u6licrea", "estado", "ciudad",
            "codigo_postal", "direccion", "work_status", "operador", "notas", "checked_at"
        ]
        csv_lines = [",".join(headers)]
        for r in rows:
            line = []
            for h in headers:
                val = str(r.get(h) or "").replace('"', '""')
                line.append(f'"{val}"')
            csv_lines.append(",".join(line))

        csv_data = "\ufeff" + "\n".join(csv_lines)
        return RawResponse(
            content=csv_data,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="santander_hits.csv"'}
        )
    finally:
        conn.close()

@app.get("/api/purger/status")
def get_purger_status(_: None = Depends(require_auth)):
    # Primera opción: el mismo directorio donde ya se resolvió DB_PATH (fuente única de verdad,
    # coincide siempre con santander_purger.STATUS_JSON_PATH). El resto son fallbacks de compatibilidad.
    status_paths = [
        os.path.join(os.path.dirname(DB_PATH), "purger_status.json"),
        "/opt/kvm4/apps/santander/data/purger_status.json",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "purger_status.json"))
    ]
    for sp in status_paths:
        if os.path.exists(sp):
            try:
                with open(sp, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {"state": "STOPPED", "total_processed": 0, "hits": 0, "offs": 0, "retries": 0}

@app.post("/api/purger/pause")
def pause_purger(_: None = Depends(require_auth)):
    """Pausa manual del purger: crea un archivo flag que el daemon chequea cada ciclo."""
    flag_path = os.path.join(os.path.dirname(DB_PATH), "purger_pause.flag")
    try:
        with open(flag_path, "w") as f:
            f.write(str(time.time()))
        return {"ok": True, "paused": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/purger/resume")
def resume_purger(_: None = Depends(require_auth)):
    """Reanuda el purger: borra el archivo flag de pausa manual."""
    flag_path = os.path.join(os.path.dirname(DB_PATH), "purger_pause.flag")
    try:
        if os.path.exists(flag_path):
            os.remove(flag_path)
        return {"ok": True, "paused": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/batch_update")
def batch_update(payload: BatchUpdatePayload, _: None = Depends(require_auth)):
    if not payload.items:
        return {"ok": True, "updated": 0}
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        updated_count = 0
        for item in payload.items:
            if item.field not in ("curp", "results"):
                continue
            val = item.value.strip() if item.value is not None else None
            if item.field == "curp" and val:
                val = val.upper()
            val = val if val != "" else None
            if item.field == "curp":
                st = "existente" if val else "no_calculable"
                fl = None if val else "sin_curp"
                cur.execute("UPDATE santander_records SET curp = ?, curp_status = ?, curp_falta = ? WHERE id = ?", (val, st, fl, item.id))
            else:
                cur.execute(f"UPDATE santander_records SET {item.field} = ? WHERE id = ?", (val, item.id))
            updated_count += cur.rowcount
        conn.commit()
        return {"ok": True, "updated": updated_count}
    finally:
        conn.close()

@app.post("/api/bulk_curp")
def bulk_curp(payload: BulkCurpPayload, _: None = Depends(require_auth)):
    raw_text = payload.text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Texto vacío")

    conn = get_db_connection()
    cur = conn.cursor()
    updated_count = 0

    try:
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        curp_regex = re.compile(r"\b([A-Z][AEIOUX][A-Z]{2}\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[HM][A-Z]{2}[B-DF-HJ-NP-TV-Z]{3}[A-Z0-9]\d)\b", re.IGNORECASE)

        for line in lines:
            curp_match = curp_regex.search(line)
            if not curp_match:
                continue
            curp_val = curp_match.group(1).upper()
            
            card_match = re.search(r"\b(\d{16})\b", line)
            if card_match:
                card_val = card_match.group(1)
                cur.execute("UPDATE santander_records SET curp = ?, curp_status = 'existente', curp_falta = NULL WHERE u6acct = ? AND (curp IS NULL OR curp = '')", (curp_val, card_val))
                if cur.rowcount > 0:
                    updated_count += cur.rowcount
                    continue

            rfc_prefix = curp_val[:10]
            cur.execute("""
                UPDATE santander_records 
                SET curp = ?, curp_status = 'existente', curp_falta = NULL 
                WHERE id = (
                    SELECT id FROM santander_records 
                    WHERE u6rfc LIKE ? AND (curp IS NULL OR curp = '')
                    LIMIT 1
                )
            """, (curp_val, f"{rfc_prefix}%"))
            if cur.rowcount > 0:
                updated_count += cur.rowcount

        conn.commit()
        return {"ok": True, "updated_count": updated_count}
    finally:
        conn.close()

@app.get("/api/export_csv")
def export_csv(
    filter: str = Query("all"),
    search: Optional[str] = None,
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc"),
    col_filters: Optional[str] = None,
    limit: int = Query(2000, le=10000),
    _: None = Depends(require_auth)
):
    res = get_records(page=1, limit=limit, filter=filter, search=search, sort_by=sort_by, sort_dir=sort_dir, col_filters=col_filters)
    records = res["records"]
    
    headers = [
        "id", "u6rfc", "curp", "curp_status", "curp_falta", "dmname", "genero", "fecha_nacimiento",
        "ciudad", "estado", "codigo_postal", "results", "u6acct", "direccion", "u6tel1", "u6tel2",
        "u6licrea", "u6cvereg", "u6numcto", "dmssnum"
    ]
    csv_lines = [",".join(f'"{h}"' for h in headers)]
    for r in records:
        row_vals = []
        for h in headers:
            v = str(r.get(h) or "").replace('"', '""')
            row_vals.append(f'"{v}"')
        csv_lines.append(",".join(row_vals))
    
    csv_data = "\ufeff" + "\n".join(csv_lines)
    return RawResponse(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="santander_export.csv"'}
    )

from fastapi.responses import RedirectResponse


class CheckCurpPayload(BaseModel):
    curp: str


ACTIVE_CHECKS: dict[str, int] = {}
USER_CHECK_HISTORY: dict[str, list[float]] = {}
MAX_OPERATOR_CONCURRENT = 3
MAX_OPERATOR_BURST_10S = 5

def cleanup_orphan_chromium():
    """Termina procesos huérfanos de Chromium/Chrome de root con más de 2 minutos de vida."""
    if os.name != 'posix':
        return
    try:
        cmd = ["ps", "-u", "root", "-o", "pid,etime,cmd"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        for line in res.stdout.splitlines()[1:]:
            parts = line.strip().split(None, 2)
            if len(parts) >= 3:
                pid_str, etime, cmdline = parts[0], parts[1], parts[2]
                if ("chromium" in cmdline.lower() or "chrome" in cmdline.lower()) and pid_str.isdigit():
                    is_old = False
                    if "-" in etime or etime.count(":") >= 2:
                        is_old = True
                    elif etime.count(":") == 1:
                        m, _ = etime.split(":")
                        if m.isdigit() and int(m) >= 2:
                            is_old = True
                    if is_old:
                        try:
                            os.kill(int(pid_str), 9)
                        except Exception:
                            pass
    except Exception:
        pass

@app.on_event("startup")
async def startup_watchdog():
    async def watchdog_loop():
        while True:
            await asyncio.sleep(120)
            try:
                cleanup_orphan_chromium()
            except Exception:
                pass
    asyncio.create_task(watchdog_loop())


@app.post("/api/check_curp")
async def check_curp_endpoint(payload: CheckCurpPayload, user: dict = Depends(require_auth)):
    username = user.get("username", "unknown")
    role = user.get("role", "operator")
    is_superadmin = (role == "superadmin")
    
    curp = (payload.curp or "").strip().upper()
    if not curp:
        raise HTTPException(status_code=400, detail="El campo CURP no puede estar vacío.")

    # 1. Control de concurrencia y anti-spam para operadores (Magdiel, Luisito)
    if not is_superadmin:
        active_now = ACTIVE_CHECKS.get(username, 0)
        if active_now >= MAX_OPERATOR_CONCURRENT:
            raise HTTPException(
                status_code=429,
                detail=f"Límite alcanzado: Máximo {MAX_OPERATOR_CONCURRENT} verificaciones simultáneas permitidas para tu usuario ({username}). Espera a que termine una."
            )
            
        now = time.time()
        history = [t for t in USER_CHECK_HISTORY.get(username, []) if now - t < 10.0]
        if len(history) >= MAX_OPERATOR_BURST_10S:
            raise HTTPException(
                status_code=429,
                detail="Anti-Spam activado: Demasiadas solicitudes en pocos segundos. Por favor espera a que terminen tus comprobaciones."
            )
        history.append(now)
        USER_CHECK_HISTORY[username] = history

    # 2. Incremento de concurrencia activa
    ACTIVE_CHECKS[username] = ACTIVE_CHECKS.get(username, 0) + 1
    try:
        res = await asyncio.wait_for(check_single_curp(curp), timeout=45.0)
        if res.get("status") == "OFF":
            res["short_reason"] = format_short_reason(res.get("detail", ""))
        return res
    except asyncio.TimeoutError:
        return {"curp": curp, "status": "ERROR", "detail": "Timeout en Onboarding Santander (45s excedido)"}
    except Exception as e:
        return {"curp": curp, "status": "ERROR", "detail": f"Error: {str(e)[:80]}"}
    finally:
        ACTIVE_CHECKS[username] = max(0, ACTIVE_CHECKS.get(username, 1) - 1)
        cleanup_orphan_chromium()

@app.get("/", response_class=HTMLResponse)
@app.get("/santabase", response_class=HTMLResponse)
@app.get("/santabase/", response_class=HTMLResponse)
def index(request: Request):
    return HTML_CONTENT

@app.get("/santander")
@app.get("/santander/")
def redirect_legacy_santander():
    return RedirectResponse(url="/santabase", status_code=302)

HTML_CONTENT = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Santa Base — Bóveda Operativa (4.9M Registros)</title>
  <meta name="description" content="Santander DB — Motor Soberano de Consulta y Gestión (Santa Base)">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/animejs/3.2.2/anime.min.js"></script>
  <script>if (typeof anime === 'undefined') { document.write('<script src="/static/anime.min.js"><' + '/script>'); }</script>
  <style>
    :root {
      /* Superficies y Fondos — Red & Obsidian Ops */
      --bg-app: #07070a;
      --bg-card: #0f0f15;
      --bg-surface: #12121a;
      --bg-surface-elevated: #181824;
      --bg-row-hover: rgba(236, 0, 0, 0.05);
      --bg-row-selected: rgba(236, 0, 0, 0.18);
      --excel-selection-bg: rgba(236, 0, 0, 0.14);

      /* Bordes y Divisiones */
      --border: #1e1e2a;
      --border-subtle: #191924;
      --border-strong: #2a2a3c;
      --border-focus: #ec0000;

      /* Radios de curvatura */
      --radius-sm: 4px;
      --radius-md: 6px;
      --radius-lg: 8px;
      --radius-full: 9999px;

      /* Sistema Semántico de Color — Rojo Santander & Negro Carbón */
      /* Nivel 1: Primario (Acción Principal / Foco) */
      --color-primary: #ec0000;
      --color-primary-hover: #ff1a1a;
      --color-primary-active: #cc0000;
      --color-primary-ring: rgba(236, 0, 0, 0.4);

      /* Nivel 2: Secundario / Neutro (Acciones frecuentes, Toolbar, Copia) */
      --color-neutral-bg: #14141e;
      --color-neutral-border: #28283a;
      --color-neutral-hover: #1e1e2c;
      --color-neutral-text: #f3f4f6;

      /* Nivel 3: Destructivo / Peligro (Logout, Reset, Alertas) */
      --color-danger: #ec0000;
      --color-danger-hover: #ff1a1a;
      --color-danger-subtle: rgba(236, 0, 0, 0.14);
      --color-danger-border: rgba(236, 0, 0, 0.4);

      /* Marca Santander Canónica */
      --santander: #ec0000;

      /* Tipografía */
      --font-mono: 'JetBrains Mono', monospace;
      --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --font-size-base: 13px;
      --font-size-cell: 12.5px;
      --font-size-header: 11.5px;
      --font-size-btn: 12.5px;
      --font-size-small: 11px;
      --font-size-kpi-val: 16px;
      --font-size-kpi-lbl: 10px;

      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --text-dim: #6b7280;

      /* Dimensiones de Celdas (Respirar) */
      --cell-h: 36px;
      --cell-pad-x: 10px;
      --cell-pad-y: 6px;

      /* Microinteracciones */
      --transition-fast: all 140ms ease;
    }

    /* Custom Sleek Scrollbars — Red & Black Velvet Fintech */
    ::-webkit-scrollbar {
      width: 7px;
      height: 7px;
    }
    ::-webkit-scrollbar-track {
      background: #08080c;
    }
    ::-webkit-scrollbar-thumb {
      background: #232330;
      border-radius: 4px;
      border: 1px solid #14141d;
      transition: background 0.2s ease;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #ec0000;
      box-shadow: 0 0 10px rgba(236, 0, 0, 0.6);
    }
    ::-webkit-scrollbar-corner {
      background: #08080c;
    }
    * {
      scrollbar-width: thin;
      scrollbar-color: #232330 #08080c;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg-app);
      color: var(--text);
      font-family: var(--font-sans);
      font-size: var(--font-size-base);
      line-height: 1.4;
      padding: 8px 12px;
      user-select: none;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    /* Lock Screen Overlay */
    #lock-screen {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(8, 13, 26, 0.96);
      backdrop-filter: blur(12px);
      z-index: 9999;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: opacity 0.3s ease;
    }
    #lock-screen.hidden { display: none; pointer-events: none; }
    .lock-card {
      background: var(--bg-card);
      border: 1px solid var(--border-strong);
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 35px rgba(2, 132, 199, 0.1);
      border-radius: var(--radius-lg);
      padding: 34px 30px;
      width: 380px;
      max-width: 90vw;
      text-align: center;
    }
    .lock-icon-circle {
      width: 54px;
      height: 54px;
      background: rgba(2, 132, 199, 0.12);
      border: 1px solid rgba(2, 132, 199, 0.3);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 24px;
      margin: 0 auto 16px;
      color: var(--color-primary);
    }
    .lock-title {
      font-size: 18px;
      font-weight: 800;
      color: #fff;
      margin-bottom: 6px;
      letter-spacing: -0.2px;
    }
    .lock-subtitle {
      font-size: 12px;
      color: var(--text-muted);
      margin-bottom: 22px;
      line-height: 1.45;
    }
    .password-input-group {
      position: relative;
      margin-bottom: 16px;
    }
    .password-input {
      width: 100%;
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      padding: 11px 42px 11px 14px;
      border-radius: var(--radius-md);
      font-size: 13px;
      font-family: var(--font-mono);
      outline: none;
      transition: var(--transition-fast);
    }
    .password-input:focus {
      border-color: var(--border-focus);
      box-shadow: 0 0 0 3px var(--color-primary-ring);
    }
    .eye-btn {
      position: absolute;
      right: 12px;
      top: 50%;
      transform: translateY(-50%);
      background: transparent;
      border: none;
      color: var(--text-dim);
      cursor: pointer;
      font-size: 16px;
      padding: 4px;
      transition: var(--transition-fast);
    }
    .eye-btn:hover { color: #cbd5e1; }
    .btn-login {
      width: 100%;
      background: var(--color-primary);
      color: #fff;
      border: none;
      padding: 11px;
      border-radius: var(--radius-md);
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: var(--transition-fast);
      box-shadow: 0 2px 8px rgba(2, 132, 199, 0.25);
    }
    .btn-login:hover {
      background: var(--color-primary-hover);
      box-shadow: 0 4px 14px rgba(2, 132, 199, 0.4);
    }
    .lock-error {
      margin-top: 12px;
      color: #f87171;
      font-size: 11.5px;
      display: none;
    }
    .lock-error.show { display: block; }

    /* Top Bar */
    .top-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
      gap: 12px;
    }
    .brand-group {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }
    /* Unified Brand Logo: SANTA (Red Pill) + 🙏🏻 + BASE (Italic Flame) */
    .santa-brand-logo {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 3px 6px;
      border-radius: var(--radius-md);
      transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
      cursor: default;
      user-select: none;
    }
    .santa-brand-logo:hover {
      transform: scale(1.02);
    }
    .santa-brand-logo.lock-logo {
      margin-bottom: 12px;
      transform: scale(1.15);
    }
    .logo-pill-santa {
      background: linear-gradient(135deg, #ec0000 0%, #bd0000 100%);
      color: #ffffff;
      font-family: var(--font-sans);
      font-weight: 900;
      font-size: 15px;
      letter-spacing: 0.1em;
      padding: 3px 10px;
      border-radius: 6px;
      box-shadow: 0 0 16px rgba(236, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.25);
      text-transform: uppercase;
      line-height: 1.1;
      display: inline-flex;
      align-items: center;
    }
    .logo-icon-pray {
      font-size: 17px;
      line-height: 1;
      filter: drop-shadow(0 0 8px rgba(236, 0, 0, 0.5));
      display: inline-flex;
      align-items: center;
    }
    .logo-text-base {
      font-family: var(--font-sans);
      font-weight: 900;
      font-style: italic;
      font-size: 17px;
      letter-spacing: 0.12em;
      background: linear-gradient(135deg, #ff1a1a 0%, #ff5e1a 50%, #ffa600 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      text-shadow: 0 0 18px rgba(236, 0, 0, 0.35);
      line-height: 1.1;
      display: inline-flex;
      align-items: center;
    }
    /* Clases de compatibilidad para suite de tests */
    .brand-santa { font-weight: 900; }
    .brand-pray { }
    .brand-base { font-weight: 900; font-style: italic; }
    .stats-group {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .kpi-card {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 3px 10px;
      display: inline-flex;
      flex-direction: column;
      align-items: flex-start;
      min-width: 82px;
      transition: var(--transition-fast);
    }
    .kpi-card:hover {
      border-color: var(--border-strong);
      background: var(--bg-surface-elevated);
    }
    .kpi-label {
      font-size: var(--font-size-kpi-lbl);
      color: var(--text-dim);
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      line-height: 1.1;
      margin-bottom: 1px;
    }
    .kpi-val {
      font-family: var(--font-mono);
      font-size: var(--font-size-kpi-val);
      font-weight: 700;
      color: #f1f5f9;
      line-height: 1.1;
    }
    .kpi-card {
      background: #111118;
      border: 1px solid #22222f;
      border-radius: var(--radius-md);
      padding: 4px 11px;
      transition: all 180ms ease;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
    }
    .kpi-card:hover {
      border-color: rgba(236, 0, 0, 0.45);
      background: #161622;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(236, 0, 0, 0.15);
    }
    .kpi-card.curp .kpi-val { color: #10b981; }
    .kpi-card.calc .kpi-val { color: #ff3b5c; }
    .kpi-card.missing .kpi-val { color: #f59e0b; }
    .kpi-card.results .kpi-val { color: #facc15; }

    /* Compatibilidad retrospectiva para stat-pill */
    .stat-pill {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      padding: 4px 8px;
      border-radius: var(--radius-sm);
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: var(--font-size-small);
      font-family: var(--font-mono);
    }
    .stat-pill span { font-weight: 700; color: #38bdf8; }
    .stat-pill.curp span { color: #34d399; }
    .stat-pill.results span { color: #fbbf24; }

    .btn-logout {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 6px 10px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-size: var(--font-size-small);
      font-weight: 600;
      transition: var(--transition-fast);
      margin-left: 4px;
    }
    .btn-logout:hover {
      color: #fff;
      background: var(--color-danger);
      border-color: var(--color-danger);
      box-shadow: 0 0 10px rgba(236, 0, 0, 0.4);
    }

    /* Mega-Buscador (Command Center) - Reemplazo de Formula Bar */
    .mega-search-bar {
      display: flex;
      align-items: center;
      gap: 12px;
      background: linear-gradient(180deg, #12121a 0%, #0d0d13 100%);
      border: 1px solid #282838;
      border-radius: var(--radius-lg);
      padding: 8px 16px;
      margin: 8px 0;
      flex-shrink: 0;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.04);
      transition: border-color 180ms ease, box-shadow 180ms ease;
    }
    .mega-search-bar:focus-within {
      border-color: var(--color-primary);
      box-shadow: 0 0 0 3px var(--color-primary-ring), 0 8px 24px rgba(236, 0, 0, 0.22);
    }
    .mega-search-icon {
      font-size: 18px;
      color: #ec0000;
      filter: drop-shadow(0 0 6px rgba(236, 0, 0, 0.5));
      flex-shrink: 0;
    }
    .mega-filter-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: rgba(236, 0, 0, 0.15);
      color: #ff4d4d;
      border: 1px solid rgba(236, 0, 0, 0.45);
      border-radius: var(--radius-sm);
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
      white-space: nowrap;
      font-family: var(--font-mono);
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
      transition: all 180ms ease;
    }
    .mega-filter-badge:hover {
      background: rgba(236, 0, 0, 0.28);
      border-color: #ff3333;
      transform: translateY(-1px);
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
      background: rgba(236, 0, 0, 0.12);
      border: 1px solid rgba(236, 0, 0, 0.35);
      color: #ff5555;
    }

    /* Formulario Multi-Usuario en Lock Screen (Input de Texto Estricto) */
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
    }

    /* Toolbar con 4 Clusters Visuales y Segmented Control */
    .toolbar {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 6px;
      background: var(--bg-card);
      padding: 6px 10px;
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      flex-shrink: 0;
      overflow-x: auto;
    }
    .tb-group {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
      flex-shrink: 0;
    }
    .tb-sep {
      width: 1px;
      height: 24px;
      background: var(--border-strong);
      margin: 0 4px;
      flex-shrink: 0;
    }
    /* Segmented Control de Filtros Predefinidos */
    .filter-tabs {
      display: inline-flex;
      background: var(--bg-app);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 2px;
      gap: 2px;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 4px 10px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-size: var(--font-size-small);
      font-weight: 500;
      transition: var(--transition-fast);
    }
    .tab-btn:hover {
      color: #fff;
      background: rgba(255, 255, 255, 0.05);
    }
    .tab-btn.active {
      background: var(--color-primary);
      color: #fff;
      font-weight: 600;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
    }
    .global-search {
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      padding: 5px 10px;
      border-radius: var(--radius-sm);
      font-size: var(--font-size-small);
      width: 210px;
      outline: none;
      transition: var(--transition-fast);
    }
    .global-search:focus {
      border-color: var(--border-focus);
      box-shadow: 0 0 0 2px var(--color-primary-ring);
    }

    /* Sistema de Botones Semanticos (3 Niveles) */
    .btn {
      background: var(--color-neutral-bg);
      color: var(--color-neutral-text);
      border: 1px solid var(--color-neutral-border);
      padding: 5px 10px;
      border-radius: var(--radius-sm);
      font-size: var(--font-size-btn);
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: var(--transition-fast);
      white-space: nowrap;
    }
    .btn:hover {
      background: var(--color-neutral-hover);
      border-color: #475569;
      color: #fff;
    }
    .btn-primary {
      background: var(--color-primary) !important;
      border-color: var(--color-primary) !important;
      color: #fff !important;
      font-weight: 600;
    }
    .btn-primary:hover {
      background: var(--color-primary-hover) !important;
      border-color: var(--color-primary-hover) !important;
      box-shadow: 0 2px 10px rgba(236, 0, 0, 0.4);
    }
    .btn-excel {
      background: linear-gradient(180deg, #1c1215 0%, #12090b 100%);
      border: 1px solid rgba(236, 0, 0, 0.45);
      color: #ff5555;
      font-weight: 600;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
      transition: all 160ms ease;
    }
    .btn-excel:hover {
      background: linear-gradient(180deg, #ec0000 0%, #c40000 100%);
      border-color: #ff3333;
      color: #ffffff;
      box-shadow: 0 0 16px rgba(236, 0, 0, 0.5);
      transform: translateY(-1px);
    }
    .btn-curp {
      background: var(--color-neutral-bg);
      border: 1px solid #0d9488;
      color: #2dd4bf;
      font-weight: 600;
    }
    .btn-curp:hover {
      background: rgba(13, 148, 136, 0.15);
      border-color: #14b8a6;
      color: #5eead4;
    }
    .btn-success {
      background: #059669;
      border-color: #047857;
      color: #fff;
      font-weight: 600;
    }
    .btn-success:hover {
      background: #047857;
    }
    .btn-outline {
      background: transparent;
      border: 1px solid var(--border-strong);
      color: var(--text);
    }
    .btn-outline:hover {
      background: var(--bg-surface-elevated);
      border-color: #475569;
      color: #fff;
    }
    .btn-danger-outline {
      background: transparent;
      border: 1px solid var(--color-danger-border);
      color: #f87171;
    }
    .btn-danger-outline:hover {
      background: var(--color-danger);
      border-color: var(--color-danger);
      color: #fff;
      box-shadow: 0 0 8px rgba(236, 0, 0, 0.4);
    }

    /* Active Filters Indicator Bar */
    #active-filters-bar {
      display: none;
      align-items: center;
      gap: 8px;
      padding: 4px 10px;
      background: #101c33;
      border: 1px solid #1e3a8a;
      border-radius: var(--radius-sm);
      margin-bottom: 6px;
      font-size: var(--font-size-small);
      flex-shrink: 0;
    }
    #active-filters-bar.show { display: flex; flex-wrap: wrap; }
    .filter-chip {
      background: #1e3a8a;
      color: #93c5fd;
      padding: 2px 7px;
      border-radius: var(--radius-sm);
      font-family: var(--font-mono);
      font-size: 10.5px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }
    .filter-chip-remove {
      cursor: pointer;
      font-weight: bold;
      color: #bfdbfe;
    }
    .filter-chip-remove:hover { color: #fff; }

    /* General Explorer View Container */
    #general-view-container {
      display: flex;
      flex-direction: column;
      flex: 1;
      min-height: 0;
    }

    /* Grid Table Container */
    .grid-container {
      flex: 1;
      min-height: 0;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      overflow: auto;
      position: relative;
    }
    table.excel-table {
      border-collapse: separate;
      border-spacing: 0;
      width: max-content;
      min-width: 100%;
      text-align: left;
    }

    /* Cabeceras de Columna */
    th.excel-header {
      position: relative;
      overflow: visible;
      background: #0a0a0f;
      color: var(--text-muted);
      font-size: var(--font-size-header);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 0;
      position: sticky;
      top: 0;
      z-index: 20;
      border-bottom: 2px solid #27354f;
      border-right: 1px solid var(--border-subtle);
      white-space: nowrap;
      user-select: none;
      box-sizing: border-box;
      height: 34px;
    }
    .th-inner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 4px;
      padding: 6px 8px;
      width: 100%;
      height: 100%;
      box-sizing: border-box;
      overflow: hidden;
    }
    .th-title-wrap {
      display: flex;
      align-items: center;
      gap: 4px;
      min-width: 0;
      flex: 1 1 auto;
      overflow: hidden;
    }
    .col-letter {
      font-size: 10px;
      color: var(--text-dim);
      font-family: var(--font-mono);
      flex-shrink: 0;
    }
    .th-title {
      font-weight: 600;
      color: #cbd5e1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      min-width: 0;
      font-size: var(--font-size-header);
    }
    .th-editable-pill {
      background: #065f46;
      color: #34d399;
      font-size: 9px;
      font-weight: 700;
      padding: 1px 4px;
      border-radius: 2px;
      flex-shrink: 0;
    }
    .header-btns {
      display: flex;
      align-items: center;
      gap: 3px;
      flex-shrink: 0;
    }
    .sort-indicator {
      font-size: 9px;
      color: var(--color-primary);
      flex-shrink: 0;
    }
    .filter-btn {
      background: transparent;
      border: 1px solid transparent;
      color: var(--text-dim);
      padding: 2px 4px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-size: 10px;
      line-height: 1;
      transition: var(--transition-fast);
    }
    .filter-btn:hover {
      background: var(--bg-surface-elevated);
      color: #f1f5f9;
      border-color: var(--border-strong);
    }
    .filter-btn.has-filter {
      background: #065f46;
      color: #34d399;
      border-color: #059669;
      box-shadow: 0 0 6px rgba(16, 185, 129, 0.4);
    }

    th.row-num-header {
      width: 38px;
      min-width: 38px;
      max-width: 38px;
      text-align: center;
      background: #09090d;
      color: var(--text-dim);
      font-family: var(--font-mono);
      font-size: 10px;
      position: sticky;
      left: 0;
      z-index: 30;
      border-right: 1px solid #1f1f2e;
    }
    td.row-num-cell {
      position: sticky;
      left: 0;
      z-index: 10;
      background: #0a0a0f;
      color: var(--text-dim);
      text-align: center;
      font-family: var(--font-mono);
      font-size: var(--font-size-small);
      border-right: 1px solid var(--border-subtle);
      border-bottom: 1px solid var(--border-subtle);
      padding: 0 4px;
      cursor: pointer;
      vertical-align: middle;
      transition: background-color 120ms ease;
    }

    /* Filas y Celdas con Spacing Generoso (Respirar) */
    tr {
      height: var(--cell-h);
      transition: background-color 120ms ease;
    }
    tr:hover td {
      background-color: var(--bg-row-hover);
    }
    tr.row-selected td {
      background-color: var(--bg-row-selected) !important;
    }

    td.excel-cell {
      padding: var(--cell-pad-y) var(--cell-pad-x);
      border-right: 1px solid var(--border-subtle);
      border-bottom: 1px solid var(--border-subtle);
      vertical-align: middle;
      white-space: nowrap;
      font-size: var(--font-size-cell);
      position: relative;
      cursor: cell;
      overflow: hidden;
      text-overflow: ellipsis;
      box-sizing: border-box;
      transition: background-color 120ms ease;
    }
    .mono { font-family: var(--font-mono); }

    td.excel-cell.excel-active {
      outline: 2px solid var(--color-primary) !important;
      outline-offset: -2px;
      background-color: var(--excel-selection-bg) !important;
      z-index: 15;
    }
    td.excel-cell.excel-active::after {
      content: '';
      position: absolute;
      right: -2px;
      bottom: -2px;
      width: 6px;
      height: 6px;
      background: var(--color-primary);
      border: 1px solid #090d16;
      cursor: crosshair;
    }

    /* Rango de celdas seleccionadas por arrastre (misma columna) o Ctrl+arrastre (multi-segmento) */
    td.excel-cell.excel-range-selected {
      background-color: var(--excel-selection-bg) !important;
      box-shadow: inset 1px 0 0 var(--color-primary), inset -1px 0 0 var(--color-primary);
    }
    td.excel-cell.excel-range-edge-top {
      box-shadow: inset 1px 0 0 var(--color-primary), inset -1px 0 0 var(--color-primary), inset 0 2px 0 var(--color-primary);
    }
    td.excel-cell.excel-range-edge-bottom {
      box-shadow: inset 1px 0 0 var(--color-primary), inset -1px 0 0 var(--color-primary), inset 0 -2px 0 var(--color-primary);
    }

    @keyframes cellSavedAnim {
      0% { background-color: #065f46; color: #fff; }
      100% { background-color: transparent; }
    }
    .cell-saved { animation: cellSavedAnim 1.2s ease-out; }

    .cell-editor-input {
      position: absolute;
      top: 0; left: 0;
      width: 100%; height: 100%;
      background: var(--bg-surface-elevated);
      color: #fff;
      border: 2px solid var(--color-primary);
      font-family: var(--font-mono);
      font-size: var(--font-size-cell);
      padding: var(--cell-pad-y) var(--cell-pad-x);
      outline: none;
      z-index: 25;
      box-shadow: 0 0 0 3px var(--color-primary-ring);
    }

    .rfc-pill {
      font-weight: 700;
      color: #ffffff;
      background: #181824;
      padding: 2px 6px;
      border-radius: var(--radius-sm);
      border: 1px solid rgba(236, 0, 0, 0.3);
      letter-spacing: 0.02em;
    }
    .curp-pill {
      color: #34d399;
      font-weight: 700;
      background: rgba(16, 185, 129, 0.1);
      padding: 2px 6px;
      border-radius: var(--radius-sm);
      border: 1px dashed rgba(16, 185, 129, 0.4);
    }
    .curp-empty {
      color: var(--text-dim);
      font-style: italic;
      font-size: 11px;
    }
    .status-badge {
      font-size: 10px;
      padding: 2px 6px;
      border-radius: var(--radius-sm);
      font-weight: 600;
      text-transform: uppercase;
      font-family: var(--font-mono);
    }
    .status-calculada { background: #064e3b; color: #34d399; border: 1px solid #059669; }
    .status-existente { background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; }
    .status-no_calculable { background: #3b0764; color: #d8b4fe; border: 1px solid #7e22ce; }
    .falta-badge {
      font-size: 10px;
      padding: 2px 6px;
      border-radius: var(--radius-sm);
      background: #27272a;
      color: #a1a1aa;
      font-family: var(--font-mono);
    }
    .tag-btn {
      background: #1e293b;
      border: 1px solid #334155;
      color: #cbd5e1;
      font-size: 9.5px;
      padding: 2px 5px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      margin-left: 3px;
    }
    .tag-btn.hit, .tag-btn.live { 
      border-color: #059669; 
      color: #34d399; 
      background: #064e3b; 
      font-weight: 700; 
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 3px;
      line-height: 1.2;
      transition: all 0.15s ease;
    }
    .tag-btn.live:hover, .tag-btn.hit:hover {
      background: #047857;
      color: #ecfdf5;
      box-shadow: 0 0 8px rgba(52, 211, 153, 0.4);
      transform: translateY(-1px);
    }
    .tag-btn.dead { border-color: #dc2626; color: #f87171; background: #450a0a; font-weight: 700; }

    /* Pagination Bar */
    .pagination-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 8px;
      font-size: var(--font-size-small);
      color: var(--text-muted);
      flex-shrink: 0;
    }
    .page-controls {
      display: flex;
      gap: 8px;
      align-items: center;
    }

    /* Popover */
    .filter-popover {
      display: none;
      position: fixed;
      background: var(--bg-card);
      border: 1px solid var(--border-strong);
      box-shadow: 0 16px 36px rgba(0, 0, 0, 0.7);
      border-radius: var(--radius-md);
      width: 260px;
      z-index: 1000;
      padding: 12px;
      font-family: var(--font-sans);
    }
    .filter-popover.show { display: block; }
    .popover-header {
      font-weight: 700;
      font-size: 12px;
      color: #fff;
      margin-bottom: 8px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .popover-close { cursor: pointer; color: var(--text-muted); font-size: 14px; }
    .popover-close:hover { color: #fff; }
    .popover-sort-btns { display: flex; flex-direction: column; gap: 5px; margin-bottom: 8px; }
    .sort-menu-btn {
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-strong);
      color: #e2e8f0;
      text-align: left;
      padding: 5px 8px;
      border-radius: var(--radius-sm);
      font-size: 11px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: var(--transition-fast);
    }
    .sort-menu-btn:hover { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
    .popover-divider { height: 1px; background: var(--border); margin: 8px 0; }
    .popover-input-group { display: flex; flex-direction: column; gap: 5px; margin-bottom: 8px; }
    .popover-select, .popover-input {
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      padding: 5px 8px;
      border-radius: var(--radius-sm);
      font-size: 11.5px;
      outline: none;
      transition: var(--transition-fast);
    }
    .popover-input:focus { border-color: var(--border-focus); }
    .popover-actions { display: flex; justify-content: space-between; gap: 8px; }

    /* Search Input Wrapper with Instant Clear */
    .search-input-wrap {
      position: relative;
      display: inline-flex;
      align-items: center;
    }
    .global-search {
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      padding: 5px 28px 5px 10px;
      border-radius: var(--radius-sm);
      font-size: var(--font-size-small);
      width: 220px;
      outline: none;
      transition: var(--transition-fast);
    }
    .global-search:focus {
      border-color: var(--border-focus);
      box-shadow: 0 0 0 2px var(--color-primary-ring);
    }
    .search-clear-btn {
      position: absolute;
      right: 6px;
      background: transparent;
      border: none;
      color: var(--text-dim);
      font-size: 11px;
      cursor: pointer;
      padding: 2px 4px;
      border-radius: 50%;
      line-height: 1;
      transition: var(--transition-fast);
    }
    .search-clear-btn:hover {
      color: #fff;
      background: rgba(255, 255, 255, 0.1);
    }

    /* Context Menu Modern Acrylic & Shortcut Badges */
    .context-menu {
      display: none;
      position: fixed;
      background: rgba(15, 23, 42, 0.96);
      backdrop-filter: blur(14px);
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-md);
      box-shadow: 0 16px 36px -4px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.05);
      min-width: 215px;
      z-index: 1100;
      padding: 5px;
    }
    .context-menu.show { display: block; }
    .ctx-header {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-dim);
      padding: 4px 8px 5px;
      font-weight: 700;
      border-bottom: 1px solid var(--border);
      margin-bottom: 3px;
    }
    .ctx-item {
      padding: 6px 10px;
      font-size: 12px;
      color: #e2e8f0;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-radius: var(--radius-sm);
      transition: var(--transition-fast);
      gap: 12px;
    }
    .ctx-item:hover {
      background: var(--color-primary);
      color: #fff;
    }
    .ctx-item.ctx-highlight {
      background: rgba(2, 132, 199, 0.15);
      color: #38bdf8;
      font-weight: 600;
    }
    .ctx-item.ctx-highlight:hover {
      background: var(--color-primary);
      color: #fff;
    }
    .ctx-item-danger:hover {
      background: var(--color-danger) !important;
      color: #fff !important;
    }
    .ctx-shortcut {
      font-family: var(--font-mono);
      font-size: 10px;
      color: var(--text-dim);
      background: rgba(255, 255, 255, 0.06);
      padding: 1px 5px;
      border-radius: 3px;
    }
    .ctx-item:hover .ctx-shortcut {
      color: #fff;
      background: rgba(0, 0, 0, 0.25);
    }
    .ctx-badge {
      font-family: var(--font-mono);
      font-size: 10px;
      color: #38bdf8;
      font-weight: 700;
    }
    .ctx-item:hover .ctx-badge {
      color: #fff;
    }
    .ctx-sep { height: 1px; background: var(--border); margin: 4px 0; }

    /* Layout Responsive (Zero Overlaps) */
    @media (max-width: 1280px) {
      .global-search { width: 170px; }
      .kpi-card { min-width: 72px; padding: 2px 7px; }
      .kpi-val { font-size: 14px; }
    }
    @media (max-width: 1050px) {
      .top-bar { flex-wrap: wrap; }
      .keyboard-hint { display: none; }
      .toolbar { gap: 6px; }
      .tb-sep { margin: 0 2px; }
    }

    /* Modal */
    .modal {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.75);
      backdrop-filter: blur(5px);
      z-index: 1200;
      align-items: center;
      justify-content: center;
    }
    .modal.show { display: flex; }
    .modal-content {
      background: var(--bg-card);
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-lg);
      width: 520px;
      max-width: 90vw;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .modal-textarea {
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      font-family: var(--font-mono);
      padding: 9px;
      border-radius: var(--radius-sm);
      height: 160px;
      resize: vertical;
      font-size: 11.5px;
      outline: none;
      transition: var(--transition-fast);
    }
    .modal-textarea:focus { border-color: var(--border-focus); }

    #toast {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: var(--bg-card);
      border: 1px solid var(--border-focus);
      color: #fff;
      padding: 8px 16px;
      border-radius: var(--radius-md);
      font-size: 12px;
      font-weight: 500;
      box-shadow: 0 12px 28px rgba(0,0,0,0.65);
      opacity: 0;
      transform: translateY(10px);
      transition: all 0.2s ease;
      z-index: 2000;
      pointer-events: none;
    }
    #toast.show { opacity: 1; transform: translateY(0); }

    /* Modernized Quieter & Resizable Styles */
    .col-resizer {
      position: absolute;
      top: 0;
      right: 0;
      width: 6px;
      height: 100%;
      cursor: col-resize;
      user-select: none;
      z-index: 25;
    }
    .col-resizer:hover, .col-resizer.resizing {
      background: var(--color-primary);
    }
    body.resizing-col {
      cursor: col-resize !important;
      user-select: none !important;
    }
    body.resizing-col * {
      user-select: none !important;
    }

    /* Quieter Monospace Elements */
    .copyable-text {
      cursor: pointer;
      padding: 2px 4px;
      border-radius: var(--radius-sm);
      transition: var(--transition-fast);
      display: inline-block;
    }
    .copyable-text:hover {
      background: rgba(236, 0, 0, 0.15);
      color: #ff5555 !important;
      text-decoration: underline;
    }
    .rfc-text {
      color: #cbd5e1;
      font-family: var(--font-mono);
      font-size: var(--font-size-cell);
      letter-spacing: 0.5px;
    }
    .rfc-date {
      color: #ff5555;
      font-weight: 700;
      background: rgba(236, 0, 0, 0.14);
      padding: 0 3px;
      border-radius: 3px;
    }
    .curp-text {
      color: #34d399;
      font-family: var(--font-mono);
      font-size: var(--font-size-cell);
      font-weight: 600;
      letter-spacing: 0.5px;
    }
    .card-text {
      color: #e2e8f0;
      font-family: var(--font-mono);
      font-size: var(--font-size-cell);
      letter-spacing: 0.8px;
    }
    .limite-text {
      color: #6ee7b7;
      font-family: var(--font-mono);
      font-weight: 600;
      font-size: var(--font-size-cell);
      display: block;
      text-align: right;
      padding-right: 4px;
    }

    /* Large responsive checkbox hitbox */
    td.select-col-cell {
      padding: 0 !important;
      cursor: pointer;
      text-align: center;
      vertical-align: middle;
      user-select: none;
    }
    td.select-col-cell input.row-checkbox {
      cursor: pointer;
      width: 16px;
      height: 16px;
      pointer-events: none;
      accent-color: var(--color-primary);
    }

    /* Floating micro feedback tooltip */
    .inline-copy-feedback {
      position: fixed;
      background: #10b981;
      color: #ffffff;
      font-size: 10.5px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: var(--radius-sm);
      box-shadow: 0 4px 14px rgba(0,0,0,0.4);
      z-index: 10000;
      pointer-events: none;
      animation: feedbackFade 0.75s forwards;
    }
    @keyframes feedbackFade {
      0% { opacity: 0; transform: translateY(4px); }
      20% { opacity: 1; transform: translateY(0); }
      80% { opacity: 1; transform: translateY(0); }
      100% { opacity: 0; transform: translateY(-6px); }
    }

    /* ── Impeccable Design Pass: Check Button & Glimmer ── */
    @keyframes checkGlimmerSweep {
      0% { transform: translateX(-160%) skewX(-20deg); }
      35%, 100% { transform: translateX(260%) skewX(-20deg); }
    }
    @keyframes spinLoader {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    .spin { display: inline-block; animation: spinLoader 1.4s linear infinite; }

    .btn-check-curp {
      position: relative;
      overflow: hidden;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      padding: 3px 10px;
      font-family: var(--font-sans);
      font-size: 10.5px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #ffffff;
      background: linear-gradient(135deg, rgba(236, 0, 0, 0.28) 0%, rgba(20, 10, 14, 0.95) 100%);
      border: 1px solid rgba(236, 0, 0, 0.65);
      border-radius: 5px;
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.6), 0 0 8px rgba(236, 0, 0, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.18);
      transition: all 180ms cubic-bezier(0.16, 1, 0.3, 1);
      user-select: none;
    }
    .btn-check-curp::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 55%;
      height: 100%;
      background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.38), transparent);
      transform: translateX(-160%) skewX(-20deg);
      pointer-events: none;
      animation: checkGlimmerSweep 3.6s infinite ease-in-out;
    }
    .btn-check-curp:hover {
      background: linear-gradient(135deg, rgba(236, 0, 0, 0.45) 0%, rgba(38, 12, 18, 0.98) 100%);
      border-color: #ff3333;
      color: #ffffff;
      transform: translateY(-1px);
      box-shadow: 0 4px 14px rgba(236, 0, 0, 0.5), 0 0 16px rgba(236, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.3);
    }
    .btn-check-curp:active {
      transform: translateY(0.5px) scale(0.97);
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.8), inset 0 1px 2px rgba(0, 0, 0, 0.5);
    }
    .btn-check-curp .check-icon {
      font-size: 10px;
      color: #ff4d4d;
      filter: drop-shadow(0 0 4px rgba(236, 0, 0, 0.8));
      transition: transform 180ms ease;
    }
    .btn-check-curp:hover .check-icon {
      transform: scale(1.25);
      color: #ff8080;
    }

    .btn-check-retry {
      background: rgba(245, 158, 11, 0.18);
      border: 1px solid rgba(245, 158, 11, 0.55);
      color: #fbbf24;
      border-radius: 4px;
      padding: 2px 6px;
      margin-left: 5px;
      cursor: pointer;
      font-size: 12px;
      line-height: 1;
      transition: all 180ms ease;
    }
    .btn-check-retry:hover {
      background: rgba(245, 158, 11, 0.35);
      border-color: #f59e0b;
      color: #fff;
      transform: rotate(60deg);
      box-shadow: 0 0 8px rgba(245, 158, 11, 0.4);
    }

    .checking-pill {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      color: #fbbf24;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.05em;
      background: rgba(245, 158, 11, 0.12);
      border: 1px solid rgba(245, 158, 11, 0.35);
      padding: 3px 8px;
      border-radius: 4px;
      user-select: none;
    }

    /* Polished Table Hover & Focus Accents */
    tr[data-row-idx]:hover {
      background-color: rgba(236, 0, 0, 0.06) !important;
    }
    tr[data-row-idx]:hover td.row-num-cell {
      border-left: 3px solid #ec0000 !important;
      color: #f3f4f6 !important;
    }

    /* ── Bóveda de HITS VIP & Selector Maestro ── */
    .mode-nav-bar {
      display: flex;
      gap: 8px;
      margin-bottom: 8px;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }
    .nav-tab {
      background: var(--bg-card);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 7px 16px;
      border-radius: var(--radius-md);
      cursor: pointer;
      font-size: 12.5px;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: var(--transition-fast);
      letter-spacing: 0.02em;
    }
    .nav-tab:hover {
      background: var(--bg-surface-elevated);
      color: #fff;
      border-color: var(--border-strong);
    }
    .nav-tab.active {
      background: #181824;
      color: #fff;
      border-color: var(--color-primary);
      box-shadow: 0 0 10px rgba(236, 0, 0, 0.25);
    }
    .nav-tab-hits {
      border-color: rgba(16, 185, 129, 0.4);
      color: #34d399;
    }
    .nav-tab-hits.active {
      border-color: #10b981;
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      box-shadow: 0 0 14px rgba(16, 185, 129, 0.35);
    }
    .nav-badge {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 800;
      padding: 1px 7px;
      border-radius: var(--radius-full);
      background: rgba(16, 185, 129, 0.25);
      border: 1px solid rgba(16, 185, 129, 0.5);
      color: #34d399;
    }
    .hit-kpi {
      border-color: rgba(16, 185, 129, 0.45) !important;
      background: rgba(16, 185, 129, 0.08) !important;
      transition: all 180ms ease;
    }
    .hit-kpi:hover {
      background: rgba(16, 185, 129, 0.18) !important;
      border-color: #10b981 !important;
      transform: translateY(-1px);
    }
    .hit-status-select {
      background: #14141e;
      border: 1px solid var(--border-strong);
      color: #fff;
      font-size: 11px;
      font-weight: 700;
      padding: 3px 6px;
      border-radius: var(--radius-sm);
      outline: none;
      cursor: pointer;
      width: 100%;
    }
    .hit-status-select.status-ACTIVE { border-color: #10b981; color: #34d399; background: rgba(16,185,129,0.12); }
    .hit-status-select.status-SUCCESS { border-color: #3b82f6; color: #93c5fd; background: rgba(59,130,246,0.12); }
    .hit-status-select.status-OFF { border-color: #6b7280; color: #9ca3af; background: rgba(107,114,128,0.12); }

    .hit-link-santander {
      background: #064e3b;
      border: 1px solid #059669;
      color: #34d399;
      font-size: 10px;
      padding: 2px 5px;
      border-radius: 3px;
      text-decoration: none;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
      gap: 3px;
      margin-left: 4px;
    }
    .hit-link-santander:hover {
      background: #059669;
      color: #fff;
    }
    .hit-notes-input {
      background: transparent;
      border: 1px solid transparent;
      color: var(--text);
      font-size: 11.5px;
      padding: 2px 4px;
      width: 100%;
      border-radius: var(--radius-sm);
    }
    .hit-notes-input:focus {
      background: #14141e;
      border-color: var(--color-primary);
      outline: none;
      color: #fff;
    }
    .btn-hit-trabajar {
      background: linear-gradient(135deg, #059669, #0d9488);
      border: 1px solid #10b981;
      color: #ffffff;
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 4px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      transition: all 0.15s ease;
      box-shadow: 0 1px 3px rgba(0,0,0,0.3);
      white-space: nowrap;
      text-decoration: none;
    }
    .btn-hit-trabajar:hover {
      background: linear-gradient(135deg, #10b981, #14b8a6);
      border-color: #34d399;
      transform: translateY(-1px);
      box-shadow: 0 3px 8px rgba(16, 185, 129, 0.35);
    }
    .btn-hit-trabajar:active {
      transform: translateY(0);
    }
    .excel-header.sortable-th {
      user-select: none;
      cursor: pointer;
      transition: background 0.15s ease;
    }
    .excel-header.sortable-th:hover {
      background: #182238 !important;
      color: #fff;
    }
    .excel-header.sortable-th .th-title-wrap {
      display: flex;
      align-items: center;
      gap: 3px;
      width: 100%;
    }
    .excel-header.sortable-th .sort-indicator {
      color: #38bdf8;
      font-size: 10px;
      font-weight: 900;
    }
  </style>
</head>
<body>

  <!-- Lock Screen Overlay -->
  <div id="lock-screen">
    <div class="lock-card">
      <div class="lock-icon-circle">🔒</div>
      <div class="santa-brand-logo lock-logo">
        <span class="logo-pill-santa brand-santa">SANTA</span>
        <span class="logo-icon-pray brand-pray">🙏🏻</span>
        <span class="logo-text-base brand-base">BASE</span>
      </div>
      <p class="lock-subtitle">Autenticación Segura Multi-Usuario — Bóveda Operativa (4.9M Registros)</p>
      
      <div class="login-field-group">
        <label class="login-label">Usuario</label>
        <input type="text" id="login-username" class="login-input" 
               placeholder="Escribe tu usuario (ej. Robertvs)..." 
               autocomplete="username" autocapitalize="words" spellcheck="false"
               onkeydown="if(event.key==='Enter') document.getElementById('login-password')?.focus()">
        <span class="login-hint">🔒 Sensible a mayúsculas. La 1ra letra debe ser Mayúscula.</span>
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

  <!-- Top Bar -->
  <div class="top-bar">
    <div class="brand-group">
      <div class="santa-brand-logo" title="Santa Base">
        <span class="logo-pill-santa brand-santa">SANTA</span>
        <span class="logo-icon-pray brand-pray">🙏🏻</span>
        <span class="logo-text-base brand-base">BASE</span>
      </div>
    </div>
    <div class="stats-group">
      <div class="kpi-card" title="Total de registros en base de datos">
        <span class="kpi-label">Total</span>
        <span class="kpi-val" id="stat-total">...</span>
      </div>
      <div class="kpi-card curp" title="CURPs totales registradas">
        <span class="kpi-label">Con CURP</span>
        <span class="kpi-val" id="stat-curp">...</span>
      </div>
      <div class="kpi-card calc" title="CURPs calculadas por el motor">
        <span class="kpi-label">Calculadas</span>
        <span class="kpi-val" id="stat-calc">...</span>
      </div>
      <div class="kpi-card missing" title="Falta CURP por calcular">
        <span class="kpi-label">Falta CURP</span>
        <span class="kpi-val" id="stat-no-curp">...</span>
      </div>
      <div class="kpi-card results" title="Con resultados de consulta">
        <span class="kpi-label">Resultados</span>
        <span class="kpi-val" id="stat-results">...</span>
      </div>
      <div class="kpi-card hit-kpi" onclick="switchViewMode('hits')" style="cursor: pointer;" title="Abrir Bóveda Exclusiva de HITS">
        <span class="kpi-label" style="color: #34d399; font-weight: 700;">🟢 Bóveda HITS</span>
        <span class="kpi-val" id="stat-hits" style="color: #34d399;">...</span>
      </div>
      <div class="user-pill role-superadmin" id="current-user-badge" title="Sesión activa">👑 RobertVS</div>
      <button class="btn-logout" onclick="doLogout()" title="Cerrar sesión">Salir</button>
    </div>
  </div>

  <!-- Selector Maestro de Vista (Explorador 4.9M vs Bóveda HITS) -->
  <div class="mode-nav-bar">
    <div style="display: flex; gap: 8px; align-items: center;">
      <button id="nav-btn-general" class="nav-tab active" onclick="switchViewMode('general')">
        📊 Explorador General (4.9M)
      </button>
      <button id="nav-btn-hits" class="nav-tab nav-tab-hits" onclick="switchViewMode('hits')">
        🟢 BÓVEDA HITS VIP <span class="nav-badge" id="nav-hits-badge">0</span>
      </button>
    </div>
    <div id="hits-quick-actions" style="display: none; gap: 8px; align-items: center;">
      <button class="btn btn-outline" onclick="copyHitsCurps()" title="Copiar todas las CURPs de esta vista de hits">📋 Copiar CURPs HITS</button>
      <button class="btn btn-excel" onclick="exportHitsCsv()" title="Descargar CSV con todos los HITS">⬇️ Exportar HITS (CSV)</button>
    </div>
  </div>

  <!-- Contenedor Explorador General -->
  <div id="general-view-container" style="display: flex; flex-direction: column; flex: 1; min-height: 0;">
    <!-- Mega-Buscador (Command Center de 4.9M Registros) -->
    <div class="mega-search-bar search-input-wrap" id="mega-search-bar">
      <div class="mega-search-icon">🔍</div>
      <div class="mega-filter-badge" id="mega-filter-badge" onclick="cyclePresetFilter()" title="Ámbito de búsqueda activo. Clic para alternar.">
        <span id="mega-filter-badge-text">TODOS</span>
      </div>
      <input type="text" id="global-search" class="mega-search-input" 
             placeholder="Buscar en 4.9M de registros (RFC, Nombre, CURP, Ciudad, Tarjeta, CP...) — Atajo: (Ctrl+K) o /" 
             onkeydown="if(event.key==='Enter') applyGlobalSearch(); else if(event.key==='Escape') clearGlobalSearch();" 
             oninput="toggleSearchClearBtn()">
      <button id="btn-clear-search" class="mega-search-clear-btn" onclick="clearGlobalSearch()" title="Limpiar búsqueda (Esc)" style="display:none;">✕</button>
      <button class="btn btn-primary mega-search-submit-btn" onclick="applyGlobalSearch()" title="Ejecutar búsqueda">
        <span>Buscar</span>
        <span class="search-btn-badge">↵</span>
      </button>
    </div>

    <!-- Toolbar con 4 Clusters Visuales y Segmented Control -->
    <div class="toolbar">
      <!-- 1. Filtros Predefinidos (Segmented Control) -->
      <div class="tb-group">
        <div class="filter-tabs">
          <button class="tab-btn active" onclick="setPresetFilter('all')">Todos</button>
          <button class="tab-btn" onclick="setPresetFilter('no_curp')">Falta CURP</button>
          <button class="tab-btn" onclick="setPresetFilter('has_curp')">Con CURP</button>
          <button class="tab-btn" onclick="setPresetFilter('calculada')">Calculadas</button>
          <button class="tab-btn" onclick="setPresetFilter('no_calculable')">No Calculables</button>
          <button class="tab-btn" onclick="setPresetFilter('has_results')">Con Result</button>
        </div>
      </div>

      <div class="tb-sep"></div>

      <!-- 2. Selección / Copia RFCs & CURPs -->
      <div class="tb-group">
        <button class="btn" onclick="copySelectedRfcs()" title="Copiar RFCs de filas seleccionadas">📋 Copiar RFCs (<span id="sel-count">0</span>)</button>
        <button class="btn btn-curp" onclick="copySelectedCurps()" title="Copiar CURPs de filas seleccionadas">📋 Copiar CURPs (<span id="sel-curp-count">0</span>)</button>
        <button class="btn btn-outline" onclick="copyPageRfcs()" title="Copiar todos los RFCs de la página">📄 RFCs Pág</button>
        <button class="btn btn-outline" onclick="copyPageCurps()" title="Copiar todas las CURPs de la página">📄 CURPs Pág</button>
        <button class="btn btn-danger-outline" id="btn-clear-selection" onclick="clearSelection()" title="Limpiar selección" style="display:none; padding: 4px 8px;">✕</button>
        <button class="btn btn-primary" id="btn-copy-range" onclick="copyCellRangeSelection()" title="Copiar celdas seleccionadas" style="display:none;">🎯 Copiar Selección (<span id="range-sel-count">0</span>)</button>
        <button class="btn btn-danger-outline" id="btn-clear-range" onclick="clearCellRangeSelection()" title="Limpiar selección de celdas" style="display:none; padding: 4px 8px;">✕</button>
      </div>

      <div class="tb-sep"></div>

      <!-- 3. Acciones CURP Masivas -->
      <div class="tb-group">
        <button class="btn btn-outline" onclick="openBulkCurpModal()">📥 Pegar CURPs (/cep)</button>
      </div>

      <div class="tb-sep"></div>

      <!-- 4. Exportar & Reset -->
      <div class="tb-group">
        <button class="btn btn-excel" onclick="exportCsv()">⬇️ Exportar CSV</button>
        <button class="btn btn-danger-outline" id="btn-clear-all-filters" onclick="clearAllFilters()" style="display:none;">✖ Limpiar Filtros</button>
      </div>

      <div class="tb-sep"></div>

      <!-- 5. Control del Purger -->
      <div class="tb-group">
        <button class="btn" id="btn-purger-toggle" onclick="togglePurger()" title="Pausar/Reanudar el purger automático">⏸️ Pausar Purger</button>
        <span id="purger-state-badge" style="font-size:11px; padding:2px 8px; border-radius:10px; background:#374151; color:#9ca3af;">—</span>
      </div>
    </div>

    <!-- Active Filters Indicator Bar -->
    <div id="active-filters-bar">
      <span style="font-weight:700; color:#38bdf8;">Filtros activos:</span>
      <div id="active-filters-chips" style="display:flex; gap:5px; flex-wrap:wrap;"></div>
    </div>

    <!-- Grid Table Container -->
    <div class="grid-container" id="grid-container" style="flex: 1; min-height: 0;">
      <table class="excel-table" id="excel-table">
        <thead>
          <tr id="header-row"></tr>
        </thead>
        <tbody id="table-body">
          <tr><td colspan="22" style="text-align:center; padding: 40px; color: var(--text-muted);">Cargando registros de Santander...</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination Bar -->
    <div class="pagination-bar">
      <div id="page-info">Mostrando 0 de 0 registros</div>
      <div class="page-controls">
        <label>Por pág: 
          <select id="limit-select" onchange="changeLimit()" style="background:#090d16; border:1px solid var(--border); color:#fff; padding:2px 5px; border-radius:4px; font-size:10.5px;">
            <option value="25">25</option>
            <option value="50">50</option>
            <option value="100">100</option>
            <option value="200" selected>200</option>
            <option value="500">500</option>
          </select>
        </label>
        <button class="btn btn-outline" id="btn-prev" onclick="prevPage()">◀ Anterior</button>
        <span id="page-num" style="font-weight: 700; font-family:var(--font-mono); padding: 0 4px;">1 / 1</span>
        <button class="btn btn-outline" id="btn-next" onclick="nextPage()">Siguiente ▶</button>
      </div>
    </div>
  </div>

  <!-- Vista Dedicada Bóveda de HITS VIP -->
  <div id="hits-view-container" style="display:none; flex-direction: column; flex: 1; min-height: 0;">
    <div class="toolbar hits-toolbar">
      <div class="tb-group">
        <div class="filter-tabs">
          <button id="hits-tab-all" class="tab-btn active" onclick="setHitsStatusFilter('all')">Todos (<span id="hits-count-all">0</span>)</button>
          <button id="hits-tab-active" class="tab-btn" onclick="setHitsStatusFilter('ACTIVE')" style="color: #34d399;">🟢 Activos (<span id="hits-count-active">0</span>)</button>
          <button id="hits-tab-success" class="tab-btn" onclick="setHitsStatusFilter('SUCCESS')" style="color: #60a5fa;">✅ Success (<span id="hits-count-success">0</span>)</button>
          <button id="hits-tab-off" class="tab-btn" onclick="setHitsStatusFilter('OFF')" style="color: #9ca3af;">⚪ Off (<span id="hits-count-off">0</span>)</button>
        </div>
      </div>

      <div class="tb-sep"></div>

      <div class="tb-group" style="flex: 1; max-width: 380px;">
        <input type="text" id="hits-search-input" class="global-search" style="width: 100%;"
               placeholder="Buscar en HITS (CURP, Nombre, Estado, Ciudad, Tarjeta, CP...)"
               onkeydown="if(event.key==='Enter') applyHitsSearch();"
               oninput="if(this.value==='') applyHitsSearch();">
      </div>

      <div class="tb-sep"></div>

      <div class="tb-group">
        <label style="font-size: 11px; color: var(--text-muted);">Ordenar:
          <select id="hits-sort-select" onchange="changeHitsSort()" style="background: var(--bg-app); border: 1px solid var(--border-strong); color: #fff; padding: 4px 8px; border-radius: var(--radius-sm); font-size: 11px;">
            <option value="checked_at:desc" selected>Más recientes</option>
            <option value="u6licrea:desc">Mayor Crédito ($)</option>
            <option value="estado:asc">Estado (A-Z)</option>
            <option value="work_status:asc">Estatus</option>
          </select>
        </label>
        <button class="btn btn-outline" onclick="fetchHits()" title="Recargar tabla de Hits">↻ Recargar</button>
      </div>
    </div>

    <!-- Contenedor Tabla de HITS VIP -->
    <div class="grid-container" id="hits-grid-container" style="flex: 1; min-height: 0;">
      <table class="excel-table" id="hits-table">
        <thead>
          <tr id="hits-header-row">
            <th class="excel-header row-num-header" style="width: 40px; text-align: center;">#</th>
            <th class="excel-header sortable-th" style="width: 120px;" onclick="toggleHitsSort('work_status')" title="Clic para ordenar por Status">
              <div class="th-title-wrap">STATUS <span id="th-hits-sort-work_status" class="sort-indicator"></span></div>
            </th>
            <th class="excel-header sortable-th" style="width: 165px;" onclick="toggleHitsSort('u6acct')" title="Clic para ordenar por Tarjeta">
              <div class="th-title-wrap">TARJETA <span id="th-hits-sort-u6acct" class="sort-indicator"></span></div>
            </th>
            <th class="excel-header sortable-th" style="width: 180px;" onclick="toggleHitsSort('curp')" title="Clic para ordenar por CURP">
              <div class="th-title-wrap">CURP <span id="th-hits-sort-curp" class="sort-indicator"></span></div>
            </th>
            <th class="excel-header sortable-th" style="width: 220px;" onclick="toggleHitsSort('dmname')" title="Clic para ordenar por Nombre">
              <div class="th-title-wrap">NOMBRE COMPLETO <span id="th-hits-sort-dmname" class="sort-indicator"></span></div>
            </th>
            <th class="excel-header sortable-th" style="width: 125px; text-align: right;" onclick="toggleHitsSort('u6licrea')" title="Clic para ordenar por Límite de Crédito">
              <div class="th-title-wrap" style="justify-content: flex-end;">LÍMITE CRÉDITO <span id="th-hits-sort-u6licrea" class="sort-indicator"></span></div>
            </th>
            <th class="excel-header sortable-th" style="width: 130px;" onclick="toggleHitsSort('estado')" title="Clic para ordenar por Estado">
              <div class="th-title-wrap">ESTADO <span id="th-hits-sort-estado" class="sort-indicator"></span></div>
            </th>
            <th class="excel-header sortable-th" style="width: 130px;" onclick="toggleHitsSort('ciudad')" title="Clic para ordenar por Ciudad">
              <div class="th-title-wrap">CIUDAD <span id="th-hits-sort-ciudad" class="sort-indicator"></span></div>
            </th>
            <th class="excel-header sortable-th" style="width: 85px; text-align: center;" onclick="toggleHitsSort('codigo_postal')" title="Clic para ordenar por Código Postal">
              <div class="th-title-wrap" style="justify-content: center;">CP <span id="th-hits-sort-codigo_postal" class="sort-indicator"></span></div>
            </th>
            <th class="excel-header" style="width: 260px;">DIRECCIÓN</th>
            <th class="excel-header sortable-th" style="width: 110px;" onclick="toggleHitsSort('operador')" title="Clic para ordenar por Operador">
              <div class="th-title-wrap">OPERADOR <span id="th-hits-sort-operador" class="sort-indicator"></span></div>
            </th>
            <th class="excel-header" style="width: 200px;">NOTAS</th>
            <th class="excel-header sortable-th" style="width: 135px;" onclick="toggleHitsSort('checked_at')" title="Clic para ordenar por Fecha">
              <div class="th-title-wrap">DETECCIÓN <span id="th-hits-sort-checked_at" class="sort-indicator"></span></div>
            </th>
          </tr>
        </thead>
        <tbody id="hits-table-body">
          <tr><td colspan="13" style="text-align:center; padding: 40px; color: var(--text-muted);">Cargando Bóveda de HITS...</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Paginación de HITS -->
    <div class="pagination-bar" id="hits-pagination-bar">
      <div id="hits-page-info">Mostrando 0 de 0 hits</div>
      <div class="page-controls">
        <label>Por pág: 
          <select id="hits-limit-select" onchange="changeHitsLimit()" style="background:#090d16; border:1px solid var(--border); color:#fff; padding:2px 5px; border-radius:4px; font-size:10.5px;">
            <option value="50">50</option>
            <option value="100" selected>100</option>
            <option value="200">200</option>
          </select>
        </label>
        <button class="btn btn-outline" id="btn-hits-prev" onclick="prevHitsPage()">◀ Anterior</button>
        <span id="hits-page-num" style="font-weight: 700; font-family:var(--font-mono); padding: 0 4px;">1 / 1</span>
        <button class="btn btn-outline" id="btn-hits-next" onclick="nextHitsPage()">Siguiente ▶</button>
      </div>
    </div>
  </div>

  <!-- Column Filter Popover -->
  <div class="filter-popover" id="filter-popover">
    <div class="popover-header">
      <span id="popover-title">Filtro de Columna</span>
      <span class="popover-close" onclick="closeFilterPopover()">✕</span>
    </div>
    <div class="popover-sort-btns">
      <button class="sort-menu-btn" onclick="applySort('asc')">▲ Ordenar A-Z / Menor a Mayor</button>
      <button class="sort-menu-btn" onclick="applySort('desc')">▼ Ordenar Z-A / Mayor a Menor</button>
    </div>
    <div class="popover-divider"></div>
    <div class="popover-input-group">
      <label style="font-size:9.5px; color:var(--text-muted); text-transform:uppercase;">Condición:</label>
      <select id="popover-operator" class="popover-select" onchange="onOperatorChange()">
        <option value="contains">Contiene...</option>
        <option value="starts_with">Empieza con...</option>
        <option value="equals">Es igual a...</option>
        <option value="not_empty">No vacíos (Con datos)</option>
        <option value="empty">Vacíos (Sin datos)</option>
      </select>
      <input type="text" id="popover-filter-val" class="popover-input" placeholder="Texto a buscar..." onkeydown="if(event.key==='Enter') applyColumnFilter()">
    </div>
    <div class="popover-actions">
      <button class="btn btn-outline" onclick="clearCurrentColumnFilter()" style="font-size:10px;">Limpiar</button>
      <button class="btn btn-excel" onclick="applyColumnFilter()" style="font-size:10px;">Aplicar</button>
    </div>
  </div>

  <!-- Custom Context Menu -->
  <div class="context-menu" id="context-menu">
    <div class="ctx-header">Acciones Rápidas</div>
    <div class="ctx-item ctx-highlight" id="ctx-range-item" onclick="copyCellRangeSelection()" style="display:none;">
      <span>🎯 Copiar Rango</span>
      <span class="ctx-badge" id="ctx-range-badge">0</span>
    </div>
    <div class="ctx-item" onclick="ctxCopyCell()">
      <span>📋 Copiar Celda</span>
      <span class="ctx-shortcut">Ctrl+C</span>
    </div>
    <div class="ctx-item" onclick="ctxCopyRfc()">
      <span>📄 Copiar RFC</span>
      <span class="ctx-shortcut">RFC</span>
    </div>
    <div class="ctx-item" onclick="ctxCopyRow()">
      <span>📑 Copiar Fila TSV</span>
      <span class="ctx-shortcut">TSV</span>
    </div>
    <div class="ctx-sep"></div>
    <div class="ctx-item" id="ctx-paste-item" onclick="ctxPasteCell()">
      <span>📥 Pegar CURP</span>
      <span class="ctx-shortcut">Ctrl+V</span>
    </div>
    <div class="ctx-item ctx-item-danger" id="ctx-clear-item" onclick="ctxClearCell()">
      <span>🧹 Borrar CURP</span>
      <span class="ctx-shortcut">Supr</span>
    </div>
    <div class="ctx-sep"></div>
    <div class="ctx-item" onclick="ctxMarkResult('HIT')">
      <span>🟢 Marcar HIT</span>
      <span class="ctx-shortcut">HIT</span>
    </div>
    <div class="ctx-item" onclick="ctxMarkResult('DEAD')">
      <span>🔴 Marcar DEAD</span>
      <span class="ctx-shortcut">DEAD</span>
    </div>
  </div>

  <!-- Bulk CURP Modal -->
  <div class="modal" id="bulk-curp-modal">
    <div class="modal-content">
      <h3 style="font-size: 14px; font-weight:700;">Pegar Resultados de /cep (CURPs)</h3>
      <p style="font-size: 10.5px; color: var(--text-muted);">Pega la respuesta de Ruthopia o lista de CURPs. Se emparejarán automáticamente por tarjeta o por los 10 primeros dígitos del RFC:</p>
      <textarea id="bulk-curp-text" class="modal-textarea" placeholder="Pega aquí la salida de /cep..."></textarea>
      <div style="display: flex; justify-content: flex-end; gap: 6px;">
        <button class="btn btn-outline" onclick="closeBulkCurpModal()">Cancelar</button>
        <button class="btn btn-success" onclick="submitBulkCurp()">Procesar e Importar</button>
      </div>
    </div>
  </div>

  <div id="toast">Mensaje</div>

  <script>
    const BASE_PATH = window.location.pathname.startsWith('/santabase') ? '/santabase' : (window.location.pathname.startsWith('/santander') ? '/santander' : '');

    // ORDEN OPTIMIZADO: ID + RFC + CURP + NOMBRE caben sin scroll al abrir
    const COLUMNS = [
      { key: "curp", label: "CURP", letter: "A", width: "175px", mono: true, sticky: true, editable: true },
      { key: "u6rfc", label: "RFC", letter: "B", width: "135px", mono: true, sticky: true, editable: false },
      { key: "dmname", label: "NOMBRE COMPLETO", letter: "C", width: "220px", mono: false, editable: false },
      { key: "estado", label: "ESTADO", letter: "D", width: "140px", mono: false, editable: false },
      { key: "ciudad", label: "CIUDAD", letter: "E", width: "140px", mono: false, editable: false },
      { key: "codigo_postal", label: "C.P.", letter: "F", width: "65px", mono: true, editable: false },
      { key: "direccion", label: "DIRECCIÓN COMPLETA", letter: "G", width: "320px", mono: false, editable: false },
      { key: "u6licrea", label: "LÍMITE CRÉDITO", letter: "H", width: "115px", mono: true, editable: false },
      { key: "results", label: "RESULTS", letter: "I", width: "125px", mono: false, editable: false },
      { key: "u6acct", label: "TARJETA (16D)", letter: "J", width: "155px", mono: true, editable: false },
      { key: "genero", label: "GÉNERO", letter: "K", width: "65px", mono: true, editable: false },
      { key: "curp_status", label: "ESTADO CURP", letter: "L", width: "105px", mono: true, editable: false },
      { key: "curp_falta", label: "MOTIVO FALTA", letter: "M", width: "110px", mono: true, editable: false },
      { key: "u6tel1", label: "TELÉFONO 1", letter: "N", width: "105px", mono: true, editable: false },
      { key: "u6tel2", label: "TELÉFONO 2", letter: "O", width: "105px", mono: true, editable: false },
      { key: "u6cvereg", label: "CVE REG", letter: "P", width: "75px", mono: true, editable: false },
      { key: "u6numcto", label: "NUM CTO", letter: "Q", width: "85px", mono: true, editable: false },
      { key: "dmssnum", label: "SS NUM", letter: "R", width: "80px", mono: true, editable: false },
      { key: "id", label: "ID", letter: "S", width: "65px", mono: true, editable: false }
    ];

    let currentPage = 1;
    let currentLimit = 200; // Default 200 según requerimiento
    let currentPresetFilter = 'all';
    let currentGlobalSearch = '';
    let currentSortBy = 'id';
    let currentSortDir = 'asc';
    let columnFilters = {};
    let selectedRowIds = new Set();
    let currentRecords = [];

    let activeRowIndex = 0;
    let activeColIndex = 2; // Por defecto sobre CURP
    let isEditingCell = false;
    let cellEditorElem = null;

    // --- Selección de rango de celdas por columna (arrastrar / Ctrl+arrastrar multi-segmento) ---
    // segments: array de {colIdx, start, end} ya confirmados (soltados)
    // drag: segmento en curso mientras el mouse está presionado, o null
    let cellRangeSelection = { segments: [], drag: null };
    let suppressNextCellTextClick = false;

    // Cálculo dinámico de posiciones sticky sumando anchos reales
    function updateStickyOffsets() {
      const rowNumWidth = 38;
      const chkWidth = 30;
      let cumLeft = rowNumWidth + chkWidth;

      COLUMNS.forEach(col => {
        if (col.sticky) {
          col.stickyLeft = cumLeft;
          cumLeft += parseInt(col.width, 10) || 60;
        } else {
          col.stickyLeft = null;
        }
      });
    }
    updateStickyOffsets();

    // Formato RFC con contraste en los 6 dígitos de fecha
    function formatRfcHtml(rfc) {
      if (!rfc) return '';
      const str = String(rfc).trim().toUpperCase();
      const m = str.match(/^([A-Za-z\u00d1\u00f1&]{3,4})([0-9]{6})([A-Za-z0-9]{3})?$/);
      if (m) {
        const prefix = escapeHtml(m[1]);
        const birth = escapeHtml(m[2]);
        const homoclave = escapeHtml(m[3] || '');
        return `${prefix}<span class="rfc-date" title="Fecha en RFC: ${birth}">${birth}</span>${homoclave}`;
      }
      return escapeHtml(str);
    }

    // Copia al hacer clic en el TEXTO (sin seleccionar celda)
    function copyInlineText(e, text, label) {
      if (e) {
        e.stopPropagation();
        e.preventDefault();
      }
      if (suppressNextCellTextClick) { suppressNextCellTextClick = false; return; }
      if (!text) return;
      const cleanText = String(text).trim();

      const showPill = () => {
        if (e && e.clientX && e.clientY) {
          const badge = document.createElement('div');
          badge.className = 'inline-copy-feedback';
          badge.innerText = `✓ Copiado`;
          badge.style.left = `${Math.min(window.innerWidth - 80, Math.max(10, e.clientX - 30))}px`;
          badge.style.top = `${Math.max(10, e.clientY - 25)}px`;
          document.body.appendChild(badge);
          setTimeout(() => { if (badge.parentNode) badge.parentNode.removeChild(badge); }, 750);
        } else {
          showToast(`✓ ${label || 'Dato'} copiado`);
        }
      };

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(cleanText).then(showPill).catch(() => {
          fallbackCopy(cleanText);
          showPill();
        });
      } else {
        fallbackCopy(cleanText);
        showPill();
      }
    }

    function fallbackCopy(text) {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      try { document.execCommand('copy'); } catch(err){}
      document.body.removeChild(ta);
    }

    // Resizing de columnas
    let resizingColKey = null;
    let resizeStartX = 0;
    let resizeStartWidth = 0;

    function initColResize(e, colKey) {
      e.stopPropagation();
      e.preventDefault();
      resizingColKey = colKey;
      resizeStartX = e.clientX;
      const colObj = COLUMNS.find(c => c.key === colKey);
      resizeStartWidth = parseInt(colObj ? colObj.width : '100', 10) || 100;
      document.body.classList.add('resizing-col');
      window.addEventListener('mousemove', handleColResize);
      window.addEventListener('mouseup', stopColResize);
    }

    function handleColResize(e) {
      if (!resizingColKey) return;
      const delta = e.clientX - resizeStartX;
      const newWidth = Math.max(45, resizeStartWidth + delta);
      const colObj = COLUMNS.find(c => c.key === resizingColKey);
      if (colObj) {
        colObj.width = newWidth + 'px';
        const th = document.querySelector(`th[data-col-key="${resizingColKey}"]`);
        if (th) {
          th.style.width = colObj.width;
          th.style.minWidth = colObj.width;
          th.style.maxWidth = colObj.width;
        }
        document.querySelectorAll(`td[data-col-key="${resizingColKey}"]`).forEach(td => {
          td.style.width = colObj.width;
          td.style.minWidth = colObj.width;
          td.style.maxWidth = colObj.width;
        });
        updateStickyOffsets();
      }
    }

    function stopColResize() {
      if (!resizingColKey) return;
      resizingColKey = null;
      document.body.classList.remove('resizing-col');
      window.removeEventListener('mousemove', handleColResize);
      window.removeEventListener('mouseup', stopColResize);
    }


    let currentUser = null;

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
      setTimeout(() => document.getElementById('login-username')?.focus(), 100);
    }

    function hideLockScreen() {
      document.getElementById('lock-screen').classList.add('hidden');
    }

    function togglePasswordVisibility() {
      const input = document.getElementById('login-password');
      input.type = input.type === 'password' ? 'text' : 'password';
    }

    async function submitLogin() {
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
      }

      try {
        const res = await fetch(`${BASE_PATH}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: username, password: pass })
        });
        const data = await res.json();
        if (res.ok && (data.authenticated || data.ok)) {
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
      if (document.getElementById('login-password')) document.getElementById('login-password').value = '';
      if (document.getElementById('login-username')) document.getElementById('login-username').value = '';
      showLockScreen();
    }

        function animateCounter(elementId, targetValue) {
      const el = document.getElementById(elementId);
      if (!el) return;
      if (typeof anime === 'undefined') {
        el.innerText = Number(targetValue).toLocaleString();
        return;
      }
      const rawCurrent = parseInt((el.innerText || '0').replace(/[^0-9]/g, '')) || 0;
      const obj = { val: rawCurrent };
      anime({
        targets: obj,
        val: targetValue,
        round: 1,
        duration: 900,
        easing: 'easeOutExpo',
        update: function() {
          el.innerText = obj.val.toLocaleString();
        }
      });
    }

    // Micro-interacción háptica elástica en botones con Anime.js
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn, .btn-login, .tab-btn, .mega-search-clear-btn');
      if (btn && typeof anime !== 'undefined') {
        anime({
          targets: btn,
          scale: [0.95, 1],
          duration: 180,
          easing: 'easeOutQuad'
        });
      }
    });

function initApp() {
      syncMegaFilterBadge();
      buildHeaderRow();
      fetchStats();
      loadRecords();
      setupKeyboardListeners();
      setupFormulaBarListener();
    }

    function showToast(text) {
      const t = document.getElementById('toast');
      t.innerText = text;
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 2200);
    }

    async function fetchStats() {
      try {
        const res = await fetch(`${BASE_PATH}/api/stats`);
        if (res.status === 401) { showLockScreen(); return; }
        const data = await res.json();
        animateCounter('stat-total', data.total);
        animateCounter('stat-curp', data.with_curp);
        animateCounter('stat-calc', data.curp_calculada || 0);
        animateCounter('stat-no-curp', data.without_curp);
        animateCounter('stat-results', data.with_results);
        if (data.hits_total !== undefined) {
          animateCounter('stat-hits', data.hits_total);
          const navBadge = document.getElementById('nav-hits-badge');
          if (navBadge) navBadge.innerText = Number(data.hits_total).toLocaleString();
        }
      } catch(e) { console.error(e); }
    }

    function buildHeaderRow() {
      const headerRow = document.getElementById('header-row');
      let html = `
        <th class="excel-header row-num-header" style="left:0px;">#</th>
        <th class="excel-header" style="width: 30px; min-width: 30px; max-width: 30px; left: 38px; position: sticky; z-index: 30; text-align:center; background:#0a0f1b; border-right:1px solid #27354f;">
          <input type="checkbox" id="select-all" onchange="toggleSelectAll()">
        </th>
      `;

      COLUMNS.forEach((col) => {
        const hasFilter = !!columnFilters[col.key];
        const isSorted = currentSortBy === col.key;
        const sortIcon = isSorted ? (currentSortDir === 'asc' ? '▲' : '▼') : '';
        const editableBadge = col.editable ? '<span class="th-editable-pill">✏️</span>' : '';
        const stickyStyle = col.sticky ? `position: sticky; left: ${col.stickyLeft}px; z-index: 30; background: #0e1627; box-shadow: 2px 0 6px rgba(0,0,0,0.5);` : '';

        html += `
          <th class="excel-header" 
            style="width: ${col.width}; min-width: ${col.width}; max-width: ${col.width}; ${stickyStyle}" 
            title="${escapeHtml(col.label)} (${col.letter})"
            data-col-key="${col.key}">
            <div class="th-inner">
              <div class="th-title-wrap" title="${escapeHtml(col.label)}">
                <span class="col-letter">${col.letter}</span>
                <span class="th-title">${escapeHtml(col.label)}</span>
                ${editableBadge}
                ${sortIcon ? `<span class="sort-indicator">${sortIcon}</span>` : ''}
              </div>
              <div class="header-btns">
                <button class="filter-btn ${hasFilter ? 'has-filter' : ''}" 
                  title="Filtro/Orden (${escapeHtml(col.label)})" 
                  onclick="openFilterPopover(event, '${col.key}')">⛛</button>
              </div>
            </div>
            <div class="col-resizer" onmousedown="initColResize(event, '${col.key}')" title="Arrastra para cambiar ancho"></div>
          </th>
        `;
      });

      headerRow.innerHTML = html;
    }

    async function loadRecords() {
      const tbody = document.getElementById('table-body');
      tbody.innerHTML = '<tr><td colspan="22" style="text-align:center; padding: 40px; color: var(--text-muted);">Cargando datos...</td></tr>';

      const colFiltersJson = Object.keys(columnFilters).length > 0 ? JSON.stringify(columnFilters) : '';
      const params = new URLSearchParams({
        page: currentPage,
        limit: currentLimit,
        filter: currentPresetFilter,
        search: currentGlobalSearch,
        sort_by: currentSortBy,
        sort_dir: currentSortDir
      });
      if (colFiltersJson) params.append('col_filters', colFiltersJson);

      try {
        const t0 = performance.now();
        const res = await fetch(`${BASE_PATH}/api/records?${params.toString()}`);
        if (res.status === 401) { showLockScreen(); return; }
        const data = await res.json();
        currentRecords = data.records;

        document.getElementById('page-num').innerText = `${data.page} / ${data.total_pages}`;
        document.getElementById('page-info').innerText = `Mostrando ${data.records.length} de ${data.total.toLocaleString()} registros`;
        document.getElementById('btn-prev').disabled = data.page <= 1;
        document.getElementById('btn-next').disabled = data.page >= data.total_pages;

        updateActiveFilterChips();

        if (data.records.length === 0) {
          tbody.innerHTML = '<tr><td colspan="22" style="text-align:center; padding: 40px; color: var(--text-muted);">No se encontraron registros con los filtros actuales.</td></tr>';
          return;
        }

        const tRender0 = performance.now();
        let html = '';
        data.records.forEach((r, rIdx) => {
          const isRowChecked = selectedRowIds.has(r.id);
          const rowNum = (currentPage - 1) * currentLimit + rIdx + 1;

          html += `<tr id="row-${r.id}" data-row-idx="${rIdx}" class="${isRowChecked ? 'row-selected' : ''}">`;
          html += `<td class="row-num-cell" style="left:0px;" onmousedown="handleRowSelectMouseDown(event, ${rIdx})" title="Clic o arrastra para seleccionar">${rowNum}</td>`;
          html += `<td class="excel-cell select-col-cell" style="left:38px; position: sticky; z-index: 10; width: 34px;" onmousedown="handleRowSelectMouseDown(event, ${rIdx})" title="Clic o arrastra para marcar fila">
            <input type="checkbox" class="row-checkbox" value="${r.id}" ${isRowChecked ? 'checked' : ''}>
          </td>`;

          COLUMNS.forEach((col, cIdx) => {
            const rawVal = r[col.key] !== null && r[col.key] !== undefined ? String(r[col.key]) : '';
            let displayContent = escapeHtml(rawVal);

            if (col.key === 'u6rfc' && rawVal) {
              const rfcHtml = formatRfcHtml(rawVal);
              displayContent = `<span class="copyable-text rfc-text" onclick="copyInlineText(event, '${escapeHtml(rawVal)}', 'RFC')" title="Clic en texto para copiar RFC">${rfcHtml}</span>`;
            } else if (col.key === 'curp') {
              if (rawVal) {
                displayContent = `<span class="copyable-text curp-text" onclick="copyInlineText(event, '${escapeHtml(rawVal)}', 'CURP')" title="Clic en texto para copiar CURP">${escapeHtml(rawVal)}</span>`;
              } else {
                displayContent = `<span class="curp-empty" onclick="event.stopPropagation(); startCellEdit(${rIdx}, ${cIdx})" title="Doble clic o Enter para ingresar CURP">+ CURP</span>`;
              }
            } else if (col.key === 'u6acct' && rawVal) {
              displayContent = `<span class="copyable-text card-text" onclick="copyInlineText(event, '${escapeHtml(rawVal)}', 'Tarjeta')" title="Clic en texto para copiar Tarjeta">${escapeHtml(rawVal)}</span>`;
            } else if (col.key === 'u6licrea' && rawVal) {
              const numVal = parseInt(rawVal, 10);
              const formattedLim = !isNaN(numVal) ? '$' + numVal.toLocaleString('es-MX') : '$' + rawVal;
              displayContent = `<span class="limite-text" title="Límite: ${formattedLim}">${formattedLim}</span>`;
            } else if (col.key === 'curp_status' && rawVal) {
              displayContent = `<span class="status-badge status-${rawVal}">${rawVal}</span>`;
            } else if (col.key === 'curp_falta' && rawVal) {
              displayContent = `<span class="falta-badge">${rawVal}</span>`;
            } else if (col.key === 'genero' && rawVal) {
              const gColor = rawVal === 'H' ? '#60a5fa' : '#f472b6';
              displayContent = `<span style="color:${gColor}; font-weight:700;">${rawVal}</span>`;
            } else if (col.key === 'results') {
              let displayUI = '';
              const isLive = (rawVal === 'HIT' || rawVal === 'LIVE' || rawVal === 'ON');
              const isNeg = isNegativeResult(rawVal);
              if (!rawVal) {
                 displayUI = `<button class="btn-check-curp" onclick="runCheck(event, ${rIdx}, ${cIdx})" title="Verificar elegibilidad en Onboarding Santander"><span class="check-icon">⚡</span> CHECK</button>`;
              } else if (isLive) {
                const curpVal = escapeHtml(r.curp || '');
                displayUI = `<span class="tag-btn hit" onclick="copyInlineText(event, '${curpVal}', 'CURP')" title="Elegible Santander (Clic para copiar CURP)"><span style="margin-right:3px;">✅</span>HIT</span>`;
                displayUI += `<button class="btn-check-retry" onclick="runCheck(event, ${rIdx}, ${cIdx})" title="Re-verificar contra Onboarding">↻</button>`;
              } else if (isNeg) {
                const shortText = formatShortReason(rawVal);
                displayUI = `<span class="tag-btn dead" style="padding:3px 7px;" title="Rechazo Santander: ${escapeHtml(rawVal)}"><span style="opacity:0.75; font-size:9px; margin-right:3px;">✕</span>${escapeHtml(shortText)}</span>`;
                displayUI += `<button class="btn-check-retry" onclick="runCheck(event, ${rIdx}, ${cIdx})" title="Re-verificar contra Onboarding">↻</button>`;
              } else {
                 displayUI = `<span class="tag-btn error-lbl" style="flex:1; background:rgba(251,191,36,0.12); color:#fbbf24; border:1px solid rgba(251,191,36,0.45); white-space: nowrap; overflow:hidden; text-overflow:ellipsis; padding:2px 6px; border-radius:4px; display:inline-block; font-size:10px;" title="${escapeHtml(rawVal)}">${escapeHtml(rawVal)}</span>`;
                 displayUI += `<button class="btn-check-retry" onclick="runCheck(event, ${rIdx}, ${cIdx})" title="Reintentar verificación">↻</button>`;
              }
              displayContent = `<div style="display:flex; align-items:center; width:100%; justify-content:center; gap:3px;">${displayUI}</div>`;
            }

            const stickyStyle = col.sticky ? `position: sticky; left: ${col.stickyLeft}px; z-index: 10; background: #0e1627;` : '';

            html += `
              <td class="excel-cell ${col.mono ? 'mono' : ''}" 
                id="cell-${rIdx}-${cIdx}"
                style="width: ${col.width}; min-width: ${col.width}; max-width: ${col.width}; ${stickyStyle}"
                data-row-idx="${rIdx}" 
                data-col-idx="${cIdx}" 
                data-col-key="${col.key}"
                data-record-id="${r.id}"
                data-raw-val="${escapeHtml(rawVal)}"
                title="${escapeHtml(rawVal)}"
                onclick="handleCellClick(event, ${rIdx}, ${cIdx})"
                onmousedown="handleCellRangeMouseDown(event, ${rIdx}, ${cIdx})"
                onmouseenter="handleCellRangeMouseEnter(event, ${rIdx}, ${cIdx})"
                ondblclick="startCellEdit(${rIdx}, ${cIdx})"
                oncontextmenu="handleCellContextMenu(event, ${rIdx}, ${cIdx})">
                ${displayContent}
              </td>
            `;
          });

          html += `</tr>`;
        });

        tbody.innerHTML = html;
        const tRender1 = performance.now();
        console.log(`[PERF] ${data.records.length} filas renderizadas en ${(tRender1 - tRender0).toFixed(1)} ms (Fetch total: ${(tRender1 - t0).toFixed(1)} ms)`);

        updateSelectCount();
        if (activeRowIndex >= currentRecords.length) activeRowIndex = 0;
        highlightActiveCell();
      } catch(e) {
        console.error(e);
        tbody.innerHTML = '<tr><td colspan="22" style="text-align:center; padding: 40px; color: #ef4444;">Error de conexión al cargar registros.</td></tr>';
      }
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    // ============ Selección de rango de celdas (arrastrar / Ctrl+arrastrar) ============
    // Restringida a UNA columna por selección: arrastra hacia abajo para tomar C5:C20,
    // Ctrl+arrastra un segundo tramo para agregar C25:C30 sin perder el primero.
    function handleCellRangeMouseDown(e, rowIdx, colIdx) {
      if (e.button !== 0) return; // solo click izquierdo
      const isCtrl = e.ctrlKey || e.metaKey;

      if (!isCtrl) {
        cellRangeSelection.segments = [];
      } else if (cellRangeSelection.segments.length > 0 && cellRangeSelection.segments[0].colIdx !== colIdx) {
        cellRangeSelection.segments = [];
        showToast('↺ Selección reiniciada (nueva columna)');
      }
      cellRangeSelection.drag = { colIdx, start: rowIdx, end: rowIdx, moved: false, ctrl: isCtrl };
      renderCellRangeHighlight();
    }

    function handleCellRangeMouseEnter(e, rowIdx, colIdx) {
      const d = cellRangeSelection.drag;
      if (!d) return;
      if (e.buttons !== 1) { cellRangeSelection.drag = null; return; }
      if (colIdx !== d.colIdx) return; // el arrastre solo extiende dentro de la misma columna
      if (rowIdx !== d.end) d.moved = true;
      d.end = rowIdx;
      renderCellRangeHighlight();
    }

    function finalizeCellRangeDrag() {
      const d = cellRangeSelection.drag;
      if (!d) return;
      cellRangeSelection.drag = null;

      if (d.moved || d.ctrl) {
        cellRangeSelection.segments.push({ colIdx: d.colIdx, start: Math.min(d.start, d.end), end: Math.max(d.start, d.end) });
        // Si mousedown y mouseup cayeron en celdas distintas, el navegador nunca dispara 'click'
        // y esta bandera quedaría armada contaminando el siguiente click real. Se autolimpia en el
        // próximo tick: si sí hay 'click' síncrono (mismo elemento), lo consume primero.
        suppressNextCellTextClick = true;
        setTimeout(() => { suppressNextCellTextClick = false; }, 0);
      }
      renderCellRangeHighlight();
      updateRangeSelectionUI();
    }

    function renderCellRangeHighlight() {
      document.querySelectorAll('.excel-range-selected, .excel-range-edge-top, .excel-range-edge-bottom').forEach(el => {
        el.classList.remove('excel-range-selected', 'excel-range-edge-top', 'excel-range-edge-bottom');
      });
      const segs = cellRangeSelection.segments.slice();
      if (cellRangeSelection.drag) {
        const d = cellRangeSelection.drag;
        segs.push({ colIdx: d.colIdx, start: Math.min(d.start, d.end), end: Math.max(d.start, d.end) });
      }
      segs.forEach(seg => {
        for (let r = seg.start; r <= seg.end; r++) {
          const cell = document.getElementById(`cell-${r}-${seg.colIdx}`);
          if (!cell) continue;
          cell.classList.add('excel-range-selected');
          if (r === seg.start) cell.classList.add('excel-range-edge-top');
          if (r === seg.end) cell.classList.add('excel-range-edge-bottom');
        }
      });
    }

    function getCellRangeCount() {
      return cellRangeSelection.segments.reduce((acc, s) => acc + (s.end - s.start + 1), 0);
    }

    function getCellRangeValues() {
      const values = [];
      cellRangeSelection.segments.slice().sort((a, b) => a.start - b.start).forEach(seg => {
        for (let r = seg.start; r <= seg.end; r++) {
          const cell = document.getElementById(`cell-${r}-${seg.colIdx}`);
          if (cell) values.push(cell.getAttribute('data-raw-val') || '');
        }
      });
      return values;
    }

    function copyCellRangeSelection() {
      const values = getCellRangeValues();
      if (values.length === 0) return;
      const text = values.join(String.fromCharCode(10));
      const colIdx = cellRangeSelection.segments[0].colIdx;
      const col = COLUMNS[colIdx];
      const done = () => showToast(`✓ ${values.length} valores de ${col ? col.label : 'columna'} copiados`);
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(() => { fallbackCopy(text); done(); });
      } else {
        fallbackCopy(text);
        done();
      }
    }

    function clearCellRangeSelection() {
      cellRangeSelection.segments = [];
      cellRangeSelection.drag = null;
      renderCellRangeHighlight();
      updateRangeSelectionUI();
    }

    function updateRangeSelectionUI() {
      const btn = document.getElementById('btn-copy-range');
      const clearBtn = document.getElementById('btn-clear-range');
      const countEl = document.getElementById('range-sel-count');
      if (!btn || !countEl) return;
      const count = getCellRangeCount();
      if (count > 0) {
        btn.style.display = '';
        if (clearBtn) clearBtn.style.display = '';
        countEl.innerText = count;
        const col = COLUMNS[cellRangeSelection.segments[0].colIdx];
        btn.title = `Copiar ${count} celda(s) de ${col ? col.label : ''} (Ctrl+C también funciona)`;
      } else {
        btn.style.display = 'none';
        if (clearBtn) clearBtn.style.display = 'none';
      }
    }
    // ============ fin selección de rango de celdas ============

    function handleCellClick(e, rowIdx, colIdx) {
      if (suppressNextCellTextClick) { suppressNextCellTextClick = false; return; }
      if (isEditingCell) commitCellEdit();
      activeRowIndex = rowIdx;
      activeColIndex = colIdx;
      highlightActiveCell();

      const record = currentRecords[rowIdx];
      if (!record) return;

      if (e && (e.ctrlKey || e.metaKey)) {
        const isSelected = selectedRowIds.has(record.id);
        setRowSelected(record.id, !isSelected);
        lastClickedRowIndex = rowIdx;
        updateSelectCount();
      } else if (e && e.shiftKey && lastClickedRowIndex !== -1) {
        const start = Math.min(lastClickedRowIndex, rowIdx);
        const end = Math.max(lastClickedRowIndex, rowIdx);
        for (let i = start; i <= end; i++) {
          const r = currentRecords[i];
          if (r) setRowSelected(r.id, true);
        }
        updateSelectCount();
      }
    }

    function highlightActiveCell() {
      document.querySelectorAll('.excel-cell.excel-active').forEach(c => c.classList.remove('excel-active'));
      const cell = document.getElementById(`cell-${activeRowIndex}-${activeColIndex}`);
      if (!cell) return;

      cell.classList.add('excel-active');
      cell.scrollIntoView({ block: 'nearest', inline: 'nearest' });

      const col = COLUMNS[activeColIndex];
      const rawVal = cell.getAttribute('data-raw-val') || '';

      const coordBox = document.getElementById('cell-coord');
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
      }
    }

    function setupFormulaBarListener() {
      const formulaInput = document.getElementById('formula-input');
      if (!formulaInput) return;
      formulaInput.addEventListener('keydown', (e) => {
        const col = COLUMNS[activeColIndex];
        if (!col.editable) return;

        if (e.key === 'Enter') {
          saveActiveCellValue(formulaInput.value);
          formulaInput.blur();
        } else if (e.key === 'Escape') {
          const cell = document.getElementById(`cell-${activeRowIndex}-${activeColIndex}`);
          if (cell) formulaInput.value = cell.getAttribute('data-raw-val') || '';
          formulaInput.blur();
        }
      });
    }

    function startCellEdit(rowIdx, colIdx, initialChar = null) {
      if (isEditingCell) commitCellEdit();

      activeRowIndex = rowIdx;
      activeColIndex = colIdx;
      highlightActiveCell();

      const col = COLUMNS[colIdx];
      if (!col.editable) {
        showToast('🔒 Solo el campo CURP es editable');
        return;
      }

      const cell = document.getElementById(`cell-${rowIdx}-${colIdx}`);
      if (!cell) return;

      isEditingCell = true;
      const currentVal = cell.getAttribute('data-raw-val') || '';

      const input = document.createElement('input');
      input.type = 'text';
      input.className = 'cell-editor-input';
      input.value = initialChar !== null ? initialChar.toUpperCase() : currentVal;
      cellEditorElem = input;

      cell.appendChild(input);
      input.focus();
      if (initialChar === null) input.select();

      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          commitCellEdit();
          if (activeRowIndex < currentRecords.length - 1) {
            activeRowIndex++;
            highlightActiveCell();
          }
        } else if (e.key === 'Tab') {
          e.preventDefault();
          commitCellEdit();
          if (e.shiftKey) {
            if (activeColIndex > 0) activeColIndex--;
          } else {
            if (activeColIndex < COLUMNS.length - 1) activeColIndex++;
          }
          highlightActiveCell();
        } else if (e.key === 'Escape') {
          cancelCellEdit();
        }
      });

      input.addEventListener('blur', () => {
        if (isEditingCell) commitCellEdit();
      });
    }

    async function commitCellEdit() {
      if (!isEditingCell || !cellEditorElem) return;
      const newVal = cellEditorElem.value.trim().toUpperCase();
      isEditingCell = false;
      if (cellEditorElem.parentNode) cellEditorElem.parentNode.removeChild(cellEditorElem);
      cellEditorElem = null;

      await saveActiveCellValue(newVal);
    }

    function cancelCellEdit() {
      isEditingCell = false;
      if (cellEditorElem && cellEditorElem.parentNode) {
        cellEditorElem.parentNode.removeChild(cellEditorElem);
      }
      cellEditorElem = null;
      highlightActiveCell();
    }

    async function saveActiveCellValue(newVal) {
      const col = COLUMNS[activeColIndex];
      if (!col.editable) {
        showToast('🔒 Solo el campo CURP es editable');
        return;
      }

      const cell = document.getElementById(`cell-${activeRowIndex}-${activeColIndex}`);
      if (!cell) return;

      const record = currentRecords[activeRowIndex];
      if (!record) return;

      const oldVal = cell.getAttribute('data-raw-val') || '';
      if (newVal === oldVal) return;

      cell.setAttribute('data-raw-val', newVal);
      cell.setAttribute('title', newVal);
      updateCellDisplay(cell, col.key, newVal);
      const fInput = document.getElementById('formula-input'); if (fInput) fInput.value = newVal;

      try {
        const res = await fetch(`${BASE_PATH}/api/record/${record.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ field: 'curp', value: newVal })
        });
        const data = await res.json();
        if (data.ok) {
          record.curp = newVal;
          record.curp_status = newVal ? 'existente' : 'no_calculable';
          cell.classList.add('cell-saved');
          setTimeout(() => cell.classList.remove('cell-saved'), 1200);
          showToast(`CURP guardada para ID #${record.id}`);
          fetchStats();
        } else {
          showToast(`Error al guardar: ${data.detail || 'Fallo de BD'}`);
          cell.setAttribute('data-raw-val', oldVal);
          cell.setAttribute('title', oldVal);
          updateCellDisplay(cell, col.key, oldVal);
        }
      } catch(e) {
        console.error(e);
        showToast('Error de red al persistir CURP');
        cell.setAttribute('data-raw-val', oldVal);
        cell.setAttribute('title', oldVal);
        updateCellDisplay(cell, col.key, oldVal);
      }
    }

    function handleLiveLinkClick(e, curp) {
      if (e) e.stopPropagation();
      if (curp) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(curp).then(() => {
            showToast(`CURP copiada: ${curp}`, 'success');
          }).catch(() => {
            fallbackCopy(curp);
          });
        } else {
          fallbackCopy(curp);
        }
      }
    }

    function fallbackCopy(text) {
      try {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast(`CURP copiada: ${text}`, 'success');
      } catch(e) {}
    }

    
    function formatShortReason(detail) {
      if (!detail) return "Rechazo";
      const s = String(detail).trim();
      if (s.includes("PE1002")) return "PE1002";
      if (s.toLowerCase().includes("timeout")) return "Timeout";
      if (s.includes("confirm-contact") || s.toLowerCase().includes("contacto") || s.toLowerCase().includes("preexistente")) return "Reg. previo";
      if (s.toLowerCase().includes("derivation") || s.toLowerCase().includes("likeu")) return "LikeU Pro";
      if (s.toLowerCase().includes("sucursal") || s.toLowerCase().includes("rechazo")) return "Sucursal";
      if (s === "OFF" || s === "DEAD") return "Rechazo";
      return s.length > 15 ? s.slice(0, 14) + "…" : s;
    }

    function isNegativeResult(val) {
      if (!val) return false;
      const s = String(val).toUpperCase();
      if (s === 'HIT' || s === 'LIVE' || s === 'ON') return false;
      if (s === 'DEAD' || s === 'OFF' || s === 'RECHAZO' || s === 'NO CUMPLE' ||
          s.includes('PE1002') || s.includes('PREVIO') || s.includes('CONTACTO') ||
          s.includes('LIKEU') || s.includes('SUCURSAL') || s.includes('TIMEOUT') ||
          s.includes('CONFIRM-DATA')) {
        return true;
      }
      return false;
    }

    const activeChecks = new Set();

    async function runCheck(e, rIdx, cIdx) {
      if (e) { e.stopPropagation(); e.preventDefault(); }
      const rec = currentRecords[rIdx];
      if (!rec) return;

      if (activeChecks.has(rec.id)) {
        showToast("Esta fila ya se está verificando...", "info");
        return;
      }

      // Límite en cliente: Máximo 3 checks simultáneos para operadores
      const isSuperadmin = (currentUser && currentUser.role === 'superadmin');
      if (!isSuperadmin && activeChecks.size >= 3) {
        showToast("⚠️ Máximo 3 checks simultáneos permitidos. Espera a que termine uno.", "warning");
        return;
      }

      const curp = (rec.curp || '').trim();
      const cell = document.getElementById(`cell-${rIdx}-${cIdx}`);
      if (!curp) {
        showToast("Se requiere CURP. Por favor ingresa el CURP para procesar.", "warning");
        if (cell) updateCellDisplay(cell, 'results', "SIN CURP");
        return;
      }

      activeChecks.add(rec.id);
      if (cell) {
        cell.innerHTML = `<span class="checking-pill"><span class="spin">⏳</span> VERIFICANDO...</span>`;
      }

      try {
        const res = await fetch(BASE_PATH + '/api/check_curp', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ curp: curp })
        });

        if (res.status === 401) {
          showLockScreen();
          return;
        }

        if (res.status === 429) {
          const errData = await res.json().catch(() => ({}));
          const msg = errData.detail || "Límite de concurrencia (máx. 3 checks a la vez)";
          showToast(`⚠️ ${msg}`, "warning");
          if (cell) updateCellDisplay(cell, 'results', rec.results || "");
          return;
        }

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          showToast(`Error (${res.status}): ${errData.detail || 'Fallo en servidor'}`, "error");
          if (cell) updateCellDisplay(cell, 'results', rec.results || "");
          return;
        }

        const data = await res.json();
        let tag = '';
        if (data.status === 'ON') {
           tag = 'HIT';
        } else if (data.status === 'OFF') {
           tag = data.short_reason || formatShortReason(data.detail);
        } else {
           tag = data.detail || 'ERROR';
        }
        
        try {
          await fetch(BASE_PATH + '/api/record/' + rec.id, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field: 'results', value: tag })
          });
        } catch(saveErr) {
          console.warn("Fallo persistiendo results:", saveErr);
        }

        rec.results = tag;
        if (cell) updateCellDisplay(cell, 'results', tag);
        
        if (tag === 'HIT') {
          showToast(`¡HIT detectado para CURP ${curp}!`, "success");
        }
      } catch (err) {
        showToast("Error de conexión al verificar CURP", "error");
        if (cell) updateCellDisplay(cell, 'results', rec.results || "");
      } finally {
        activeChecks.delete(rec.id);
      }
    }

    function updateCellDisplay(cell, colKey, val) {
      let displayContent = escapeHtml(val);
      if (colKey === 'curp') {
        if (val) {
          displayContent = `<span class="curp-pill">${escapeHtml(val)}</span>`;
        } else {
          displayContent = `<span class="curp-empty">+ Ingresar CURP</span>`;
        }
      } else if (colKey === 'results') {
        let displayUI = '';
        const isLive = (val === 'HIT' || val === 'LIVE' || val === 'ON');
        const isNeg = isNegativeResult(val);
        if (!val) {
           displayUI = `<button class="btn-check-curp" onclick="runCheck(event, cell.dataset.rowIdx, cell.dataset.colIdx)" title="Verificar elegibilidad en Onboarding Santander"><span class="check-icon">⚡</span> CHECK</button>`;
        } else if (isLive) {
           const rec = currentRecords[cell.dataset.rowIdx];
           const curpVal = escapeHtml(rec ? rec.curp : '');
           displayUI = `<span class="tag-btn hit" onclick="copyInlineText(event, '${curpVal}', 'CURP')" title="Elegible Santander (Clic para copiar CURP)"><span style="margin-right:3px;">✅</span>HIT</span>`;
           displayUI += `<button class="btn-check-retry" onclick="runCheck(event, cell.dataset.rowIdx, cell.dataset.colIdx)" title="Re-verificar contra Onboarding">↻</button>`;
        } else if (isNeg) {
           const shortText = formatShortReason(val);
           displayUI = `<span class="tag-btn dead" style="padding:3px 7px;" title="Rechazo Santander: ${escapeHtml(val)}"><span style="opacity:0.75; font-size:9px; margin-right:3px;">✕</span>${escapeHtml(shortText)}</span>`;
           displayUI += `<button class="btn-check-retry" onclick="runCheck(event, cell.dataset.rowIdx, cell.dataset.colIdx)" title="Re-verificar contra Onboarding">↻</button>`;
        } else {
           displayUI = `<span class="tag-btn error-lbl" style="flex:1; background:rgba(251,191,36,0.12); color:#fbbf24; border:1px solid rgba(251,191,36,0.45); white-space: nowrap; overflow:hidden; text-overflow:ellipsis; padding:2px 6px; border-radius:4px; display:inline-block; font-size:10px;" title="${escapeHtml(val)}">${escapeHtml(val)}</span>`;
           displayUI += `<button class="btn-check-retry" onclick="runCheck(event, cell.dataset.rowIdx, cell.dataset.colIdx)" title="Reintentar verificación">↻</button>`;
        }
        displayContent = `<div style="display:flex; align-items:center; width:100%; justify-content:center; gap:3px;">${displayUI}</div>`;
      }
      cell.innerHTML = displayContent;
    }

    
    function copySelectedToClipboard() {
      if (cellRangeSelection.segments.length > 0) {
        copyCellRangeSelection();
        return;
      }
      if (selectedRowIds.size === 0) {
        const cell = document.getElementById(`cell-${activeRowIndex}-${activeColIndex}`);
        if (cell) {
          const val = cell.getAttribute('data-raw-val') || '';
          navigator.clipboard.writeText(val).then(() => showToast(`Copiado: "${val}"`));
        }
        return;
      }

      const selectedRecords = currentRecords.filter(r => selectedRowIds.has(r.id));
      const lines = [];
      selectedRecords.forEach(rec => {
        const rowVals = COLUMNS.map(col => rec[col.key] !== null && rec[col.key] !== undefined ? String(rec[col.key]) : '');
        lines.push(rowVals.join(String.fromCharCode(9)));
      });
      const tsvData = lines.join(String.fromCharCode(10));
      navigator.clipboard.writeText(tsvData).then(() => {
        showToast(`✓ ${selectedRecords.length} filas copiadas como TSV`);
      });
    }

    function setupKeyboardListeners() {
      window.addEventListener('keydown', (e) => {
        if (['login-password', 'search-input', 'global-search', 'popover-filter-val', 'bulk-curp-text', 'hits-search-input'].includes(e.target.id) || (e.target && e.target.classList && e.target.classList.contains('hit-notes-input'))) {
          return;
        }

        // Navegación con teclado en la Bóveda de HITS
        if (currentViewMode === 'hits') {
          const hitsGrid = document.getElementById('hits-grid-container');
          if (hitsGrid) {
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              hitsGrid.scrollTop += 40;
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              hitsGrid.scrollTop -= 40;
            } else if (e.key === 'PageDown') {
              e.preventDefault();
              hitsGrid.scrollTop += hitsGrid.clientHeight * 0.8;
            } else if (e.key === 'PageUp') {
              e.preventDefault();
              hitsGrid.scrollTop -= hitsGrid.clientHeight * 0.8;
            } else if (e.key === 'Home') {
              e.preventDefault();
              hitsGrid.scrollTop = 0;
            } else if (e.key === 'End') {
              e.preventDefault();
              hitsGrid.scrollTop = hitsGrid.scrollHeight;
            }
          }
          return;
        }

        if (currentViewMode !== 'general') return;

        if (isEditingCell) return;

        if (e.key === 'ArrowDown') {
          e.preventDefault();
          if (activeRowIndex < currentRecords.length - 1) activeRowIndex++;
          highlightActiveCell();
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          if (activeRowIndex > 0) activeRowIndex--;
          highlightActiveCell();
        } else if (e.key === 'ArrowRight') {
          e.preventDefault();
          if (activeColIndex < COLUMNS.length - 1) activeColIndex++;
          highlightActiveCell();
        } else if (e.key === 'ArrowLeft') {
          e.preventDefault();
          if (activeColIndex > 0) activeColIndex--;
          highlightActiveCell();
        } else if (e.key === 'Tab') {
          e.preventDefault();
          if (e.shiftKey) {
            if (activeColIndex > 0) activeColIndex--;
          } else {
            if (activeColIndex < COLUMNS.length - 1) activeColIndex++;
          }
          highlightActiveCell();
        } else if (e.key === 'Enter' || e.key === 'F2') {
          e.preventDefault();
          const col = COLUMNS[activeColIndex];
          if (col.editable) {
            startCellEdit(activeRowIndex, activeColIndex);
          } else {
            showToast('🔒 Solo el campo CURP es editable');
          }
        } else if (e.key === 'Delete' || e.key === 'Backspace') {
          const col = COLUMNS[activeColIndex];
          if (col.editable) {
            e.preventDefault();
            saveActiveCellValue('');
          }
        } else if (e.key === 'Escape' && cellRangeSelection.segments.length > 0) {
          e.preventDefault();
          clearCellRangeSelection();
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
          e.preventDefault();
          copySelectedToClipboard();
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'x') {
          e.preventDefault();
          copySelectedToClipboard();
          const col = COLUMNS[activeColIndex];
          if (col.editable) {
            saveActiveCellValue('');
          }
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') {
          const col = COLUMNS[activeColIndex];
          if (col.editable) {
            e.preventDefault();
            navigator.clipboard.readText().then(text => {
              if (text) saveActiveCellValue(text.trim().toUpperCase());
            });
          } else {
            showToast('🔒 Solo el campo CURP es editable');
          }
        } else if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
          const col = COLUMNS[activeColIndex];
          if (col.editable) {
            startCellEdit(activeRowIndex, activeColIndex, e.key);
          }
        }
      });
    }

    let currentFilterColKey = null;

    function openFilterPopover(e, colKey) {
      e.stopPropagation();
      currentFilterColKey = colKey;
      const col = COLUMNS.find(c => c.key === colKey);
      if (!col) return;

      const popover = document.getElementById('filter-popover');
      document.getElementById('popover-title').innerText = `Filtro: ${col.label} (${col.letter})`;

      const existing = columnFilters[colKey];
      const opSelect = document.getElementById('popover-operator');
      const valInput = document.getElementById('popover-filter-val');

      if (existing) {
        opSelect.value = existing.op || 'contains';
        valInput.value = existing.val || '';
      } else {
        opSelect.value = 'contains';
        valInput.value = '';
      }
      onOperatorChange();

      const btnRect = e.target.getBoundingClientRect();
      popover.style.top = `${btnRect.bottom + 6}px`;
      let leftPos = btnRect.left - 120;
      if (leftPos + 260 > window.innerWidth) leftPos = window.innerWidth - 270;
      if (leftPos < 10) leftPos = 10;
      popover.style.left = `${leftPos}px`;

      popover.classList.add('show');
      setTimeout(() => valInput.focus(), 50);
    }

    function closeFilterPopover() {
      document.getElementById('filter-popover').classList.remove('show');
    }

    function onOperatorChange() {
      const op = document.getElementById('popover-operator').value;
      const valInput = document.getElementById('popover-filter-val');
      if (op === 'empty' || op === 'not_empty') {
        valInput.style.display = 'none';
      } else {
        valInput.style.display = 'block';
      }
    }

    function applyColumnFilter() {
      if (!currentFilterColKey) return;
      const op = document.getElementById('popover-operator').value;
      const val = document.getElementById('popover-filter-val').value.trim();

      if (op !== 'empty' && op !== 'not_empty' && !val) {
        delete columnFilters[currentFilterColKey];
      } else {
        columnFilters[currentFilterColKey] = { op, val };
      }

      closeFilterPopover();
      currentPage = 1;
      buildHeaderRow();
      loadRecords();
    }

    function clearCurrentColumnFilter() {
      if (currentFilterColKey && columnFilters[currentFilterColKey]) {
        delete columnFilters[currentFilterColKey];
        closeFilterPopover();
        currentPage = 1;
        buildHeaderRow();
        loadRecords();
      }
    }

    function clearAllFilters() {
      columnFilters = {};
      currentGlobalSearch = '';
      document.getElementById('global-search').value = '';
      currentPresetFilter = 'all';
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelector('.tab-btn').classList.add('active');
      currentPage = 1;
      buildHeaderRow();
      loadRecords();
    }

    function applySort(dir) {
      if (!currentFilterColKey) return;
      currentSortBy = currentFilterColKey;
      currentSortDir = dir;
      closeFilterPopover();
      currentPage = 1;
      buildHeaderRow();
      loadRecords();
    }

    function updateActiveFilterChips() {
      const bar = document.getElementById('active-filters-bar');
      const container = document.getElementById('active-filters-chips');
      const clearBtn = document.getElementById('btn-clear-all-filters');
      const keys = Object.keys(columnFilters);

      if (keys.length === 0 && !currentGlobalSearch && currentPresetFilter === 'all') {
        bar.classList.remove('show');
        clearBtn.style.display = 'none';
        return;
      }

      bar.classList.add('show');
      clearBtn.style.display = 'inline-flex';

      let html = '';
      if (currentPresetFilter !== 'all') {
        html += `<span class="filter-chip">Preset: ${currentPresetFilter}</span>`;
      }
      if (currentGlobalSearch) {
        html += `<span class="filter-chip">Búsqueda: "${escapeHtml(currentGlobalSearch)}"</span>`;
      }
      keys.forEach(k => {
        const col = COLUMNS.find(c => c.key === k);
        const f = columnFilters[k];
        let desc = `${col ? col.label : k}: ${f.op}`;
        if (f.val) desc += ` "${escapeHtml(f.val)}"`;
        html += `
          <span class="filter-chip">
            ${desc}
            <span class="filter-chip-remove" onclick="removeFilter('${k}')">✕</span>
          </span>
        `;
      });
      container.innerHTML = html;
    }

    function removeFilter(colKey) {
      delete columnFilters[colKey];
      currentPage = 1;
      buildHeaderRow();
      loadRecords();
    }

    let ctxRecordId = null;
    let ctxRowIdx = null;
    let ctxColIdx = null;

    function handleCellContextMenu(e, rowIdx, colIdx) {
      e.preventDefault();
      ctxRowIdx = rowIdx;
      ctxColIdx = colIdx;
      activeRowIndex = rowIdx;
      activeColIndex = colIdx;
      highlightActiveCell();

      const record = currentRecords[rowIdx];
      if (!record) return;
      ctxRecordId = record.id;

      const col = COLUMNS[colIdx];
      const pasteItem = document.getElementById('ctx-paste-item');
      const clearItem = document.getElementById('ctx-clear-item');
      if (col.editable) {
        pasteItem.style.display = 'flex';
        clearItem.style.display = 'flex';
      } else {
        pasteItem.style.display = 'none';
        clearItem.style.display = 'none';
      }

      const menu = document.getElementById('context-menu');
      const rangeItem = document.getElementById('ctx-range-item');
      const rangeBadge = document.getElementById('ctx-range-badge');
      if (typeof cellRangeSelection !== 'undefined' && cellRangeSelection.segments.length > 0 && rangeItem && rangeBadge) {
        rangeItem.style.display = 'flex';
        rangeBadge.innerText = `${getCellRangeCount()} celdas`;
      } else if (rangeItem) {
        rangeItem.style.display = 'none';
      }

      menu.classList.add('show');
      const rect = menu.getBoundingClientRect();
      let top = e.clientY;
      let left = e.clientX;
      if (left + rect.width > window.innerWidth) left = window.innerWidth - rect.width - 10;
      if (top + rect.height > window.innerHeight) top = window.innerHeight - rect.height - 10;
      menu.style.top = `${Math.max(10, top)}px`;
      menu.style.left = `${Math.max(10, left)}px`;
    }

    window.addEventListener('click', () => {
      document.getElementById('context-menu').classList.remove('show');
      const popover = document.getElementById('filter-popover');
      if (popover && !popover.contains(event.target) && !event.target.classList.contains('filter-btn')) {
        popover.classList.remove('show');
      }
    });

    function ctxCopyCell() {
      const cell = document.getElementById(`cell-${ctxRowIdx}-${ctxColIdx}`);
      if (cell) {
        const val = cell.getAttribute('data-raw-val') || '';
        navigator.clipboard.writeText(val).then(() => showToast(`Copiado: "${val}"`));
      }
    }

    function ctxCopyRfc() {
      const record = currentRecords[ctxRowIdx];
      if (record && record.u6rfc) {
        navigator.clipboard.writeText(record.u6rfc).then(() => showToast(`RFC copiado: ${record.u6rfc}`));
      }
    }

    function ctxCopyRow() {
      const record = currentRecords[ctxRowIdx];
      if (!record) return;
      const rowTsv = COLUMNS.map(c => record[c.key] || '').join(String.fromCharCode(9));
      navigator.clipboard.writeText(rowTsv).then(() => showToast(`Fila #${record.id} copiada como TSV`));
    }

    function ctxPasteCell() {
      const col = COLUMNS[ctxColIdx];
      if (!col.editable) return;
      navigator.clipboard.readText().then(text => {
        if (text) saveActiveCellValue(text.trim().toUpperCase());
      });
    }

    function ctxClearCell() {
      const col = COLUMNS[ctxColIdx];
      if (!col.editable) return;
      saveActiveCellValue('');
    }

    async function ctxMarkResult(tag) {
      if (!ctxRecordId) return;
      try {
        const res = await fetch(`${BASE_PATH}/api/record/${ctxRecordId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ field: 'results', value: tag })
        });
        const data = await res.json();
        if (data.ok) {
          const record = currentRecords.find(r => r.id === ctxRecordId);
          if (record) record.results = tag;
          const cell = document.querySelector(`td[data-record-id="${ctxRecordId}"][data-col-key="results"]`);
          if (cell) updateCellDisplay(cell, 'results', tag);
          showToast(`ID #${ctxRecordId} marcado como ${tag}`);
          fetchStats();
        }
      } catch(e) { console.error(e); }
    }

    const PRESET_LABELS = {
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
    }

    
    function toggleSearchClearBtn() {
      const val = document.getElementById('global-search').value;
      const btn = document.getElementById('btn-clear-search');
      if (btn) btn.style.display = val ? 'block' : 'none';
    }

    function clearGlobalSearch() {
      const input = document.getElementById('global-search');
      if (input) {
        input.value = '';
        toggleSearchClearBtn();
        applyGlobalSearch();
      }
    }

    window.addEventListener('keydown', (e) => {
      const isInputActive = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);
      if (((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') || (e.key === '/' && !isInputActive)) {
        e.preventDefault();
        const searchInput = document.getElementById('global-search');
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    });

    function applyGlobalSearch() {
      currentGlobalSearch = document.getElementById('global-search').value.trim();
      currentPage = 1;
      loadRecords();
    }

    function changeLimit() {
      currentLimit = parseInt(document.getElementById('limit-select').value);
      currentPage = 1;
      loadRecords();
    }

    function prevPage() {
      if (currentPage > 1) { currentPage--; loadRecords(); }
    }
    function nextPage() {
      currentPage++; loadRecords();
    }

        let isDraggingSelection = false;
    let dragStartIndex = -1;
    let dragTargetState = true;
    let lastClickedRowIndex = -1;

    function setRowSelected(id, selected) {
      const rowElem = document.getElementById(`row-${id}`);
      const cb = document.querySelector(`#row-${id} .row-checkbox`);
      if (selected) {
        selectedRowIds.add(id);
        if (rowElem) rowElem.classList.add('row-selected');
        if (cb) cb.checked = true;
      } else {
        selectedRowIds.delete(id);
        if (rowElem) rowElem.classList.remove('row-selected');
        if (cb) cb.checked = false;
      }
    }

    function handleRowSelectMouseDown(e, rIdx) {
      if (e.button !== 0) return; // Solo clic izquierdo
      e.preventDefault();

      isDraggingSelection = true;
      dragStartIndex = rIdx;

      const record = currentRecords[rIdx];
      if (!record) return;

      const isCtrl = e.ctrlKey || e.metaKey;
      const isShift = e.shiftKey;

      if (isShift && lastClickedRowIndex !== -1) {
        const start = Math.min(lastClickedRowIndex, rIdx);
        const end = Math.max(lastClickedRowIndex, rIdx);
        for (let i = start; i <= end; i++) {
          const rec = currentRecords[i];
          if (rec) setRowSelected(rec.id, true);
        }
        isDraggingSelection = false;
        updateSelectCount();
        return;
      }

      lastClickedRowIndex = rIdx;

      const isCurrentlySelected = selectedRowIds.has(record.id);
      dragTargetState = !isCurrentlySelected;
      setRowSelected(record.id, dragTargetState);
      updateSelectCount();
    }

    function handleRowSelectMouseEnter(e, rIdx) {
      if (!isDraggingSelection || dragStartIndex === -1) return;

      const start = Math.min(dragStartIndex, rIdx);
      const end = Math.max(dragStartIndex, rIdx);

      for (let i = start; i <= end; i++) {
        const rec = currentRecords[i];
        if (rec) {
          setRowSelected(rec.id, dragTargetState);
        }
      }
      updateSelectCount();
    }

    function toggleRowSelect(id, cb) {
      setRowSelected(id, cb.checked);
      updateSelectCount();
    }

    function toggleSelectAll() {
      const checkAll = document.getElementById('select-all').checked;
      currentRecords.forEach(r => {
        setRowSelected(r.id, checkAll);
      });
      updateSelectCount();
    }

    function selectFullRow(rowIdx) {
      const record = currentRecords[rowIdx];
      if (!record) return;
      const isSelected = selectedRowIds.has(record.id);
      setRowSelected(record.id, !isSelected);
      updateSelectCount();
    }

    function clearSelection() {
      selectedRowIds.clear();
      document.querySelectorAll('.row-selected').forEach(el => el.classList.remove('row-selected'));
      document.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = false);
      const selectAllCb = document.getElementById('select-all');
      if (selectAllCb) selectAllCb.checked = false;
      updateSelectCount();
      showToast('Selección desmarcada');
    }

    function updateSelectCount() {
      const totalSel = selectedRowIds.size;
      const selCountEl = document.getElementById('sel-count');
      if (selCountEl) selCountEl.innerText = totalSel;

      let curpCount = 0;
      currentRecords.forEach(r => {
        if (selectedRowIds.has(r.id) && r.curp && r.curp.trim()) {
          curpCount++;
        }
      });
      const selCurpEl = document.getElementById('sel-curp-count');
      if (selCurpEl) selCurpEl.innerText = curpCount;

      const clearBtn = document.getElementById('btn-clear-selection');
      if (clearBtn) {
        clearBtn.style.display = totalSel > 0 ? 'inline-flex' : 'none';
      }
    }

    function copySelectedRfcs() {
      if (selectedRowIds.size === 0) {
        showToast('Selecciona al menos una fila con la casilla o arrastrando');
        return;
      }
      const rfcs = [];
      currentRecords.forEach(r => {
        if (selectedRowIds.has(r.id) && r.u6rfc && r.u6rfc.trim()) {
          rfcs.push(r.u6rfc.trim());
        }
      });
      if (rfcs.length === 0) {
        showToast('No hay RFCs en las filas seleccionadas');
        return;
      }
      navigator.clipboard.writeText(rfcs.join(String.fromCharCode(10))).then(() => {
        showToast(`¡${rfcs.length} RFCs copiados al portapapeles!`);
      });
    }

    function copySelectedCurps() {
      if (selectedRowIds.size === 0) {
        showToast('Selecciona al menos una fila con la casilla o arrastrando');
        return;
      }
      const curps = [];
      currentRecords.forEach(r => {
        if (selectedRowIds.has(r.id) && r.curp && r.curp.trim()) {
          curps.push(r.curp.trim());
        }
      });
      if (curps.length === 0) {
        showToast('No hay CURPs en las filas seleccionadas');
        return;
      }
      navigator.clipboard.writeText(curps.join(String.fromCharCode(10))).then(() => {
        showToast(`¡${curps.length} CURPs copiadas al portapapeles!`);
      });
    }

    function copyPageRfcs() {
      const rfcs = currentRecords.map(r => r.u6rfc ? r.u6rfc.trim() : '').filter(Boolean);
      if (rfcs.length === 0) {
        showToast('No hay registros en esta página');
        return;
      }
      navigator.clipboard.writeText(rfcs.join(String.fromCharCode(10))).then(() => {
        showToast(`¡${rfcs.length} RFCs de la página copiados!`);
      });
    }

    function copyPageCurps() {
      const curps = currentRecords.map(r => r.curp ? r.curp.trim() : '').filter(Boolean);
      if (curps.length === 0) {
        showToast('No hay CURPs en esta página');
        return;
      }
      navigator.clipboard.writeText(curps.join(String.fromCharCode(10))).then(() => {
        showToast(`¡${curps.length} CURPs de la página copiadas!`);
      });
    }

function exportCsv() {
      const colFiltersJson = Object.keys(columnFilters).length > 0 ? JSON.stringify(columnFilters) : '';
      const params = new URLSearchParams({
        filter: currentPresetFilter,
        search: currentGlobalSearch,
        sort_by: currentSortBy,
        sort_dir: currentSortDir,
        limit: 5000
      });
      if (colFiltersJson) params.append('col_filters', colFiltersJson);
      window.location.href = `${BASE_PATH}/api/export_csv?${params.toString()}`;
    }

    // --- Control del Purger (pausa/reanuda manual) ---
    let purgerPaused = false;

    async function togglePurger() {
      const endpoint = purgerPaused ? '/api/purger/resume' : '/api/purger/pause';
      try {
        const res = await fetch(`${BASE_PATH}${endpoint}`, { method: 'POST' });
        const data = await res.json();
        purgerPaused = data.paused;
        updatePurgerUI();
        showToast(purgerPaused ? 'Purger pausado' : 'Purger reanudado');
      } catch (e) {
        showToast('Error: ' + e.message);
      }
    }

    function updatePurgerUI() {
      const btn = document.getElementById('btn-purger-toggle');
      const badge = document.getElementById('purger-state-badge');
      if (purgerPaused) {
        btn.textContent = '▶️ Reanudar Purger';
        btn.classList.add('btn-success');
        badge.textContent = 'PAUSADO';
        badge.style.background = '#dc2626';
        badge.style.color = '#fff';
      } else {
        btn.textContent = '⏸️ Pausar Purger';
        btn.classList.remove('btn-success');
        badge.textContent = 'ACTIVO';
        badge.style.background = '#16a34a';
        badge.style.color = '#fff';
      }
    }

    async function refreshPurgerStatus() {
      try {
        const res = await fetch(`${BASE_PATH}/api/purger/status`);
        const data = await res.json();
        const badge = document.getElementById('purger-state-badge');
        const state = data.state || 'STOPPED';
        if (state === 'PAUSED_MANUAL') {
          purgerPaused = true;
          updatePurgerUI();
        } else if (state === 'PAUSED_HITS_POOL') {
          badge.textContent = 'PAUSA POOL';
          badge.style.background = '#f59e0b';
          badge.style.color = '#000';
        } else if (state === 'BURST') {
          badge.textContent = 'BURST';
          badge.style.background = '#16a34a';
          badge.style.color = '#fff';
        } else if (state === 'COOLDOWN') {
          badge.textContent = 'COOLDOWN';
          badge.style.background = '#3b82f6';
          badge.style.color = '#fff';
        } else if (state === 'COMPLETED') {
          badge.textContent = 'COMPLETADO';
          badge.style.background = '#6b7280';
          badge.style.color = '#fff';
        } else if (state === 'STOPPED') {
          badge.textContent = 'DETENIDO';
          badge.style.background = '#374151';
          badge.style.color = '#9ca3af';
        }
      } catch (e) { /* silencio */ }
    }

    setInterval(refreshPurgerStatus, 10000);
    refreshPurgerStatus();

    function openBulkCurpModal() {
      document.getElementById('bulk-curp-modal').classList.add('show');
    }
    function closeBulkCurpModal() {
      document.getElementById('bulk-curp-modal').classList.remove('show');
    }

    async function submitBulkCurp() {
      const text = document.getElementById('bulk-curp-text').value.trim();
      if (!text) {
        showToast('Ingresa texto con CURPs');
        return;
      }
      try {
        const res = await fetch(`${BASE_PATH}/api/bulk_curp`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        const data = await res.json();
        if (data.ok) {
          showToast(`¡${data.updated_count} CURPs emparejados y guardados!`);
          closeBulkCurpModal();
          document.getElementById('bulk-curp-text').value = '';
          fetchStats();
          loadRecords();
        } else {
          showToast('Error procesando CURPs');
        }
      } catch(e) {
        console.error(e);
        showToast('Error de conexión');
      }
    }
    window.addEventListener('mouseup', () => {
      if (isDraggingSelection) {
        isDraggingSelection = false;
        dragStartIndex = -1;
        updateSelectCount();
      }
    });
    window.addEventListener('mouseup', finalizeCellRangeDrag);

    const tableBodyElem = document.getElementById('table-body');
    if (tableBodyElem) {
      tableBodyElem.addEventListener('mouseover', (e) => {
        if (!isDraggingSelection || dragStartIndex === -1) return;
        const tr = e.target.closest('tr[data-row-idx]');
        if (!tr) return;
        const rIdx = parseInt(tr.getAttribute('data-row-idx'), 10);
        if (!isNaN(rIdx)) {
          handleRowSelectMouseEnter(e, rIdx);
        }
      });
      tableBodyElem.addEventListener('dragstart', (e) => e.preventDefault());
    }

    // =========================================================================
    // LÓGICA DE CONTROL BÓVEDA DE HITS VIP
    // =========================================================================
    let currentViewMode = 'general';
    let hitsPage = 1;
    let hitsLimit = 100;
    let hitsStatusFilter = 'all';
    let hitsSearch = '';
    let hitsSortBy = 'checked_at';
    let hitsSortDir = 'desc';
    let currentHits = [];

    function switchViewMode(mode) {
      currentViewMode = mode;
      const genBtn = document.getElementById('nav-btn-general');
      const hitsBtn = document.getElementById('nav-btn-hits');
      const genWrap = document.getElementById('general-view-container');
      const hitsWrap = document.getElementById('hits-view-container');
      const hitsActions = document.getElementById('hits-quick-actions');

      if (mode === 'hits') {
        genBtn.classList.remove('active');
        hitsBtn.classList.add('active');
        genWrap.style.display = 'none';
        hitsWrap.style.display = 'flex';
        hitsActions.style.display = 'flex';
        fetchHits();
      } else {
        hitsBtn.classList.remove('active');
        genBtn.classList.add('active');
        hitsWrap.style.display = 'none';
        genWrap.style.display = 'flex';
        hitsActions.style.display = 'none';
        loadRecords();
      }
    }

    function setHitsStatusFilter(st) {
      hitsStatusFilter = st;
      hitsPage = 1;
      ['all', 'active', 'success', 'off'].forEach(k => {
        const btn = document.getElementById(`hits-tab-${k}`);
        if (btn) btn.classList.remove('active');
      });
      const activeKey = st === 'all' ? 'all' : (st === 'ACTIVE' ? 'active' : (st === 'SUCCESS' ? 'success' : 'off'));
      const activeBtn = document.getElementById(`hits-tab-${activeKey}`);
      if (activeBtn) activeBtn.classList.add('active');
      fetchHits();
    }

    function applyHitsSearch() {
      const input = document.getElementById('hits-search-input');
      hitsSearch = input ? input.value.trim() : '';
      hitsPage = 1;
      fetchHits();
    }

    function changeHitsSort() {
      const sel = document.getElementById('hits-sort-select');
      if (sel) {
        const [col, dir] = sel.value.split(':');
        hitsSortBy = col || 'checked_at';
        hitsSortDir = dir || 'desc';
        hitsPage = 1;
        fetchHits();
      }
    }

    function changeHitsLimit() {
      const sel = document.getElementById('hits-limit-select');
      if (sel) {
        hitsLimit = parseInt(sel.value, 10) || 100;
        hitsPage = 1;
        fetchHits();
      }
    }

    function prevHitsPage() {
      if (hitsPage > 1) {
        hitsPage--;
        fetchHits();
      }
    }

    function nextHitsPage() {
      hitsPage++;
      fetchHits();
    }

    function toggleHitsSort(colKey) {
      if (hitsSortBy === colKey) {
        hitsSortDir = hitsSortDir === 'asc' ? 'desc' : 'asc';
      } else {
        hitsSortBy = colKey;
        hitsSortDir = (colKey === 'u6licrea' || colKey === 'checked_at') ? 'desc' : 'asc';
      }
      hitsPage = 1;
      updateHitsSortIndicators();
      const sel = document.getElementById('hits-sort-select');
      if (sel) {
        const val = `${hitsSortBy}:${hitsSortDir}`;
        const matching = Array.from(sel.options).find(o => o.value === val);
        if (matching) sel.value = val;
      }
      fetchHits();
    }

    function updateHitsSortIndicators() {
      const keys = ['work_status', 'u6acct', 'curp', 'dmname', 'u6licrea', 'estado', 'ciudad', 'codigo_postal', 'operador', 'checked_at'];
      keys.forEach(k => {
        const el = document.getElementById(`th-hits-sort-${k}`);
        if (el) {
          if (hitsSortBy === k) {
            el.innerText = hitsSortDir === 'asc' ? ' ▲' : ' ▼';
          } else {
            el.innerText = '';
          }
        }
      });
    }

    async function fetchHits() {
      const tbody = document.getElementById('hits-table-body');
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="13" style="text-align:center; padding: 30px; color: var(--text-muted);"><span class="spin">⏳</span> Cargando Bóveda de HITS...</td></tr>';

      const params = new URLSearchParams({
        page: hitsPage,
        limit: hitsLimit,
        sort_by: hitsSortBy,
        sort_dir: hitsSortDir
      });
      if (hitsStatusFilter && hitsStatusFilter !== 'all') params.append('work_status', hitsStatusFilter);
      if (hitsSearch) params.append('search', hitsSearch);

      try {
        const res = await fetch(`${BASE_PATH}/api/hits?${params.toString()}`);
        if (res.status === 401) { showLockScreen(); return; }
        const data = await res.json();
        currentHits = data.hits || [];

        // Actualizar contadores
        const stats = data.stats || {};
        if (document.getElementById('hits-count-all')) document.getElementById('hits-count-all').innerText = (stats.total || 0).toLocaleString();
        if (document.getElementById('hits-count-active')) document.getElementById('hits-count-active').innerText = (stats.active || 0).toLocaleString();
        if (document.getElementById('hits-count-success')) document.getElementById('hits-count-success').innerText = (stats.success || 0).toLocaleString();
        if (document.getElementById('hits-count-off')) document.getElementById('hits-count-off').innerText = (stats.off || 0).toLocaleString();
        if (document.getElementById('nav-hits-badge')) document.getElementById('nav-hits-badge').innerText = (stats.total || 0).toLocaleString();
        if (document.getElementById('stat-hits')) document.getElementById('stat-hits').innerText = (stats.total || 0).toLocaleString();

        document.getElementById('hits-page-num').innerText = `${data.page} / ${data.total_pages}`;
        document.getElementById('hits-page-info').innerText = `Mostrando ${currentHits.length} de ${data.total.toLocaleString()} hits`;
        document.getElementById('btn-hits-prev').disabled = data.page <= 1;
        document.getElementById('btn-hits-next').disabled = data.page >= data.total_pages;

        if (currentHits.length === 0) {
          tbody.innerHTML = '<tr><td colspan="13" style="text-align:center; padding: 40px; color: var(--text-muted);">No hay registros en la Bóveda de HITS con los filtros actuales.</td></tr>';
          updateHitsSortIndicators();
          return;
        }

        let html = '';
        currentHits.forEach((h, idx) => {
          const rowNum = (hitsPage - 1) * hitsLimit + idx + 1;
          const curpEsc = escapeHtml(h.curp || '');
          const cardEsc = escapeHtml(h.u6acct || '');
          const cpEsc = escapeHtml(h.codigo_postal || '');
          const nameEsc = escapeHtml(h.dmname || '');
          const estadoEsc = escapeHtml(h.estado || '');
          const ciudadEsc = escapeHtml(h.ciudad || '');
          const limNum = parseInt(h.u6licrea, 10);
          const limFormatted = !isNaN(limNum) ? '$' + limNum.toLocaleString('es-MX') : '$' + (h.u6licrea || '0');
          const curpEncoded = encodeURIComponent(h.curp || '');
          const santanderLink = `https://onboarding.santander.com.mx/cuenta-digital-lite/product-page?canal=digital&curp=${curpEncoded}`;

          html += `
            <tr id="hit-row-${h.id}">
              <td class="row-num-cell" style="text-align: center;">${rowNum}</td>
              <td style="padding: 4px 6px;">
                <select class="hit-status-select status-${h.work_status || 'ACTIVE'}" onchange="updateHitStatus(${h.id}, this.value, this)">
                  <option value="ACTIVE" ${h.work_status === 'ACTIVE' ? 'selected' : ''}>🟢 ACTIVE</option>
                  <option value="SUCCESS" ${h.work_status === 'SUCCESS' ? 'selected' : ''}>✅ SUCCESS</option>
                  <option value="OFF" ${h.work_status === 'OFF' ? 'selected' : ''}>⚪ OFF</option>
                </select>
              </td>
              <td style="font-family: var(--font-mono); font-weight: 600; color: #60a5fa;">
                ${cardEsc ? `<span class="copyable-text" onclick="copyInlineText(event, '${cardEsc}', 'Tarjeta')" title="Copiar Tarjeta">💳 ${cardEsc}</span>` : '<span style="color:var(--text-dim);">-</span>'}
              </td>
              <td style="font-family: var(--font-mono);">
                <span class="copyable-text curp-text" onclick="copyInlineText(event, '${curpEsc}', 'CURP')" title="Copiar CURP">${curpEsc}</span>
                <a href="${santanderLink}" target="_blank" rel="noopener noreferrer" style="color:var(--text-dim); font-size:10px; margin-left:5px; text-decoration:none;" title="Abrir en pestaña web estándar (respaldo)">↗</a>
              </td>
              <td style="font-weight: 600; color: #fff;">${escapeHtml(h.dmname || 'Sin nombre')}</td>
              <td style="text-align: right; font-family: var(--font-mono); font-weight: 700; color: #34d399;">${limFormatted}</td>
              <td>${escapeHtml(h.estado || '')}</td>
              <td>${escapeHtml(h.ciudad || '')}</td>
              <td style="font-family: var(--font-mono); font-weight: 700; font-size: 11px; text-align: center; color: #a5b4fc;">
                ${cpEsc ? `<span class="copyable-text" onclick="copyInlineText(event, '${cpEsc}', 'Código Postal')" title="Copiar CP">${cpEsc}</span>` : '<span style="color:var(--text-dim);">-</span>'}
              </td>
              <td style="font-size: 11px; color: var(--text-muted);" title="${escapeHtml(h.direccion || '')}">${escapeHtml(h.direccion || '')}</td>
              <td style="font-size: 11px; color: #fbbf24;" id="hit-op-${h.id}">${escapeHtml(h.operador || '-')}</td>
              <td>
                <input type="text" class="hit-notes-input" value="${escapeHtml(h.notas || '')}"
                       placeholder="+ Nota..."
                       onchange="updateHitNotes(${h.id}, this.value)"
                       title="Presiona Enter o haz clic fuera para guardar">
              </td>
              <td style="font-size: 10.5px; font-family: var(--font-mono); color: var(--text-dim);">${escapeHtml(h.checked_at || '')}</td>
            </tr>
          `;
        });
        tbody.innerHTML = html;
        updateHitsSortIndicators();
      } catch(e) {
        console.error(e);
        tbody.innerHTML = '<tr><td colspan="13" style="text-align:center; padding: 30px; color: #ef4444;">Error cargando registros de hits.</td></tr>';
      }
    }

    async function updateHitStatus(hitId, newStatus, selectElem) {
      if (newStatus === 'OFF') {
        const ok = confirm('¿Marcar como OFF? El registro se eliminará de la bóveda y volverá a la base.');
        if (!ok) {
          if (selectElem) {
            const cur = currentHits.find(h => h.id === hitId);
            selectElem.value = (cur && cur.work_status) || 'ACTIVE';
          }
          return;
        }
      }
      if (selectElem) {
        selectElem.className = `hit-status-select status-${newStatus}`;
      }
      try {
        const res = await fetch(`${BASE_PATH}/api/hits/${hitId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ work_status: newStatus })
        });
        if (res.ok) {
          showToast(newStatus === 'OFF' ? `Hit #${hitId} descartado (vuelve a la base)` : `Estatus actualizado a ${newStatus}`);
          await fetchHits();
          fetchStats();
        } else {
          showToast('Error al actualizar estatus');
          fetchHits();
        }
      } catch(e) {
        showToast('Error de conexión');
        fetchHits();
      }
    }

    async function claimHit(hitId) {
      const res = await fetch(`${BASE_PATH}/api/hits/${hitId}/claim`, { method: 'POST' });
      if (!res.ok) throw new Error(`claim HTTP ${res.status}`);
      return await res.json();
    }

    // Funciones de compatibilidad por si se invocan desde atajos o consola
    async function updateHitNotes(hitId, notes) {
      try {
        const res = await fetch(`${BASE_PATH}/api/hits/${hitId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ notas: notes })
        });
        if (res.ok) {
          showToast('Nota guardada');
        }
      } catch(e) {
        showToast('Error al guardar nota');
      }
    }

    function copyHitsCurps() {
      if (!currentHits || currentHits.length === 0) {
        showToast('No hay hits en la vista actual');
        return;
      }
      const curps = currentHits.map(h => (h.curp || '').trim()).filter(Boolean);
      if (curps.length === 0) {
        showToast('No hay CURPs disponibles');
        return;
      }
      const text = curps.join('\\n');
      navigator.clipboard.writeText(text).then(() => {
        showToast(`✓ ${curps.length} CURPs de hits copiadas al portapapeles`);
      }).catch(() => fallbackCopy(text));
    }

    function exportHitsCsv() {
      const params = new URLSearchParams();
      if (hitsStatusFilter && hitsStatusFilter !== 'all') params.append('work_status', hitsStatusFilter);
      window.location.href = `${BASE_PATH}/api/hits/export?${params.toString()}`;
    }
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    print(f"[*] Iniciando Santander Excel Pro en http://127.0.0.1:8055 (Pass: {AUTH_PASSWORD})...")
    uvicorn.run(app, host="127.0.0.1", port=8055, log_level="info")
