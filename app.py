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

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from typing import Any, Optional
from fastapi import FastAPI, Query, HTTPException, Request, Response, Depends
from fastapi.responses import HTMLResponse, JSONResponse, Response as RawResponse
from pydantic import BaseModel
import uvicorn

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "santander.db"))
if not os.path.exists(DB_PATH):
    fallback_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "santander.db"))
    if os.path.exists(fallback_path):
        DB_PATH = fallback_path

AUTH_PASSWORD = "Santabase"
SECRET_KEY = os.environ.get("SANTANDER_SECRET", "santander-super-secret-vault-2026")
COOKIE_NAME = "santander_session"

app = FastAPI(title="Santander Database Viewer - Excel Edition")

DB_COLUMNS = [
    "id", "u6rfc", "curp", "curp_status", "curp_falta", "dmname", "genero", "fecha_nacimiento",
    "ciudad", "estado", "codigo_postal", "results", "u6acct", "u6cvereg", "u6numcto",
    "dmssnum", "dmaddr1", "dmaddr2", "u6delomu", "u6estado", "dmcity", "dmzip",
    "u6ladte1", "u6tel1", "u6ladte2", "u6tel2", "u6licrea"
]

def generate_session_token() -> str:
    timestamp = str(int(time.time()))
    signature = hmac.new(SECRET_KEY.encode(), f"auth:{timestamp}".encode(), hashlib.sha256).hexdigest()
    return f"{timestamp}:{signature}"

def verify_session_token(token: Optional[str]) -> bool:
    if not token or ":" not in token:
        return False
    try:
        timestamp_str, signature = token.split(":", 1)
        timestamp = int(timestamp_str)
        if time.time() - timestamp > 30 * 86400:
            return False
        expected_sig = hmac.new(SECRET_KEY.encode(), f"auth:{timestamp_str}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected_sig)
    except Exception:
        return False

def check_auth(request: Request) -> bool:
    cookie_token = request.cookies.get(COOKIE_NAME)
    if verify_session_token(cookie_token):
        return True
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token == AUTH_PASSWORD or verify_session_token(token):
            return True
    return False

def require_auth(request: Request):
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="No autorizado. Ingrese contraseña.")

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

# --- Rutas de Autenticación ---

@app.post("/api/auth/login")
def login(payload: LoginPayload, response: Response):
    if payload.password.strip() == AUTH_PASSWORD:
        token = generate_session_token()
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=30 * 86400,
            httponly=True,
            samesite="lax",
            path="/"
        )
        return {"ok": True, "token": token}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")

@app.get("/api/auth/status")
def auth_status(request: Request):
    return {"authenticated": check_auth(request)}

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
        return {
            "total": total,
            "with_curp": with_curp,
            "curp_calculada": curp_calculada,
            "curp_existente": curp_existente,
            "curp_no_calculable": curp_no_calculable,
            "with_results": with_results,
            "without_curp": total - with_curp
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
        return {"ok": True, "updated_id": record_id, "record": row_dict}
    finally:
        conn.close()

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

@app.get("/", response_class=HTMLResponse)
@app.get("/santander", response_class=HTMLResponse)
@app.get("/santander/", response_class=HTMLResponse)
def index(request: Request):
    return HTML_CONTENT

HTML_CONTENT = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Santander DB — Excel Pro Grid (Bóveda Operativa)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      /* Superficies y Fondos */
      --bg-app: #080d1a;
      --bg-card: #0f172a;
      --bg-surface: #131c31;
      --bg-surface-elevated: #1e293b;
      --bg-row-hover: #162238;
      --bg-row-selected: #1e3a5f;
      --excel-selection-bg: rgba(2, 132, 199, 0.15);

      /* Bordes y Divisiones */
      --border: #1e293b;
      --border-subtle: #1e293d;
      --border-strong: #334155;
      --border-focus: #0284c7;

      /* Radios de curvatura */
      --radius-sm: 4px;
      --radius-md: 6px;
      --radius-lg: 8px;
      --radius-full: 9999px;

      /* Sistema Semantico de Color (3 Niveles) */
      /* Nivel 1: Primario (Accion Principal / Foco) */
      --color-primary: #0284c7;
      --color-primary-hover: #0369a1;
      --color-primary-active: #075985;
      --color-primary-ring: rgba(2, 132, 199, 0.35);

      /* Nivel 2: Secundario / Neutro (Acciones frecuentes, Toolbar, Copia) */
      --color-neutral-bg: #1e293b;
      --color-neutral-border: #334155;
      --color-neutral-hover: #27354a;
      --color-neutral-text: #e2e8f0;

      /* Nivel 3: Destructivo / Peligro (Logout, Reset, Alertas) */
      --color-danger: #ec0000;
      --color-danger-hover: #dc2626;
      --color-danger-subtle: rgba(236, 0, 0, 0.12);
      --color-danger-border: rgba(236, 0, 0, 0.35);

      /* Marca Santander (Solo badge oficial) */
      --santander: #ec0000;

      /* Tipografia */
      --font-mono: 'JetBrains Mono', monospace;
      --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --font-size-base: 13px;
      --font-size-cell: 12.5px;
      --font-size-header: 11.5px;
      --font-size-btn: 12.5px;
      --font-size-small: 11px;
      --font-size-kpi-val: 16px;
      --font-size-kpi-lbl: 10px;

      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --text-dim: #64748b;

      /* Dimensiones de Celdas (Respirar) */
      --cell-h: 36px;
      --cell-pad-x: 10px;
      --cell-pad-y: 6px;

      /* Microinteracciones */
      --transition-fast: all 140ms ease;
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
    .badge-santander {
      background: var(--santander);
      color: #fff;
      font-weight: 800;
      font-size: 10.5px;
      padding: 2px 7px;
      border-radius: var(--radius-sm);
      letter-spacing: 0.5px;
    }
    .badge-excel {
      background: #064e3b;
      color: #34d399;
      border: 1px solid #059669;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: var(--radius-sm);
    }
    .app-title {
      display: flex;
      align-items: baseline;
      gap: 5px;
      font-size: 15px;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.3px;
    }
    .brand-santa {
      font-size: 19px;
      font-weight: 900;
      color: var(--santander);
      letter-spacing: -0.6px;
      text-shadow: 0 0 14px rgba(236, 0, 0, 0.35);
    }
    .brand-pray {
      font-size: 14px;
      filter: drop-shadow(0 0 3px rgba(236, 0, 0, 0.4));
      transform: translateY(-1px);
    }
    .brand-base {
      font-size: 14px;
      font-weight: 800;
      font-style: italic;
      letter-spacing: 1.8px;
      background: linear-gradient(90deg, #ec0000 0%, #f59e0b 100%);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }
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
    .kpi-card.curp .kpi-val { color: #34d399; }
    .kpi-card.calc .kpi-val { color: #38bdf8; }
    .kpi-card.missing .kpi-val { color: #fb923c; }
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

    /* Formula Bar */
    .formula-bar-container {
      display: flex;
      align-items: center;
      gap: 8px;
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 5px 10px;
      margin: 6px 0;
      flex-shrink: 0;
    }
    .cell-coord-box {
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: var(--color-primary);
      font-family: var(--font-mono);
      font-weight: 700;
      font-size: var(--font-size-small);
      padding: 3px 10px;
      border-radius: var(--radius-sm);
      min-width: 140px;
      text-align: center;
      letter-spacing: 0.5px;
      white-space: nowrap;
    }
    .fx-symbol {
      color: var(--text-muted);
      font-family: var(--font-mono);
      font-weight: 700;
      font-style: italic;
      font-size: 13px;
      padding: 0 3px;
    }
    .formula-input {
      flex: 1;
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      font-family: var(--font-mono);
      font-size: var(--font-size-cell);
      padding: 4px 10px;
      border-radius: var(--radius-sm);
      outline: none;
      transition: var(--transition-fast);
    }
    .formula-input:focus {
      border-color: var(--border-focus);
      box-shadow: 0 0 0 2px var(--color-primary-ring);
    }
    .formula-input.readonly {
      color: var(--text-muted);
      background: rgba(13, 18, 28, 0.6);
      cursor: not-allowed;
    }
    .keyboard-hint {
      font-size: 11px;
      color: var(--text-muted);
      white-space: nowrap;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .kbd {
      background: #1e293b;
      border: 1px solid #334155;
      padding: 2px 5px;
      border-radius: 3px;
      font-family: var(--font-mono);
      font-size: 10px;
      color: #cbd5e1;
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
      box-shadow: 0 2px 8px rgba(2, 132, 199, 0.35);
    }
    .btn-excel {
      background: #0f766e;
      border-color: #115e59;
      color: #fff;
      font-weight: 600;
    }
    .btn-excel:hover {
      background: #115e59;
      border-color: #134e4a;
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

    /* Grid Table Container */
    .grid-container {
      flex: 1;
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
      background: #0d1424;
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
      background: #0a0f1b;
      color: var(--text-dim);
      font-family: var(--font-mono);
      font-size: 10px;
      position: sticky;
      left: 0;
      z-index: 30;
      border-right: 1px solid #27354f;
    }
    td.row-num-cell {
      position: sticky;
      left: 0;
      z-index: 10;
      background: #0d1424;
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
      color: #60a5fa;
      background: #1e293b;
      padding: 2px 5px;
      border-radius: var(--radius-sm);
      border: 1px solid #334155;
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
    .tag-btn.hit { border-color: #059669; color: #34d399; background: #064e3b; font-weight: 700; }
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

    /* Menú contextual */
    .context-menu {
      display: none;
      position: fixed;
      background: var(--bg-card);
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-md);
      box-shadow: 0 12px 28px rgba(0,0,0,0.65);
      width: 190px;
      z-index: 1100;
      padding: 5px 0;
    }
    .context-menu.show { display: block; }
    .ctx-item {
      padding: 6px 12px;
      font-size: 11.5px;
      color: #e2e8f0;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 7px;
      transition: var(--transition-fast);
    }
    .ctx-item:hover { background: var(--color-primary); color: #fff; }
    .ctx-item-danger:hover { background: var(--color-danger); color: #fff; }
    .ctx-sep { height: 1px; background: var(--border); margin: 5px 0; }

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
      background: rgba(2, 132, 199, 0.15);
      color: #38bdf8 !important;
      text-decoration: underline;
    }
    .rfc-text {
      color: #cbd5e1;
      font-family: var(--font-mono);
      font-size: var(--font-size-cell);
      letter-spacing: 0.5px;
    }
    .rfc-date {
      color: #38bdf8;
      font-weight: 700;
      background: rgba(56, 189, 248, 0.08);
      padding: 0 2px;
      border-radius: 2px;
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
  </style>
</head>
<body>

  <!-- Lock Screen Overlay -->
  <div id="lock-screen">
    <div class="lock-card">
      <div class="lock-icon-circle">🔒</div>
      <div style="margin-bottom: 10px;">
        <span class="badge-santander">SANTANDER</span>
      </div>
      <h2 class="lock-title">Bóveda Operativa</h2>
      <p class="lock-subtitle">Ingresa la contraseña para desbloquear los controles tipo Excel y la base de datos de 4.9M de registros.</p>
      
      <div class="password-input-group">
        <input type="password" id="login-password" class="password-input" placeholder="Contraseña de acceso..." onkeydown="if(event.key==='Enter') submitLogin()">
        <button class="eye-btn" onclick="togglePasswordVisibility()" title="Mostrar/Ocultar">👁</button>
      </div>

      <button class="btn-login" onclick="submitLogin()">Desbloquear Bóveda ➔</button>
      <div id="lock-error" class="lock-error">Contraseña incorrecta. Intenta de nuevo.</div>
    </div>
  </div>

  <!-- Top Bar -->
  <div class="top-bar">
    <div class="brand-group">
      <span class="badge-santander">SANTANDER</span>
      <h1 class="app-title"><span class="brand-santa">SANTA</span><span class="brand-pray">🙏🏻</span><span class="brand-base">BASE</span></h1>
      <span class="badge-excel">📊 EXCEL PRO GRID</span>
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
      <button class="btn-logout" onclick="doLogout()" title="Cerrar sesión">Cerrar Sesión</button>
    </div>
  </div>

  <!-- Excel Formula & Value Bar -->
  <div class="formula-bar-container">
    <div class="cell-coord-box" id="cell-coord">C1 (CURP)</div>
    <span class="fx-symbol">fx</span>
    <input type="text" id="formula-input" class="formula-input" placeholder="Selecciona una celda...">
    <div class="keyboard-hint">
      <span class="kbd">↑↓←→</span> Navegar
      <span class="kbd">Enter</span>/<span class="kbd">F2</span> Editar CURP
      <span class="kbd">Tab</span> Avanzar
      <span class="kbd">Ctrl+C/V</span> Copiar/Pegar <span class="kbd">Arrastrar / Ctrl+Clic</span> Multiselección
    </div>
  </div>

  <!-- Toolbar con 4 Clusters Visuales y Segmented Control -->
  <div class="toolbar">
    <!-- 1. Búsqueda y Filtros Predefinidos (Segmented Control) -->
    <div class="tb-group">
      <div class="filter-tabs">
        <button class="tab-btn active" onclick="setPresetFilter('all')">Todos</button>
        <button class="tab-btn" onclick="setPresetFilter('no_curp')">Falta CURP</button>
        <button class="tab-btn" onclick="setPresetFilter('has_curp')">Con CURP</button>
        <button class="tab-btn" onclick="setPresetFilter('calculada')">Calculadas</button>
        <button class="tab-btn" onclick="setPresetFilter('no_calculable')">No Calculables</button>
        <button class="tab-btn" onclick="setPresetFilter('has_results')">Con Result</button>
      </div>
      <input type="text" id="global-search" class="global-search" placeholder="🔍 Buscar RFC, Nombre, Ciudad..." onkeydown="if(event.key==='Enter') applyGlobalSearch()">
      <button class="btn btn-primary" onclick="applyGlobalSearch()">Buscar</button>
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
  </div>

  <!-- Active Filters Indicator Bar -->
  <div id="active-filters-bar">
    <span style="font-weight:700; color:#38bdf8;">Filtros activos:</span>
    <div id="active-filters-chips" style="display:flex; gap:5px; flex-wrap:wrap;"></div>
  </div>

  <!-- Grid Table Container -->
  <div class="grid-container" id="grid-container">
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
    <div class="ctx-item" onclick="ctxCopyCell()">📋 Copiar Celda (Ctrl+C)</div>
    <div class="ctx-item" onclick="ctxCopyRfc()">📄 Copiar RFC de Fila</div>
    <div class="ctx-item" onclick="ctxCopyRow()">📑 Copiar Fila Completa</div>
    <div class="ctx-sep"></div>
    <div class="ctx-item" id="ctx-paste-item" onclick="ctxPasteCell()">📥 Pegar CURP (Ctrl+V)</div>
    <div class="ctx-item ctx-item-danger" id="ctx-clear-item" onclick="ctxClearCell()">🧹 Borrar CURP (Supr)</div>
    <div class="ctx-sep"></div>
    <div class="ctx-item" onclick="ctxMarkResult('HIT')">🟢 Marcar HIT</div>
    <div class="ctx-item" onclick="ctxMarkResult('DEAD')">🔴 Marcar DEAD</div>
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
    const BASE_PATH = window.location.pathname.startsWith('/santander') ? '/santander' : '';

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
      { key: "results", label: "RESULTS", letter: "I", width: "95px", mono: false, editable: false },
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


    checkSession();

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
    }

    function initApp() {
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
        document.getElementById('stat-total').innerText = data.total.toLocaleString();
        document.getElementById('stat-curp').innerText = data.with_curp.toLocaleString();
        document.getElementById('stat-calc').innerText = (data.curp_calculada || 0).toLocaleString();
        document.getElementById('stat-no-curp').innerText = data.without_curp.toLocaleString();
        document.getElementById('stat-results').innerText = data.with_results.toLocaleString();
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
              let tagBadge = '';
              if (rawVal === 'HIT') tagBadge = '<span class="tag-btn hit">HIT</span>';
              else if (rawVal === 'DEAD') tagBadge = '<span class="tag-btn dead">DEAD</span>';
              displayContent = `<span>${rawVal}</span> ${tagBadge}`;
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
      }
    }

    function setupFormulaBarListener() {
      const formulaInput = document.getElementById('formula-input');
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
      document.getElementById('formula-input').value = newVal;

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

    function updateCellDisplay(cell, colKey, val) {
      let displayContent = escapeHtml(val);
      if (colKey === 'curp') {
        if (val) {
          displayContent = `<span class="curp-pill">${escapeHtml(val)}</span>`;
        } else {
          displayContent = `<span class="curp-empty">+ Ingresar CURP</span>`;
        }
      } else if (colKey === 'results') {
        let tagBadge = '';
        if (val === 'HIT') tagBadge = '<span class="tag-btn hit">HIT</span>';
        else if (val === 'DEAD') tagBadge = '<span class="tag-btn dead">DEAD</span>';
        displayContent = `<span>${escapeHtml(val)}</span> ${tagBadge}`;
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
        if (['login-password', 'search-input', 'global-search', 'popover-filter-val', 'bulk-curp-text'].includes(e.target.id)) {
          return;
        }

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
      menu.style.top = `${e.clientY}px`;
      menu.style.left = `${e.clientX}px`;
      menu.classList.add('show');
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

    function setPresetFilter(f) {
      currentPresetFilter = f;
      currentPage = 1;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      event.target.classList.add('active');
      loadRecords();
    }

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
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    print(f"[*] Iniciando Santander Excel Pro en http://127.0.0.1:8055 (Pass: {AUTH_PASSWORD})...")
    uvicorn.run(app, host="127.0.0.1", port=8055, log_level="info")
