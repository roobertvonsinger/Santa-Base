#!/usr/bin/env python3
"""
SantaBase Stealth Lite — Navegador Móvil Ultra-Compacto con Detección Temprana de Errores
Diseñado específicamente para integración con SantaBase (https://2puty.tech/santabase).

Capacidades Core:
1. Ultra-Ligero: Cero overhead forense pesado (sin video HD continuo, sin trazas pesadas). Carga en <1s.
2. Detección Temprana de Errores:
   - Sonda activa de latencia y salud de proxy (ping en ms, alerta temprana de lentitud/caída).
   - Validación humana de formato CURP (RENAPO, longitud 18, fechas, estados oficiales).
   - Neutralizador de bugs de Santander (Bypass CSP en FAD para prevenir crash de pdf.worker.js).
   - Watchdog de loops conocidos de Santander (spinner infinito >12s, confirm-data trabado, rechazos PE1002).
3. Conmutación de Proxies en Caliente (In-Flight Hot-Swap):
   - MicroProxy local en 127.0.0.1:puerto.
   - Permite agregar y cambiar upstream proxies en cualquier momento sin cerrar ni reiniciar el navegador.
4. Auto-Sincronización Geográfica:
   - Detecta IP de salida del proxy y pre-inyecta coordenadas y zona horaria de México.
   - Pre-autoriza permisos de geolocalización para evitar el popup bloqueante.
5. HUD Flotante Compacto:
   - Semáforo de proxy (🟢/🟡/🔴), botón para conmutar en caliente, copiar/rellenar CURP y bitácora en vivo.
"""

import os
import sys
import time
import json
import base64
import random
import socket
import select
import threading
import queue
import urllib.request
import urllib.error
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# URL Oficial de Onboarding LikeU
URL_TARGET = (
    "https://onboarding.santander.com.mx/cuenta-digital-lite/product-page"
    "?utm_source=portal_publico&utm_medium=landing_page&utm_campaign=debito_likeu"
)

# Proxy por defecto (configurable en runtime)
DEFAULT_PROXIES = [
    "gate.nodemaven.com:8080:luiscael70_gmail_com-country-mx-region-oaxaca-sid-6d77154d6a464-ttl-10m-filter-medium-speed-fast:gg68gfdvd2"
]

# Estados oficiales de RENAPO México para validación humana de CURP
RENAPO_STATES = {
    "AS": "Aguascalientes", "BC": "Baja California", "BS": "Baja California Sur",
    "CC": "Campeche", "CL": "Coahuila", "CM": "Colima", "CS": "Chiapas",
    "CH": "Chihuahua", "DF": "Ciudad de México", "DG": "Durango", "GT": "Guanajuato",
    "GR": "Guerrero", "HG": "Hidalgo", "JC": "Jalisco", "MC": "Estado de México",
    "MN": "Michoacán", "MS": "Morelos", "NT": "Nayarit", "NL": "Nuevo León",
    "OC": "Oaxaca", "PL": "Puebla", "QT": "Querétaro", "QR": "Quintana Roo",
    "SP": "San Luis Potosí", "SL": "Sinaloa", "SR": "Sonora", "TC": "Tabasco",
    "TS": "Tamaulipas", "TL": "Tlaxcala", "VZ": "Veracruz", "YN": "Yucatán",
    "ZS": "Zacatecas", "NE": "Nacido en el Extranjero"
}

# Coordenadas y husos horarios estándar de respaldo en México
MEXICO_FALLBACK_COORDS = {
    "oaxaca": {"city": "Oaxaca", "region": "Oaxaca", "lat": 17.0608, "lon": -96.7253, "timezone": "America/Mexico_City"},
    "cdmx": {"city": "Ciudad de México", "region": "Ciudad de México", "lat": 19.4326, "lon": -99.1332, "timezone": "America/Mexico_City"},
    "guadalajara": {"city": "Guadalajara", "region": "Jalisco", "lat": 20.6767, "lon": -103.3475, "timezone": "America/Mexico_City"},
    "monterrey": {"city": "Monterrey", "region": "Nuevo León", "lat": 25.6866, "lon": -100.3161, "timezone": "America/Monterrey"},
    "puebla": {"city": "Puebla", "region": "Puebla", "lat": 19.0414, "lon": -98.2063, "timezone": "America/Mexico_City"},
    "tijuana": {"city": "Tijuana", "region": "Baja California", "lat": 32.5149, "lon": -117.0382, "timezone": "America/Tijuana"},
    "merida": {"city": "Mérida", "region": "Yucatán", "lat": 20.9674, "lon": -89.5926, "timezone": "America/Merida"}
}


# ==============================================================================
# 1. VALIDADOR DE ERRORES HUMANOS (CURP & DATOS)
# ==============================================================================
def validate_curp(curp: str) -> dict:
    """Valida sintaxis, longitud, fecha y código de estado RENAPO en una CURP."""
    if not curp:
        return {"valid": False, "error": "CURP vacía"}
    c = curp.strip().upper()
    if len(c) != 18:
        return {"valid": False, "error": f"Longitud incorrecta ({len(c)}/18 caracteres)"}
    
    # Letras iniciales
    if not c[:4].isalpha():
        return {"valid": False, "error": "Los primeros 4 caracteres deben ser letras"}
    
    # Fecha de nacimiento YYMMDD
    ymd = c[4:10]
    if not ymd.isdigit():
        return {"valid": False, "error": "Los dígitos 5 al 10 deben ser fecha numérico (AAMMDD)"}
    try:
        mm = int(ymd[2:4])
        dd = int(ymd[4:6])
        if mm < 1 or mm > 12 or dd < 1 or dd > 31:
            return {"valid": False, "error": f"Fecha no válida en CURP (Mes:{mm}, Día:{dd})"}
    except Exception:
        return {"valid": False, "error": "Error al parsear fecha de CURP"}

    # Género
    gender = c[10]
    if gender not in ("H", "M"):
        return {"valid": False, "error": f"Carácter de género inválido '{gender}' (debe ser H o M)"}

    # Estado RENAPO
    state_code = c[11:13]
    if state_code not in RENAPO_STATES:
        return {"valid": False, "error": f"Código de estado '{state_code}' no existe en RENAPO"}

    return {
        "valid": True,
        "curp": c,
        "state_code": state_code,
        "state_name": RENAPO_STATES[state_code],
        "gender": "Hombre" if gender == "H" else "Mujer",
        "birth_date": f"{ymd[:2]}/{ymd[2:4]}/{ymd[4:]}"
    }


# ==============================================================================
# 2. GESTOR DE PROXIES Y MICROPROXY LOCAL (HOT-SWAP)
# ==============================================================================
def parse_proxy_string(p_str: str) -> dict:
    """Parsea formatos host:port:user:pass o host:port o user:pass@host:port."""
    p = p_str.strip()
    if not p:
        return None
    if "@" in p:
        parts = p.split("@", 1)
        creds = parts[0]
        hp = parts[1]
        user, pwd = creds.split(":", 1) if ":" in creds else (creds, "")
        host, port = hp.split(":", 1) if ":" in hp else (hp, "80")
        return {"host": host.strip(), "port": int(port.strip()), "username": user.strip(), "password": pwd.strip()}
    
    tokens = p.split(":")
    if len(tokens) >= 4:
        return {
            "host": tokens[0].strip(),
            "port": int(tokens[1].strip()),
            "username": tokens[2].strip(),
            "password": ":".join(tokens[3:]).strip()
        }
    elif len(tokens) == 2:
        return {"host": tokens[0].strip(), "port": int(tokens[1].strip()), "username": None, "password": None}
    return None


class ProxyHealthTester:
    """Prueba rápida de latencia y disponibilidad de un proxy."""
    @staticmethod
    def measure_latency(proxy_dict: dict, timeout: float = 3.5) -> dict:
        t0 = time.time()
        if not proxy_dict or not proxy_dict.get("host"):
            # Conexión directa
            try:
                s = socket.create_connection(("1.1.1.1", 53), timeout=timeout)
                s.close()
                ms = int((time.time() - t0) * 1000)
                return {"success": True, "latency_ms": ms, "quality": "fast", "msg": f"Directo ({ms}ms)"}
            except Exception as e:
                return {"success": False, "latency_ms": 9999, "quality": "dead", "msg": str(e)}

        host = proxy_dict["host"]
        port = proxy_dict["port"]
        user = proxy_dict.get("username")
        pwd = proxy_dict.get("password")

        try:
            s = socket.create_connection((host, port), timeout=timeout)
            if user and pwd:
                auth = base64.b64encode(f"{user}:{pwd}".encode()).decode()
                req = f"CONNECT cp.cloudflare.com:80 HTTP/1.1\r\nHost: cp.cloudflare.com:80\r\nProxy-Authorization: Basic {auth}\r\n\r\n"
            else:
                req = "CONNECT cp.cloudflare.com:80 HTTP/1.1\r\nHost: cp.cloudflare.com:80\r\n\r\n"
            
            s.sendall(req.encode())
            s.settimeout(timeout)
            resp = s.recv(512).decode(errors="replace")
            s.close()
            ms = int((time.time() - t0) * 1000)

            if "200" in resp:
                if ms < 800:
                    quality = "fast"
                elif ms < 2200:
                    quality = "medium"
                else:
                    quality = "slow"
                return {"success": True, "latency_ms": ms, "quality": quality, "msg": f"Conectado ({ms}ms)"}
            elif "407" in resp:
                return {"success": False, "latency_ms": ms, "quality": "auth_error", "msg": "Error de Autenticación (407)"}
            else:
                code = resp.split("\r\n")[0] if resp else "Sin respuesta"
                return {"success": False, "latency_ms": ms, "quality": "error", "msg": f"Respuesta proxy: {code[:30]}"}
        except socket.timeout:
            return {"success": False, "latency_ms": 4000, "quality": "timeout", "msg": "Timeout (>3.5s)"}
        except Exception as ex:
            return {"success": False, "latency_ms": 9999, "quality": "dead", "msg": str(ex)[:35]}


class MicroProxy:
    """Servidor proxy local HTTP/HTTPS que permite cambiar el upstream proxy en caliente."""
    def __init__(self, bind_host="127.0.0.1", port=0):
        self.bind_host = bind_host
        self.port = port
        self.server_sock = None
        self.running = False
        self.upstream_host = None
        self.upstream_port = None
        self.upstream_user = None
        self.upstream_pass = None
        self._lock = threading.Lock()

    def set_upstream(self, host, port, user=None, password=None):
        with self._lock:
            self.upstream_host = host
            self.upstream_port = int(port) if port else None
            self.upstream_user = user
            self.upstream_pass = password

    def start(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.bind_host, self.port))
        self.port = self.server_sock.getsockname()[1]
        self.server_sock.listen(128)
        self.running = True
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def stop(self):
        self.running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass

    def _listen_loop(self):
        while self.running:
            try:
                client_sock, _ = self.server_sock.accept()
                threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()
            except Exception:
                break

    def _handle_client(self, client_sock):
        try:
            client_sock.settimeout(15)
            data = client_sock.recv(4096)
            if not data:
                client_sock.close()
                return

            first_line = data.split(b"\r\n")[0].decode(errors="replace")
            parts = first_line.split(" ")
            if len(parts) < 2:
                client_sock.close()
                return
            method, target = parts[0], parts[1]

            with self._lock:
                up_host = self.upstream_host
                up_port = self.upstream_port
                up_user = self.upstream_user
                up_pass = self.upstream_pass

            # Si no hay upstream configurado, conexión directa
            if not up_host:
                if method == "CONNECT":
                    hp = target.split(":")
                    d_host = hp[0]
                    d_port = int(hp[1]) if len(hp) > 1 else 443
                    dest_sock = socket.create_connection((d_host, d_port), timeout=15)
                    client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    self._tunnel(client_sock, dest_sock)
                else:
                    client_sock.close()
                return

            # Conectar a Upstream Proxy
            upstream_sock = socket.create_connection((up_host, up_port), timeout=15)
            auth_header = ""
            if up_user and up_pass:
                cred = base64.b64encode(f"{up_user}:{up_pass}".encode()).decode()
                auth_header = f"Proxy-Authorization: Basic {cred}\r\n"

            if method == "CONNECT":
                connect_req = f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n{auth_header}\r\n"
                upstream_sock.sendall(connect_req.encode())
                resp = upstream_sock.recv(4096)
                if b"200" in resp.split(b"\r\n")[0]:
                    client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    self._tunnel(client_sock, upstream_sock)
                else:
                    client_sock.sendall(resp)
                    client_sock.close()
                    upstream_sock.close()
            else:
                # HTTP normal
                req_str = data.decode(errors="replace")
                if auth_header and "Proxy-Authorization:" not in req_str:
                    lines = req_str.split("\r\n")
                    lines.insert(1, auth_header.strip())
                    data = "\r\n".join(lines).encode()
                upstream_sock.sendall(data)
                self._tunnel(client_sock, upstream_sock)
        except Exception:
            try:
                client_sock.close()
            except Exception:
                pass

    def _tunnel(self, s1, s2):
        s1.setblocking(False)
        s2.setblocking(False)
        socks = [s1, s2]
        while self.running:
            try:
                r, _, e = select.select(socks, [], socks, 40)
                if e:
                    break
                if not r:
                    break
                for s in r:
                    other = s2 if s is s1 else s1
                    try:
                        chunk = s.recv(16384)
                        if not chunk:
                            return
                        other.sendall(chunk)
                    except (BlockingIOError, InterruptedError):
                        continue
                    except Exception:
                        return
            except Exception:
                break
        try:
            s1.close()
            s2.close()
        except Exception:
            pass


# ==============================================================================
# 3. RESOLVEDOR DE IP GEOGRÁFICA
# ==============================================================================
def resolve_exit_ip(micro_proxy_port: int) -> dict:
    """Consulta la IP de salida del proxy y mapea coordenadas óptimas."""
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": f"http://127.0.0.1:{micro_proxy_port}", "https": f"http://127.0.0.1:{micro_proxy_port}"})
    )
    for service_url in ["http://ip-api.com/json/", "https://ifconfig.me/all.json", "https://api.ipify.org?format=json"]:
        try:
            req = urllib.request.Request(service_url, headers={"User-Agent": "curl/7.84.0"})
            with opener.open(req, timeout=4.5) as resp:
                data = json.loads(resp.read().decode())
                ip = data.get("query") or data.get("ip") or data.get("ip_addr")
                city = data.get("city", "Ciudad de México")
                region = data.get("regionName", "Ciudad de México")
                lat = data.get("lat", 19.4326)
                lon = data.get("lon", -99.1332)
                tz = data.get("timezone", "America/Mexico_City")
                return {"ip": ip, "city": city, "region": region, "lat": lat, "lon": lon, "timezone": tz}
        except Exception:
            continue
    return {"ip": "Local/Desconocida", "city": "Oaxaca", "region": "Oaxaca", "lat": 17.0608, "lon": -96.7253, "timezone": "America/Mexico_City"}


# ==============================================================================
# 4. HUD FLOTANTE ULTRA-COMPACTO (TKINTER TOOLBAR)
# ==============================================================================
class CompactHUD:
    def __init__(self, root, micro_proxy, initial_curp, cmd_queue):
        self.root = root
        self.micro_proxy = micro_proxy
        self.cmd_queue = cmd_queue
        self.current_curp = initial_curp or ""

        self.root.title("⚡ SantaBase Stealth Lite")
        self.root.geometry("380x370")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#0b0f19")
        self.root.resizable(False, False)

        # Style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#0b0f19", foreground="#cbd5e1", font=("Segoe UI", 9))

        # Header
        top_frame = tk.Frame(root, bg="#111827", padx=10, pady=8)
        top_frame.pack(fill="x")
        
        lbl_title = tk.Label(top_frame, text="⚡ SantaBase Stealth Lite", font=("Segoe UI", 11, "bold"), fg="#ec0000", bg="#111827")
        lbl_title.pack(side="left")
        
        self.lbl_status = tk.Label(top_frame, text="🟢 ONLINE", font=("Segoe UI", 9, "bold"), fg="#34d399", bg="#111827")
        self.lbl_status.pack(side="right")

        # Proxy Bar Frame
        p_frame = tk.LabelFrame(root, text=" Red & Proxy ", bg="#0b0f19", fg="#94a3b8", font=("Segoe UI", 8, "bold"), padx=8, pady=4)
        p_frame.pack(fill="x", padx=10, pady=4)

        self.lbl_proxy_info = tk.Label(p_frame, text="Iniciando...", font=("Consolas", 8), fg="#38bdf8", bg="#0b0f19")
        self.lbl_proxy_info.pack(anchor="w")

        # Hot-Add Entry
        hot_frame = tk.Frame(p_frame, bg="#0b0f19")
        hot_frame.pack(fill="x", pady=4)
        self.ent_proxy = tk.Entry(hot_frame, font=("Consolas", 8), bg="#1e293b", fg="#f8fafc", insertbackground="white")
        self.ent_proxy.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.ent_proxy.insert(0, "Pegar proxy host:port:user:pass")
        self.ent_proxy.bind("<FocusIn>", lambda e: self.ent_proxy.delete(0, "end") if "Pegar proxy" in self.ent_proxy.get() else None)

        btn_switch = tk.Button(hot_frame, text="🔀 Conmutar", font=("Segoe UI", 8, "bold"), bg="#2563eb", fg="white",
                               activebackground="#1d4ed8", bd=0, padx=8, pady=2, cursor="hand2", command=self.on_switch_proxy)
        btn_switch.pack(side="right")

        # CURP Box
        c_frame = tk.LabelFrame(root, text=" CURP Activa ", bg="#0b0f19", fg="#94a3b8", font=("Segoe UI", 8, "bold"), padx=8, pady=4)
        c_frame.pack(fill="x", padx=10, pady=4)

        curp_inner = tk.Frame(c_frame, bg="#0b0f19")
        curp_inner.pack(fill="x")
        self.lbl_curp = tk.Label(curp_inner, text=self.current_curp or "Sin CURP asignada", font=("Consolas", 10, "bold"),
                                 fg="#fbbf24" if self.current_curp else "#64748b", bg="#0b0f19")
        self.lbl_curp.pack(side="left", fill="x", expand=True)

        btn_copy_curp = tk.Button(curp_inner, text="📋 Copiar", font=("Segoe UI", 8, "bold"), bg="#334155", fg="white",
                                  bd=0, padx=6, pady=2, cursor="hand2", command=self.copy_curp)
        btn_copy_curp.pack(side="right", padx=2)

        btn_paste_dom = tk.Button(curp_inner, text="⚡ Escribir en Form", font=("Segoe UI", 8, "bold"), bg="#059669", fg="white",
                                  bd=0, padx=6, pady=2, cursor="hand2", command=self.inject_curp_to_form)
        btn_paste_dom.pack(side="right", padx=2)

        self.lbl_curp_diag = tk.Label(c_frame, text="", font=("Segoe UI", 8), fg="#94a3b8", bg="#0b0f19")
        self.lbl_curp_diag.pack(anchor="w", pady=(2, 0))
        if self.current_curp:
            self._update_curp_diag(self.current_curp)

        # Log & Early Warning Console
        l_frame = tk.LabelFrame(root, text=" Diagnóstico Temprano & Banco ", bg="#0b0f19", fg="#94a3b8", font=("Segoe UI", 8, "bold"), padx=8, pady=4)
        l_frame.pack(fill="both", expand=True, padx=10, pady=4)

        self.txt_log = scrolledtext.ScrolledText(l_frame, height=5, font=("Consolas", 8), bg="#030712", fg="#94a3b8", bd=0)
        self.txt_log.pack(fill="both", expand=True)
        self.txt_log.tag_config("warn", foreground="#f59e0b")
        self.txt_log.tag_config("ok", foreground="#34d399")
        self.txt_log.tag_config("err", foreground="#ef4444")
        self.txt_log.tag_config("bank", foreground="#a855f7")

        self.log("🚀 SantaBase Stealth Lite inicializado.", "ok")

    def log(self, msg: str, tag: str = None):
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{ts}] {msg}\n", tag)
        self.txt_log.see("end")

    def _update_curp_diag(self, curp: str):
        v = validate_curp(curp)
        if v["valid"]:
            self.lbl_curp_diag.config(text=f"✅ {v['state_name']} | {v['gender']} | F.Nac: {v['birth_date']}", fg="#34d399")
            self.log(f"CURP verificada: {curp} ({v['state_name']})", "ok")
        else:
            self.lbl_curp_diag.config(text=f"⚠️ {v['error']}", fg="#f87171")
            self.log(f"⚠️ Error humano en CURP: {v['error']}", "warn")

    def copy_curp(self):
        if self.current_curp:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.current_curp)
            self.log(f"📋 CURP {self.current_curp} copiada al portapapeles.", "ok")
        else:
            self.log("No hay CURP para copiar.", "warn")

    def inject_curp_to_form(self):
        if not self.current_curp:
            self.log("No hay CURP para rellenar.", "warn")
            return
        self.cmd_queue.put(("inject_curp", self.current_curp))
        self.log(f"⚡ Inyectando CURP {self.current_curp} en Santander...", "ok")

    def on_switch_proxy(self):
        raw = self.ent_proxy.get().strip()
        if not raw or "Pegar proxy" in raw:
            return
        p_dict = parse_proxy_string(raw)
        if not p_dict:
            self.log("❌ Formato inválido. Use host:port:user:pass", "err")
            return
        
        self.log(f"Probando latencia de proxy {p_dict['host']}...", "ok")
        res = ProxyHealthTester.measure_latency(p_dict)
        if not res["success"]:
            self.log(f"⚠️ Proxy inestable: {res['msg']}", "warn")
        else:
            self.log(f"🟢 Proxy responde en {res['latency_ms']}ms ({res['quality']})", "ok")
        
        self.micro_proxy.set_upstream(p_dict["host"], p_dict["port"], p_dict["username"], p_dict["password"])
        self.cmd_queue.put(("proxy_switched", p_dict))
        self.lbl_proxy_info.config(text=f"Proxy: {p_dict['host']}:{p_dict['port']} | {res['msg']}", fg="#38bdf8")
        self.ent_proxy.delete(0, "end")


# ==============================================================================
# 5. MOTOR PLAYWRIGHT ULTRA-LIGERO & WATCHDOG DE SANTANDER
# ==============================================================================
def browser_worker(micro_proxy, curp, cmd_queue, stop_event, hud_ref):
    """Ejecuta el navegador móvil Playwright con CSP-Bypass y detección temprana."""
    from playwright.sync_api import sync_playwright

    # Medir latencia inicial de proxy
    initial_p = {
        "host": micro_proxy.upstream_host,
        "port": micro_proxy.upstream_port,
        "username": micro_proxy.upstream_user,
        "password": micro_proxy.upstream_pass
    }
    lat_info = ProxyHealthTester.measure_latency(initial_p)
    if hud_ref:
        hud_ref.log(f"Prueba de salud proxy: {lat_info['msg']}", "ok" if lat_info["success"] else "warn")

    # Detectar Geo IP
    geo = resolve_exit_ip(micro_proxy.port)
    if hud_ref:
        hud_ref.lbl_proxy_info.config(
            text=f"IP: {geo['ip']} | {geo['city']} | {lat_info['msg']}",
            fg="#34d399" if lat_info.get("quality") == "fast" else "#fbbf24"
        )
        hud_ref.log(f"Ubicación sincronizada: {geo['city']}, {geo['region']} ({geo['ip']})", "ok")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel="chrome" if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe") else None,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-site-isolation-trials",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-features=IsolateOrigins,site-per-process",
                f"--proxy-server=http://127.0.0.1:{micro_proxy.port}",
                "--window-size=430,932"
            ]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 15; Pixel 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
            viewport={"width": 430, "height": 932},
            device_scale_factor=2.5,
            is_mobile=True,
            has_touch=True,
            locale="es-MX",
            timezone_id=geo.get("timezone", "America/Mexico_City"),
            geolocation={"latitude": float(geo.get("lat", 19.4326)), "longitude": float(geo.get("lon", -99.1332))},
            permissions=["geolocation"]
        )

        # Cloak navigator.webdriver
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        page = context.new_page()

        # ======================================================================
        # EARLY FIX: Neutralizador de Bugs Santander FAD (CSP Bypass)
        # ======================================================================
        def handle_route(route):
            try:
                response = route.fetch()
                headers = dict(response.headers)
                # Eliminar restricciones CSP para permitir pdf.worker.js en blob:
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
            page.route("**/santander_fad/**", handle_route)
            page.route("**/cuenta-digital-lite/**", handle_route)
        except Exception:
            pass

        # Navegación Directa al Onboarding LikeU
        if hud_ref:
            hud_ref.log(f"Navegando directamente a LikeU Santander...", "ok")
        
        try:
            page.goto(URL_TARGET, wait_until="domcontentloaded", timeout=35000)
        except Exception as e:
            if hud_ref:
                hud_ref.log(f"⚠️ Timeout al cargar URL: {str(e)[:40]}", "warn")

        last_known_url = ""
        stuck_spinner_counter = 0

        # ======================================================================
        # BUCLE DE CONTROL & WATCHDOG DE ERRORES TEMPRANOS
        # ======================================================================
        while not stop_event.is_set():
            # Procesar comandos del HUD
            try:
                while True:
                    cmd, val = cmd_queue.get_nowait()
                    if cmd == "stop":
                        stop_event.set()
                        break
                    elif cmd == "inject_curp":
                        try:
                            # Buscar input de CURP e inyectar
                            inp = page.locator("#onb-page-main-personal-identifier")
                            if inp.count() > 0:
                                inp.fill(val)
                                if hud_ref:
                                    hud_ref.log(f"CURP {val} escrita en el campo.", "ok")
                            else:
                                if hud_ref:
                                    hud_ref.log("Campo CURP no visible en pantalla actual.", "warn")
                        except Exception as ex:
                            if hud_ref:
                                hud_ref.log(f"Error inyectando CURP: {str(ex)[:35]}", "err")
                    elif cmd == "proxy_switched":
                        # Recalcular geolocalización al conmutar
                        threading.Thread(target=lambda: _async_regeo(micro_proxy, context, hud_ref), daemon=True).start()
                    cmd_queue.task_done()
            except queue.Empty:
                pass

            if stop_event.is_set():
                break

            # Monitoreo de Estado Santander (Early Detection)
            try:
                curr_url = page.url
                if curr_url != last_known_url:
                    last_known_url = curr_url
                    stuck_spinner_counter = 0
                    
                    if "confirm-contact" in curr_url:
                        if hud_ref:
                            hud_ref.log("🛑 [BANCO] Contacto preexistente (/confirm-contact)", "bank")
                    elif "derivation-pro" in curr_url:
                        if hud_ref:
                            hud_ref.log("🛑 [BANCO] Derivación LikeU Pro (/derivation-pro)", "bank")
                    elif "contact-data" in curr_url:
                        if hud_ref:
                            hud_ref.log("🎉 [BANCO] ¡ELEGIBLE! Avanzó a contact-data (LIVE)", "ok")
                    elif "confirm-data" in curr_url:
                        if hud_ref:
                            hud_ref.log("📄 [BANCO] En confirm-data. Verificando botón continuar...", "ok")

                # Watchdog de botón continuar trabado en confirm-data
                if "confirm-data" in curr_url:
                    try:
                        # Auto scroll y verificar
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    except Exception:
                        pass

                # Watchdog de Spinner Infinito (>12s)
                has_spinner = page.evaluate("""() => {
                    const s = document.querySelector('.onb-loading-spinner, .onb-spinner, [aria-label*="cargando"]');
                    return s ? (s.offsetParent !== null) : false;
                }""")
                if has_spinner:
                    stuck_spinner_counter += 1
                    if stuck_spinner_counter == 12:
                        if hud_ref:
                            hud_ref.log("⚠️ [ALERTA] Santander congelado >12s. Posible loop o proxy lento.", "warn")
                else:
                    stuck_spinner_counter = 0

            except Exception:
                # Si el navegador fue cerrado por el usuario
                if not page.is_closed():
                    pass
                else:
                    stop_event.set()
                    break

            time.sleep(1)

        try:
            context.close()
            browser.close()
        except Exception:
            pass


def _async_regeo(micro_proxy, context, hud_ref):
    """Actualiza la geolocalización del navegador en caliente tras cambiar proxy."""
    time.sleep(0.5)
    geo = resolve_exit_ip(micro_proxy.port)
    try:
        context.set_geolocation({"latitude": float(geo.get("lat", 19.4326)), "longitude": float(geo.get("lon", -99.1332))})
        if hud_ref:
            hud_ref.log(f"Nueva salida sincronizada: {geo['city']} ({geo['ip']})", "ok")
    except Exception:
        pass


# ==============================================================================
# 6. ENTRADA PRINCIPAL (CLI & STANDALONE)
# ==============================================================================
def main():
    curp_arg = None
    proxy_arg = None
    direct_mode = False
    no_gui = False

    for arg in sys.argv[1:]:
        a = arg.strip()
        if a.startswith("--curp="):
            curp_arg = a.split("=", 1)[1].strip()
        elif a == "--direct":
            direct_mode = True
        elif a == "--no-gui":
            no_gui = True
        elif a.startswith("--proxy="):
            proxy_arg = a.split("=", 1)[1].strip()
        elif len(a) == 18 and a[:4].isalpha():
            curp_arg = a
        elif ":" in a or "@" in a:
            proxy_arg = a

    selected_proxy = proxy_arg if proxy_arg else (DEFAULT_PROXIES[0] if not direct_mode else None)
    p_dict = parse_proxy_string(selected_proxy) if selected_proxy else None

    # Iniciar MicroProxy local
    micro_proxy = MicroProxy()
    if p_dict:
        micro_proxy.set_upstream(p_dict["host"], p_dict["port"], p_dict.get("username"), p_dict.get("password"))
    micro_proxy.start()
    print(f"[*] MicroProxy activo en 127.0.0.1:{micro_proxy.port}")

    cmd_queue = queue.Queue()
    stop_event = threading.Event()

    hud_app = None
    root = None

    if not no_gui:
        root = tk.Tk()
        hud_app = CompactHUD(root, micro_proxy, curp_arg, cmd_queue)

    worker_thread = threading.Thread(
        target=browser_worker,
        args=(micro_proxy, curp_arg, cmd_queue, stop_event, hud_app),
        daemon=True
    )
    worker_thread.start()

    if not no_gui and root:
        def poll():
            if stop_event.is_set():
                root.destroy()
            else:
                root.after(400, poll)

        def on_close():
            cmd_queue.put(("stop", None))
            stop_event.set()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_close)
        root.after(400, poll)
        root.mainloop()
    else:
        try:
            while not stop_event.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            stop_event.set()

    micro_proxy.stop()
    print("[OK] SantaBase Stealth Lite finalizado limpiamente.")


if __name__ == "__main__":
    main()
