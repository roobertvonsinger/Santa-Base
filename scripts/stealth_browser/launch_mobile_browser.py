"""Stealth Mobile Browser (Sovereign & Resource-Optimized Edition) — Santa Base
Optimizado para Onboarding Santander (Débito LikeU y Biometría FAD).
- Cero fugas de datos / proxy leaks (sin sockets huérfanos ni bucles de pestañas).
- Mapeo GPS determinista y ultra-rápido (cero consumo de MB en APIs externas).
- Soporte Multi-Proxy con conmutación nativa limpia, EN CALIENTE, sin perder sesión.
- Emulación móvil Pixel 7 (Android 14) con permisos pre-otorgados.
- Persistencia de sesión y cookies resiliente.

Fuente canónica del StealthMobileBrowser.exe (2026-09-26). Revisado y extendido 2026-09-30:
- El proxy por defecto (NodeMaven `luiscael70_gmail_com`) esta sin saldo (402) — se deja vacio
  a proposito, YA NO se auto-carga un default muerto que confunda al operador.
- Nuevo: pista de region objetivo (de que estado es el cliente) visible en el dialogo de arranque,
  para que el operador sepa que proxy pegar o si le conviene usar su propia IP local.
- Nuevo: agregar/cambiar un proxy AL VUELO desde el panel flotante sin reiniciar el navegador
  (antes solo se podia elegir entre los proxies cargados al inicio). La sesion (cookies,
  storage_state) ya se preservaba entre cambios de proxy — ahora tambien al agregar uno nuevo.
- Nuevo: `--curp=`, `--estado=`, `--operator-estado=` (o env SANTABASE_OPERATOR_ESTADO) para
  lanzarlo pre-configurado desde la boveda de hits de Santa Base.
"""

import os
import sys
import time
import json
import random
import shutil
import tempfile
import threading
import queue
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# ==============================================================================
# DEFAULTS & CONSTANTES
# ==============================================================================
# Antes traia un proxy NodeMaven hardcodeado por defecto. Esa cuenta esta sin saldo (402,
# verificado 2026-09-30) — dejarlo cargado por default hace creer al operador que hay un proxy
# activo cuando en realidad esta muerto. Se deja vacio: el operador pega uno vivo, o usa Directo.
DEFAULT_PROXIES: list[str] = []

URL_START = "https://onboarding.santander.com.mx/cuenta-digital-lite/personal-data?utm_source=portal_publico&utm_medium=landing_page&utm_campaign=debito_likeu"

USER_DATA_BASE = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~")), "StealthMobileBrowser")
os.makedirs(USER_DATA_BASE, exist_ok=True)
SESSION_META_FILE = os.path.join(USER_DATA_BASE, "last_session.json")
SESSION_STORAGE_STATE = os.path.join(USER_DATA_BASE, "storage_state.json")
OPERATOR_CONFIG_FILE = os.path.join(USER_DATA_BASE, "operator_config.json")
NETWORK_LOG_FILE = os.path.join(USER_DATA_BASE, "network_debug.log")


def _log_network_event(line: str):
    """Evidencia cruda de requests/responses contra Santander durante la sesión — para
    confirmar con datos (no suposición) si el backend valida geolocation reportada por el
    cliente, IP de origen, o ambos. Ver network_debug.log junto a storage_state.json."""
    try:
        with open(NETWORK_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S')} {line}\n")
    except Exception:
        pass

# Coordenadas estáticas para evitar consumo de MB en NodeMaven / detectar region por texto del
# username del proxy o por el --estado= pasado desde la boveda.
MEXICO_FALLBACK_COORDS = {
    "oaxaca": {"city": "Oaxaca de Juárez", "region": "Oaxaca", "lat": 17.0608, "lon": -96.7253, "timezone": "America/Mexico_City"},
    "monterrey": {"city": "Monterrey", "region": "Nuevo León", "lat": 25.6866, "lon": -100.3161, "timezone": "America/Monterrey"},
    "nuevo_leon": {"city": "Monterrey", "region": "Nuevo León", "lat": 25.6866, "lon": -100.3161, "timezone": "America/Monterrey"},
    "nuevo leon": {"city": "Monterrey", "region": "Nuevo León", "lat": 25.6866, "lon": -100.3161, "timezone": "America/Monterrey"},
    "guadalajara": {"city": "Guadalajara", "region": "Jalisco", "lat": 20.6597, "lon": -103.3496, "timezone": "America/Mexico_City"},
    "jalisco": {"city": "Guadalajara", "region": "Jalisco", "lat": 20.6597, "lon": -103.3496, "timezone": "America/Mexico_City"},
    "ciudad_de_mexico": {"city": "Ciudad de México", "region": "CDMX", "lat": 19.4326, "lon": -99.1332, "timezone": "America/Mexico_City"},
    "ciudad de mexico": {"city": "Ciudad de México", "region": "CDMX", "lat": 19.4326, "lon": -99.1332, "timezone": "America/Mexico_City"},
    "cdmx": {"city": "Ciudad de México", "region": "CDMX", "lat": 19.4326, "lon": -99.1332, "timezone": "America/Mexico_City"},
    "mexico_city": {"city": "Ciudad de México", "region": "CDMX", "lat": 19.4326, "lon": -99.1332, "timezone": "America/Mexico_City"},
    "puebla": {"city": "Puebla", "region": "Puebla", "lat": 19.0414, "lon": -98.2063, "timezone": "America/Mexico_City"},
    "queretaro": {"city": "Santiago de Querétaro", "region": "Querétaro", "lat": 20.5888, "lon": -100.3899, "timezone": "America/Mexico_City"},
    "tijuana": {"city": "Tijuana", "region": "Baja California", "lat": 32.5149, "lon": -117.0382, "timezone": "America/Tijuana"},
    "mexicali": {"city": "Mexicali", "region": "Baja California", "lat": 32.6245, "lon": -115.4523, "timezone": "America/Tijuana"},
    "cancun": {"city": "Cancún", "region": "Quintana Roo", "lat": 21.1619, "lon": -86.8515, "timezone": "America/Cancun"},
    "merida": {"city": "Mérida", "region": "Yucatán", "lat": 20.9674, "lon": -89.5926, "timezone": "America/Merida"},
    "veracruz": {"city": "Veracruz", "region": "Veracruz", "lat": 19.1738, "lon": -96.1342, "timezone": "America/Mexico_City"},
    "chiapas": {"city": "Tuxtla Gutiérrez", "region": "Chiapas", "lat": 16.7569, "lon": -93.1292, "timezone": "America/Mexico_City"},
    "leon": {"city": "León", "region": "Guanajuato", "lat": 21.1221, "lon": -101.6826, "timezone": "America/Mexico_City"},
    "guanajuato": {"city": "León", "region": "Guanajuato", "lat": 21.1221, "lon": -101.6826, "timezone": "America/Mexico_City"},
    "culiacan": {"city": "Culiacán", "region": "Sinaloa", "lat": 24.8091, "lon": -107.3940, "timezone": "America/Mazatlan"},
    "sinaloa": {"city": "Culiacán", "region": "Sinaloa", "lat": 24.8091, "lon": -107.3940, "timezone": "America/Mazatlan"},
    "hermosillo": {"city": "Hermosillo", "region": "Sonora", "lat": 29.0729, "lon": -110.9559, "timezone": "America/Hermosillo"},
    "sonora": {"city": "Hermosillo", "region": "Sonora", "lat": 29.0729, "lon": -110.9559, "timezone": "America/Hermosillo"},
    "chihuahua": {"city": "Chihuahua", "region": "Chihuahua", "lat": 28.6353, "lon": -106.0889, "timezone": "America/Chihuahua"},
    "saltillo": {"city": "Saltillo", "region": "Coahuila", "lat": 25.4260, "lon": -101.0053, "timezone": "America/Monterrey"},
    "coahuila": {"city": "Saltillo", "region": "Coahuila", "lat": 25.4260, "lon": -101.0053, "timezone": "America/Monterrey"},
    "san_luis_potosi": {"city": "San Luis Potosí", "region": "San Luis Potosí", "lat": 22.1565, "lon": -100.9855, "timezone": "America/Mexico_City"},
    "aguascalientes": {"city": "Aguascalientes", "region": "Aguascalientes", "lat": 21.8853, "lon": -102.2916, "timezone": "America/Mexico_City"},
    "cuernavaca": {"city": "Cuernavaca", "region": "Morelos", "lat": 18.9242, "lon": -99.2216, "timezone": "America/Mexico_City"},
    "morelos": {"city": "Cuernavaca", "region": "Morelos", "lat": 18.9242, "lon": -99.2216, "timezone": "America/Mexico_City"},
    "toluca": {"city": "Toluca", "region": "Estado de México", "lat": 19.2826, "lon": -99.6557, "timezone": "America/Mexico_City"},
    "estado_de_mexico": {"city": "Toluca", "region": "Estado de México", "lat": 19.2826, "lon": -99.6557, "timezone": "America/Mexico_City"},
    "hidalgo": {"city": "Pachuca", "region": "Hidalgo", "lat": 20.1011, "lon": -98.7591, "timezone": "America/Mexico_City"},
    "durango": {"city": "Durango", "region": "Durango", "lat": 24.0277, "lon": -104.6532, "timezone": "America/Mexico_City"},
}


def normalize_estado(raw: str) -> str:
    """Normaliza un nombre de estado (mayusculas/acentos/espacios/guiones) para comparar y
    para buscarlo como llave/substring en MEXICO_FALLBACK_COORDS."""
    if not raw:
        return ""
    s = raw.strip().lower()
    repl = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    for a, b in repl.items():
        s = s.replace(a, b)
    return s


def lookup_region_coords(estado_text: str) -> dict | None:
    """Busca coordenadas para un nombre de estado (viene de --estado= o del username del proxy)."""
    norm = normalize_estado(estado_text)
    if not norm:
        return None
    # Match directo por llave
    key_norm = norm.replace(" ", "_")
    if key_norm in MEXICO_FALLBACK_COORDS:
        return MEXICO_FALLBACK_COORDS[key_norm]
    # Match por substring en ambos sentidos (ej. "ciudad de mexico" contiene "cdmx"? no, al reves:
    # candidatos como "jalisco" dentro de "estado: jalisco, mx")
    for key, loc in MEXICO_FALLBACK_COORDS.items():
        key_spaced = key.replace("_", " ")
        if key_spaced in norm or norm in key_spaced:
            return loc
    return None


def load_operator_config() -> dict:
    if os.path.exists(OPERATOR_CONFIG_FILE):
        try:
            with open(OPERATOR_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_operator_config(cfg: dict):
    try:
        with open(OPERATOR_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def parse_proxy(raw_str: str) -> dict:
    raw = (raw_str or "").strip()
    if not raw:
        return {}
    server = ""
    host = ""
    port = 8080
    username = ""
    password = ""
    if "@" in raw:
        clean = raw.replace("http://", "").replace("https://", "")
        auth, host_port = clean.split("@", 1)
        server = f"http://{host_port}"
        if ":" in host_port:
            host, port = host_port.split(":", 1)
            port = int(port)
        else:
            host = host_port
        if ":" in auth:
            username, password = auth.split(":", 1)
        else:
            username = auth
    elif raw.count(":") >= 3:
        parts = raw.split(":")
        host = parts[0]
        port = int(parts[1])
        server = f"http://{host}:{port}"
        username = parts[2]
        password = ":".join(parts[3:])
    elif raw.count(":") == 1:
        parts = raw.replace("http://", "").replace("https://", "").split(":")
        host = parts[0]
        port = int(parts[1])
        server = f"http://{host}:{port}"
    else:
        host = raw
        server = raw

    return {
        "raw": raw,
        "server": server,
        "host": host,
        "port": port,
        "username": username,
        "password": password,
    }


def get_proxy_location(proxy_dict: dict, region_hint: str | None = None) -> dict:
    """Ubicación aproximada del proxy, sin gastar cuota en llamadas externas.
    Prioridad: 1) coincide con el --estado= del hit (region_hint) si el username del proxy lo
    menciona, 2) cualquier estado detectado en el username del proxy, 3) Oaxaca como fallback
    generico (mejor eso que nada, pero NUNCA se presenta como certeza — ver HUD)."""
    user = (proxy_dict.get("username") or "").lower()

    if region_hint:
        hint_norm = normalize_estado(region_hint)
        for key, loc in MEXICO_FALLBACK_COORDS.items():
            if key in user and (key in hint_norm or hint_norm in key.replace("_", " ")):
                lat = loc["lat"] + random.uniform(-0.001, 0.001)
                lon = loc["lon"] + random.uniform(-0.001, 0.001)
                return {**loc, "lat": round(lat, 5), "lon": round(lon, 5), "matched_hint": True}

    for key, loc in MEXICO_FALLBACK_COORDS.items():
        if key in user:
            lat = loc["lat"] + random.uniform(-0.001, 0.001)
            lon = loc["lon"] + random.uniform(-0.001, 0.001)
            return {**loc, "lat": round(lat, 5), "lon": round(lon, 5), "matched_hint": False}

    return {
        "city": "Oaxaca de Juárez",
        "region": "Oaxaca",
        "lat": round(17.0608 + random.uniform(-0.001, 0.001), 5),
        "lon": round(-96.7253 + random.uniform(-0.001, 0.001), 5),
        "timezone": "America/Mexico_City",
        "matched_hint": False,
    }


def resolve_direct_mode_location(region_hint: str | None) -> dict:
    """Ubicación a reportar vía geolocation cuando el operador usa su IP local (Directo).
    El supuesto de 'Directo' es que el operador YA está físicamente en el estado del hit, así
    que el GPS reportado debe coincidir con el estado del hit (region_hint), nunca quedarse en
    un default fijo (antes: CDMX hardcodeado en el arranque, o (0,0) en el switch en caliente —
    ambos mandaban una ubicación que no correspondía al hit real)."""
    loc = lookup_region_coords(region_hint) if region_hint else None
    if loc:
        return {**loc, "matched_hint": True}
    return {
        "city": "Ciudad de México",
        "region": "CDMX",
        "lat": 19.4326,
        "lon": -99.1332,
        "timezone": "America/Mexico_City",
        "matched_hint": False,
    }


class ProxyManager:
    def __init__(self, proxy_list: list[str], direct_mode: bool = False):
        self.direct_mode = direct_mode
        self.proxies = [parse_proxy(p) for p in proxy_list if p.strip()][:10]
        self.current_idx = 0

    def get_current(self) -> dict | None:
        if self.direct_mode or not self.proxies:
            return None
        return self.proxies[self.current_idx]

    def next_proxy(self) -> tuple[int, dict | None]:
        if self.direct_mode or not self.proxies:
            return 0, None
        self.current_idx = (self.current_idx + 1) % len(self.proxies)
        return self.current_idx, self.proxies[self.current_idx]

    def set_index(self, idx: int) -> dict | None:
        if 0 <= idx < len(self.proxies):
            self.current_idx = idx
            return self.proxies[self.current_idx]
        return None

    def add_and_select(self, raw_proxy: str) -> dict | None:
        """Agrega un proxy nuevo EN CALIENTE (sin reiniciar) y lo deja activo. Si ya hay 10,
        reemplaza el mas antiguo que no sea el activo actual (nunca se queda sin proxies)."""
        p = parse_proxy(raw_proxy)
        if not p or not p.get("host"):
            return None
        if len(self.proxies) >= 10:
            drop_idx = 0 if self.current_idx != 0 else 1
            self.proxies.pop(drop_idx)
            if self.current_idx > drop_idx:
                self.current_idx -= 1
        self.proxies.append(p)
        self.current_idx = len(self.proxies) - 1
        self.direct_mode = False
        return p


def find_browser_executable() -> tuple[str | None, str]:
    chrome_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in chrome_candidates:
        if c and os.path.exists(c):
            return c, "Google Chrome"

    which_chrome = shutil.which("chrome") or shutil.which("google-chrome")
    if which_chrome:
        return which_chrome, "Google Chrome"

    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for e in edge_candidates:
        if e and os.path.exists(e):
            return e, "Microsoft Edge"

    which_edge = shutil.which("msedge")
    if which_edge:
        return which_edge, "Microsoft Edge"

    return None, "Playwright Bundled Chromium"


def load_last_session_meta() -> dict | None:
    if os.path.exists(SESSION_META_FILE) and os.path.exists(SESSION_STORAGE_STATE):
        try:
            with open(SESSION_META_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data and isinstance(data, dict) and data.get("urls"):
                return data
        except Exception:
            pass
    return None


def show_startup_dialog(default_proxies: list[str], region_hint: str | None = None,
                         operator_estado: str | None = None, initial_curp: str | None = None) -> dict:
    last_session = load_last_session_meta()
    if last_session and last_session.get("proxies"):
        default_proxies = last_session["proxies"]

    region_norm = normalize_estado(region_hint) if region_hint else ""
    operator_norm = normalize_estado(operator_estado) if operator_estado else ""
    matches_operator = bool(region_norm) and bool(operator_norm) and (
        region_norm == operator_norm or region_norm in operator_norm or operator_norm in region_norm
    )

    result = {
        "use_proxy": not matches_operator,  # si el operador ya esta en el estado del cliente, Directo por default
        "proxies": default_proxies,
        "cancelled": False,
        "restore_session": bool(last_session),
        "session_meta": last_session,
        "region_hint": region_hint,
        "curp": initial_curp,
    }

    root = tk.Tk()
    root.title("Stealth Mobile Browser - Configuración")
    dialog_h = 560 if last_session else 480
    root.geometry(f"660x{dialog_h}")
    root.resizable(False, False)

    root.update_idletasks()
    x = max(0, (root.winfo_screenwidth() - 660) // 2)
    y = max(0, (root.winfo_screenheight() - dialog_h) // 2)
    root.geometry(f"660x{dialog_h}+{x}+{y}")

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    header = ttk.Label(frame, text="📱 Stealth Mobile Browser (Sovereign Edition)", font=("Segoe UI", 12, "bold"))
    header.pack(anchor="w", pady=(0, 6))

    # ── Pista de region objetivo del hit (si vino de la boveda con --estado=) ──
    if region_hint:
        hint_frame = ttk.LabelFrame(frame, text="🎯 Este hit es de", padding=10)
        hint_frame.pack(fill="x", pady=(0, 10))
        hint_text = f"{region_hint}"
        if matches_operator:
            hint_text += "  —  ✅ Coincide con tu ubicación configurada: usa CONEXIÓN DIRECTA (tu propia IP ya es de ahí)."
        else:
            hint_text += "  —  Pega abajo un proxy residencial de esa región/estado, o el navegador puede ser descartado por Santander."
        ttk.Label(hint_frame, text=hint_text, wraplength=610, foreground=("#0a7a2a" if matches_operator else "#aa4400")).pack(anchor="w")

    if initial_curp:
        curp_frame = ttk.LabelFrame(frame, text="CURP a trabajar", padding=6)
        curp_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(curp_frame, text=initial_curp, font=("Consolas", 11, "bold")).pack(anchor="w")

    session_choice_var = tk.StringVar(value="restore" if last_session else "clean")

    if last_session:
        time_str = last_session.get("time_str", "reciente")
        last_url = last_session.get("last_url", "Santander Onboarding")
        if len(last_url) > 65:
            last_url = last_url[:62] + "..."

        rec_frame = ttk.LabelFrame(frame, text="🔄 Recuperación de Sesión", padding=10)
        rec_frame.pack(fill="x", pady=(0, 10))

        rb_restore = ttk.Radiobutton(
            rec_frame,
            text=f"Recuperar última sesión (Guardada: {time_str})\n↳ Última página: {last_url}",
            variable=session_choice_var,
            value="restore"
        )
        rb_restore.pack(anchor="w", pady=(0, 4))

        rb_clean = ttk.Radiobutton(
            rec_frame,
            text="Iniciar sesión limpia (Desde cero)",
            variable=session_choice_var,
            value="clean"
        )
        rb_clean.pack(anchor="w", pady=(2, 0))

    mode_var = tk.StringVar(value="direct" if matches_operator else "proxy")

    def on_mode_change():
        if mode_var.get() == "proxy":
            text_proxies.config(state="normal", bg="#ffffff")
        else:
            text_proxies.config(state="disabled", bg="#f0f0f0")

    rb_proxy = ttk.Radiobutton(
        frame,
        text="🌐 Usar Lista de Proxies Residenciales (1 por línea, hasta 10) — región del proxy debe acercarse a la del cliente:",
        variable=mode_var,
        value="proxy",
        command=on_mode_change
    )
    rb_proxy.pack(anchor="w", pady=(0, 4))

    text_proxies = scrolledtext.ScrolledText(frame, width=74, height=5, font=("Consolas", 8))
    text_proxies.insert("1.0", "\n".join(default_proxies))
    text_proxies.pack(anchor="w", fill="x", pady=(0, 8))

    rb_direct = ttk.Radiobutton(
        frame,
        text="⚡ Conexión Directa (Sin Proxy) — usa TU propia IP local. Úsala si tú ya estás físicamente en el estado del cliente.",
        variable=mode_var,
        value="direct",
        command=on_mode_change
    )
    rb_direct.pack(anchor="w", pady=(0, 8))

    # ── Config del operador: su estado real, para el auto-match de "usa Directo" en la próxima vez ──
    op_frame = ttk.LabelFrame(frame, text="Tu ubicación real (para sugerir Directo automáticamente)", padding=6)
    op_frame.pack(fill="x", pady=(0, 8))
    ent_operator = ttk.Entry(op_frame, width=30)
    ent_operator.insert(0, operator_estado or "")
    ent_operator.pack(side="left", padx=(0, 6))
    ttk.Label(op_frame, text="(ej. Jalisco, Ciudad de México, Durango — se guarda para la próxima vez)", font=("Segoe UI", 8)).pack(side="left")

    on_mode_change()

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(anchor="e", fill="x", pady=(8, 0))

    def on_start():
        result["use_proxy"] = (mode_var.get() == "proxy")
        lines = [line.strip() for line in text_proxies.get("1.0", tk.END).splitlines() if line.strip()]
        result["proxies"] = lines[:10] if lines else default_proxies
        result["restore_session"] = (session_choice_var.get() == "restore")
        op_val = ent_operator.get().strip()
        if op_val:
            save_operator_config({"estado": op_val})
        root.destroy()

    def on_cancel():
        result["cancelled"] = True
        root.destroy()

    btn_cancel = ttk.Button(btn_frame, text="Cancelar", command=on_cancel)
    btn_cancel.pack(side="right", padx=(10, 0))

    btn_ok = ttk.Button(btn_frame, text="Iniciar Navegador", command=on_start)
    btn_ok.pack(side="right")

    root.protocol("WM_DELETE_WINDOW", on_cancel)
    root.focus_force()
    root.mainloop()

    return result


class ProxySwitcherWidget:
    def __init__(self, root: tk.Tk, proxy_mgr: ProxyManager, cmd_queue: queue.Queue, region_hint: str | None = None):
        self.root = root
        self.proxy_mgr = proxy_mgr
        self.cmd_queue = cmd_queue
        self.region_hint = region_hint

        root.title("⚡ Control de Proxies")
        root.geometry("460x320")
        root.attributes("-topmost", True)
        root.resizable(False, False)
        root.geometry("+540+40")

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)

        header = ttk.Label(frame, text="🔄 Conmutador de Proxies en Vivo", font=("Segoe UI", 11, "bold"))
        header.pack(anchor="w", pady=(0, 4))

        if region_hint:
            ttk.Label(frame, text=f"🎯 Región objetivo del hit: {region_hint}", font=("Segoe UI", 8, "bold"), foreground="#aa4400").pack(anchor="w", pady=(0, 4))

        self.lbl_active = ttk.Label(frame, text="Proxy Activo: Cargando...", font=("Segoe UI", 9, "bold"), foreground="#0055aa")
        self.lbl_active.pack(anchor="w", pady=(2, 2))

        self.lbl_geo = ttk.Label(frame, text="Ubicación: Sincronizando...", font=("Segoe UI", 8), foreground="#333")
        self.lbl_geo.pack(anchor="w", pady=(0, 8))

        self.combo_var = tk.StringVar()
        self.combo = ttk.Combobox(frame, values=self._combo_options(), state="readonly", textvariable=self.combo_var, font=("Segoe UI", 9))
        if self.proxy_mgr.proxies:
            self.combo.current(self.proxy_mgr.current_idx)
        self.combo.pack(anchor="w", fill="x", pady=(0, 10))
        self.combo.bind("<<ComboboxSelected>>", self.on_select_combo)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(0, 8))

        self.btn_next = ttk.Button(btn_frame, text="🔄 Siguiente Proxy", command=self.on_click_next)
        self.btn_next.pack(side="left", expand=True, fill="x", padx=(0, 3))

        self.btn_reload = ttk.Button(btn_frame, text="🔃 Recargar", command=self.on_click_reload)
        self.btn_reload.pack(side="left", expand=True, fill="x", padx=(3, 3))

        self.btn_direct = ttk.Button(btn_frame, text="⚡ Usar Directo", command=self.on_click_direct)
        self.btn_direct.pack(side="left", expand=True, fill="x", padx=(3, 0))

        # ── Agregar/cambiar proxy EN CALIENTE sin cerrar el navegador ni perder la sesion ──
        add_frame = ttk.LabelFrame(frame, text="➕ Agregar / Cambiar Proxy (en caliente, sin perder sesión)", padding=6)
        add_frame.pack(fill="x", pady=(6, 8))
        self.ent_new_proxy = ttk.Entry(add_frame, font=("Consolas", 8))
        self.ent_new_proxy.pack(fill="x", pady=(0, 4))
        self.ent_new_proxy.insert(0, "host:port:user:pass  (pega y da clic)")
        self.ent_new_proxy.bind("<FocusIn>", lambda e: self.ent_new_proxy.delete(0, "end") if "pega y da clic" in self.ent_new_proxy.get() else None)
        self.btn_add = ttk.Button(add_frame, text="✅ Usar este proxy ahora", command=self.on_click_add_proxy)
        self.btn_add.pack(fill="x")

        self.lbl_status = ttk.Label(
            frame,
            text="Listo para navegar. Sin drenes de datos.",
            font=("Segoe UI", 8, "italic"),
            foreground="#28a745"
        )
        self.lbl_status.pack(anchor="w", pady=(4, 0))

        self.update_display()

    def _combo_options(self):
        opts = [f"Proxy #{i+1}: {p.get('host', 'Direct')}:{p.get('port', '')}" for i, p in enumerate(self.proxy_mgr.proxies)]
        return opts if opts else ["Conexión Directa"]

    def update_display(self):
        cur = self.proxy_mgr.get_current()
        idx = self.proxy_mgr.current_idx + 1
        total = max(1, len(self.proxy_mgr.proxies))
        loc = get_proxy_location(cur, self.region_hint) if cur else resolve_direct_mode_location(self.region_hint)

        if cur:
            self.lbl_active.config(text=f"Proxy [{idx}/{total}]: {cur.get('host')}:{cur.get('port')}")
            match_note = "✅ coincide con la región del hit" if loc.get("matched_hint") else "⚠️ región sin confirmar, verifica el proxy"
            self.lbl_geo.config(text=f"📍 {loc.get('city')}, {loc.get('region')} — {match_note}")
        else:
            self.lbl_active.config(text="Modo: Conexión Directa (tu IP local)")
            self.lbl_geo.config(text="📍 Usando tu ubicación física real")

        self.combo["values"] = self._combo_options()
        if self.proxy_mgr.proxies:
            self.combo.current(self.proxy_mgr.current_idx)

    def on_select_combo(self, event=None):
        idx = self.combo.current()
        self.proxy_mgr.set_index(idx)
        self.proxy_mgr.direct_mode = False
        self.apply_switch()

    def on_click_next(self):
        self.proxy_mgr.next_proxy()
        self.apply_switch()

    def on_click_direct(self):
        self.proxy_mgr.direct_mode = True
        self.apply_switch()

    def on_click_add_proxy(self):
        raw = self.ent_new_proxy.get().strip()
        if not raw or "pega y da clic" in raw:
            self.lbl_status.config(text="Pega un proxy válido primero (host:port:user:pass).", foreground="#cc0000")
            return
        added = self.proxy_mgr.add_and_select(raw)
        if not added:
            self.lbl_status.config(text="Formato de proxy no reconocido.", foreground="#cc0000")
            return
        self.ent_new_proxy.delete(0, "end")
        self.apply_switch()

    def apply_switch(self):
        cur = self.proxy_mgr.get_current()
        loc = get_proxy_location(cur, self.region_hint) if cur else resolve_direct_mode_location(self.region_hint)
        self.update_display()
        self.lbl_status.config(text=f"Cambiando a {loc.get('city')}... (tu sesión/cookies se conservan)", foreground="#0055aa")
        self.cmd_queue.put(("switch_proxy", (cur, loc)))

    def on_click_reload(self):
        self.cmd_queue.put(("reload", None))
        self.lbl_status.config(text="Pestaña recargada.", foreground="#0055aa")


def browser_worker(proxy_mgr: ProxyManager, cmd_queue: queue.Queue, stop_event: threading.Event,
                    restore_session: bool = False, session_meta: dict | None = None,
                    region_hint: str | None = None, initial_curp: str | None = None):
    browser_bin, browser_name = find_browser_executable()
    cur = proxy_mgr.get_current()
    loc = get_proxy_location(cur, region_hint) if cur else resolve_direct_mode_location(region_hint)

    MOBILE_UA = "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"

    stealth = Stealth(
        navigator_platform_override="Linux armv8l",
        navigator_user_agent_override=MOBILE_UA,
    )

    temp_profile_dir = tempfile.mkdtemp(prefix="stealth_session_")

    try:
        with stealth.use_sync(sync_playwright()) as p:
            device = dict(p.devices["Pixel 7"])
            device["user_agent"] = MOBILE_UA

            def make_context(proxy_obj, loc_obj, storage_path=None):
                launch_args = [
                    "--window-size=460,940",
                    "--window-position=60,40",
                    "--disable-blink-features=AutomationControlled",
                    "--no-default-browser-check",
                    "--no-first-run",
                    "--use-fake-ui-for-media-stream",
                    "--enable-features=Geolocation",
                    "--disable-features=BlockGeolocation",
                ]

                launch_kwargs = {
                    "headless": False,
                    "args": launch_args,
                }
                if browser_bin:
                    launch_kwargs["executable_path"] = browser_bin

                proxy_cfg = None
                if proxy_obj and proxy_obj.get("server"):
                    proxy_cfg = {
                        "server": proxy_obj["server"],
                        "username": proxy_obj.get("username"),
                        "password": proxy_obj.get("password"),
                    }

                if proxy_cfg:
                    launch_kwargs["proxy"] = proxy_cfg

                b = p.chromium.launch(**launch_kwargs)

                ctx_kwargs = {
                    **device,
                    "locale": "es-MX",
                    "timezone_id": loc_obj.get("timezone", "America/Mexico_City"),
                    "geolocation": {"latitude": loc_obj.get("lat", 19.4326), "longitude": loc_obj.get("lon", -99.1332), "accuracy": 15},
                    "permissions": ["geolocation", "camera", "microphone"],
                    "extra_http_headers": {
                        "sec-ch-ua": '"Chrome";v="128", "Not.A)Brand";v="24", "Chromium";v="128"',
                        "sec-ch-ua-mobile": "?1",
                        "sec-ch-ua-platform": '"Android"',
                    },
                }

                if storage_path and os.path.exists(storage_path):
                    ctx_kwargs["storage_state"] = storage_path

                ctx = b.new_context(**ctx_kwargs)

                # Bloqueo de ad-tech de 3ros (Google Ads/remarketing, Facebook Pixel, Bing Ads,
                # Adobe Target) — verificado 2026-09-30 vía network_debug.log de la prueba real
                # Nuevo León (CURP BAVY770723MNLRLL02): cada page_view (confirm-data, contact-data,
                # derivation-pro) dispara 20-40 pixeles de golpe. CERO funcionales para el flujo
                # de onboarding (sin reCAPTCHA de por medio). maps.googleapis.com y dynatrace
                # (1st-party de Santander) NO se tocan: el primero resuelve la geolocation que
                # mandamos, es funcional.
                #
                # DISEÑO (rediseñado 2026-09-30, root-cause de los stalls de ~16s en cada
                # transición de página): un solo ctx.route("**/*", handler) con el filtro hecho
                # en Python intercepta vía CDP Fetch.enable TODA petición del contexto — las
                # 20-40 de ad-tech Y también fuentes/imágenes/scripts propios de Santander —
                # cada una paga un roundtrip síncrono al proceso Python antes de poder seguir.
                # Con 20-40 pixeles simultáneos eso serializa en el único hilo del browser_worker
                # y ahí es donde se va el tiempo (verificado: la ventana de la ráfaga de pixeles
                # en el log, 10:05:39-10:05:55, es exactamente el mismo ~16s que el stall
                # reportado en confirm-data y derivation-pro). Chromium/CDP sí soporta filtrar
                # por patrón ANTES de tocar Python (urlPattern en Fetch.enable) — por eso aquí se
                # registra una ruta por dominio en vez de una sola catch-all: el 1st-party de
                # Santander (y todo lo que no es ad-tech) nunca llega a hacer ese roundtrip.
                AD_TECH_ABORT_PATTERNS = (
                    "**doubleclick.net/**",
                    "**googleadservices.com/**",
                    "**googlesyndication.com/**",
                    "**www.facebook.com/**",
                    "**connect.facebook.net/**",
                    "**bat.bing.com/**",
                    "**tt.omtrdc.net/**",
                    "**analytics.google.com/**",
                    "**adservice.google.com/**",
                    "**www.google.com/pagead/**",
                    "**www.google.com/rmkt/**",
                    "**www.google.com/ccm/**",  # visto en el log: no estaba en el blocklist viejo
                )

                def _abort_route(route):
                    try:
                        route.abort()
                    except Exception:
                        pass

                for _pattern in AD_TECH_ABORT_PATTERNS:
                    try:
                        ctx.route(_pattern, _abort_route)
                    except Exception:
                        pass

                def _on_request(req):
                    if "santander" not in req.url:
                        return
                    try:
                        post = req.post_data
                        if post and len(post) > 600:
                            post = post[:600] + "...(truncado)"
                        _log_network_event(f"[REQ] {req.method} {req.url} | body={post}")
                    except Exception:
                        pass

                def _on_response(res):
                    if "santander" not in res.url:
                        return
                    try:
                        _log_network_event(f"[RES] {res.status} {res.url}")
                    except Exception:
                        pass

                ctx.on("request", _on_request)
                ctx.on("response", _on_response)

                target_origins = [
                    "https://santander.com.mx",
                    "https://www.santander.com.mx",
                    "https://onboarding.santander.com.mx",
                    "https://api.fad.santander.com.mx",
                    "https://fad.santander.com.mx",
                    "https://enlace.santander.com.mx",
                ]
                for orig in target_origins:
                    try:
                        ctx.grant_permissions(["geolocation", "camera", "microphone"], origin=orig)
                    except Exception:
                        pass

                # Neutralizador de bugs Santander FAD (CSP Bypass) — verificado 2026-09-30: SIN esto,
                # Chromium tira net::ERR_RESPONSE_HEADERS_TRUNCATED contra este dominio.
                def handle_route(route):
                    # El CSP-bypass (fetch manual + fulfill) solo hace falta para el documento
                    # principal y llamadas XHR/fetch — ahí es donde Santander manda el header CSP
                    # que truena Chromium (net::ERR_RESPONSE_HEADERS_TRUNCATED, verificado
                    # 2026-09-30). Para assets estáticos (JS/CSS/fuentes/imágenes) el roundtrip
                    # manual solo agrega latencia sin necesidad — se dejan pasar directo.
                    if route.request.resource_type not in ("document", "xhr", "fetch"):
                        try:
                            route.continue_()
                        except Exception:
                            pass
                        return
                    try:
                        response = route.fetch()
                        headers = dict(response.headers)
                        headers.pop("content-security-policy", None)
                        headers.pop("content-security-policy-report-only", None)
                        headers["access-control-allow-origin"] = "*"
                        route.fulfill(response=response, headers=headers)
                    except Exception:
                        try:
                            route.continue_()
                        except Exception:
                            pass

                try:
                    ctx.route("**/santander_fad/**", handle_route)
                    ctx.route("**/cuenta-digital-lite/**", handle_route)
                except Exception:
                    pass

                return b, ctx

            init_storage = SESSION_STORAGE_STATE if (restore_session and os.path.exists(SESSION_STORAGE_STATE)) else None
            browser, context = make_context(cur, loc, init_storage)

            def save_state(current_ctx, current_b):
                try:
                    if not current_b.is_connected() or not current_ctx.pages:
                        return
                    try:
                        current_ctx.storage_state(path=SESSION_STORAGE_STATE)
                    except Exception:
                        pass

                    active_urls = [pg.url for pg in current_ctx.pages if pg.url and not pg.url.startswith("about:")]
                    last_working_url = active_urls[-1] if active_urls else URL_START
                    cur_p = proxy_mgr.get_current()
                    meta = {
                        "timestamp": time.time(),
                        "time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "urls": [last_working_url],
                        "last_url": last_working_url,
                        "proxy": cur_p.get("raw", "") if cur_p else "",
                        "proxy_idx": proxy_mgr.current_idx,
                        "proxies": [p.get("raw", "") for p in proxy_mgr.proxies],
                    }
                    with open(SESSION_META_FILE, "w", encoding="utf-8") as f:
                        json.dump(meta, f, indent=2)
                except Exception:
                    pass

            target_url = URL_START
            if restore_session and session_meta and session_meta.get("last_url"):
                saved_u = session_meta.get("last_url")
                if saved_u and saved_u.startswith("http"):
                    target_url = saved_u

            page = context.new_page()
            try:
                page.goto(target_url, timeout=45000)
                if initial_curp:
                    try:
                        inp = page.locator("#onb-page-main-personal-identifier")
                        if inp.count() > 0:
                            inp.fill(initial_curp)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[!] Aviso al cargar: {e}", flush=True)

            save_state(context, browser)

            last_save = time.time()
            while not stop_event.is_set() and browser.is_connected():
                if len(context.pages) == 0:
                    time.sleep(0.5)
                    if len(context.pages) == 0:
                        break

                if time.time() - last_save > 15.0:
                    save_state(context, browser)
                    last_save = time.time()

                try:
                    cmd, data = cmd_queue.get(timeout=0.3)
                    if cmd == "switch_proxy":
                        new_proxy, new_loc = data
                        save_state(context, browser)

                        current_url = page.url if page and not page.is_closed() else URL_START

                        try:
                            context.close()
                            browser.close()
                        except Exception:
                            pass

                        browser, context = make_context(new_proxy, new_loc, SESSION_STORAGE_STATE)
                        page = context.new_page()
                        try:
                            page.goto(current_url, timeout=45000)
                        except Exception:
                            pass
                        save_state(context, browser)

                    elif cmd == "reload":
                        if page and not page.is_closed():
                            try:
                                page.reload(timeout=30000)
                            except Exception:
                                pass
                    elif cmd == "save_session":
                        save_state(context, browser)
                    elif cmd == "stop":
                        break
                except queue.Empty:
                    pass

            try:
                save_state(context, browser)
                browser.close()
            except Exception:
                pass

    except Exception as e:
        print(f"\n[!] Error en worker: {e}", flush=True)
    finally:
        stop_event.set()
        if os.path.exists(temp_profile_dir):
            shutil.rmtree(temp_profile_dir, ignore_errors=True)


def _parse_cli_args() -> dict:
    """Acepta dos formas de invocacion:
    1) Flags sueltas: --curp=XXX --estado=JALISCO --operator-estado=Jalisco
    2) Un solo argumento con el protocolo custom registrado en Windows:
       santabase-stealth://open?curp=XXX&estado=JALISCO
       (asi es como Windows invoca el handler cuando se hace clic en el link desde la boveda web)
    """
    args = {"curp": None, "estado": None, "operator_estado": None}
    for a in sys.argv[1:]:
        a = a.strip().strip('"')
        if a.lower().startswith("santabase-stealth:"):
            try:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(a)
                qs = parse_qs(parsed.query)
                if "curp" in qs and qs["curp"]:
                    args["curp"] = qs["curp"][0].strip()
                if "estado" in qs and qs["estado"]:
                    args["estado"] = qs["estado"][0].strip()
                if "operator_estado" in qs and qs["operator_estado"]:
                    args["operator_estado"] = qs["operator_estado"][0].strip()
            except Exception:
                pass  # URI mal formado: no truena, simplemente arranca sin pre-llenar nada
        elif a.startswith("--curp="):
            args["curp"] = a.split("=", 1)[1].strip()
        elif a.startswith("--estado="):
            args["estado"] = a.split("=", 1)[1].strip()
        elif a.startswith("--operator-estado="):
            args["operator_estado"] = a.split("=", 1)[1].strip()
    return args


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    cli = _parse_cli_args()
    op_cfg = load_operator_config()
    operator_estado = cli["operator_estado"] or os.environ.get("SANTABASE_OPERATOR_ESTADO") or op_cfg.get("estado")

    cfg = show_startup_dialog(DEFAULT_PROXIES, region_hint=cli["estado"], operator_estado=operator_estado, initial_curp=cli["curp"])
    if cfg.get("cancelled"):
        sys.exit(0)

    direct_mode = not cfg.get("use_proxy", True)
    proxy_list = cfg.get("proxies", DEFAULT_PROXIES)
    restore_session = cfg.get("restore_session", False)
    session_meta = cfg.get("session_meta")
    region_hint = cfg.get("region_hint")
    initial_curp = cfg.get("curp")

    if not restore_session:
        if os.path.exists(SESSION_STORAGE_STATE):
            try:
                os.remove(SESSION_STORAGE_STATE)
            except Exception:
                pass
        if os.path.exists(SESSION_META_FILE):
            try:
                os.remove(SESSION_META_FILE)
            except Exception:
                pass

    proxy_mgr = ProxyManager(proxy_list, direct_mode=direct_mode)
    cmd_queue = queue.Queue()
    stop_event = threading.Event()

    worker_t = threading.Thread(
        target=browser_worker,
        args=(proxy_mgr, cmd_queue, stop_event, restore_session, session_meta, region_hint, initial_curp),
        daemon=True
    )
    worker_t.start()

    root = tk.Tk()
    switcher = ProxySwitcherWidget(root, proxy_mgr, cmd_queue, region_hint=region_hint)

    def poll():
        if stop_event.is_set():
            root.destroy()
        else:
            root.after(500, poll)

    def on_close():
        cmd_queue.put(("stop", None))
        stop_event.set()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(500, poll)
    root.mainloop()


if __name__ == "__main__":
    main()
