# -*- coding: utf-8 -*-
"""Módulo runner para santa-base.

Exporta:
  - check_single_curp: pipeline HTTP curl_cffi de onboarding Santander para validar CURP.
  - check_card_existence: validación web en Chromium headful para confirmar si un cliente sigue activo.
  - format_short_reason: formato resumido para UI.
  - get_default_residential_proxy: proxy residencial MX rotativo vía Proxy001.
"""

from __future__ import annotations
from typing import Any, Dict, Optional, List, Tuple
import asyncio
import time
import sys
import os
import json
import re
import random
from curl_cffi import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def format_short_reason(detail: str) -> str:
    if not detail:
        return "Rechazo"
    short = detail.strip()
    if "PE1002" in short:
        return "PE1002"
    elif "timeout" in short.lower():
        return "Timeout"
    elif "confirm-contact" in short or "contacto" in short.lower():
        return "Reg. previo"
    elif "derivation" in short.lower() or "likeu" in short.lower():
        return "LikeU Pro"
    elif "sucursal" in short.lower() or "rechazo" in short.lower():
        return "Sucursal"
    return short[:15].strip()


def get_default_residential_proxy() -> Dict[str, str]:
    sid = random.randint(10000000, 99999999)
    return {
        "server": "http://us.proxy001.com:7878",
        "username": f"santabase1_custom_zone_MX_ssid_{sid}_time_10",
        "password": "Santabase123"
    }


STATE_COORDS = {
    "nuevo leon": ("25.6866", "-100.3161"),
    "jalisco": ("20.6597", "-103.3496"),
    "ciudad de mexico": ("19.4326", "-99.1332"),
    "cdmx": ("19.4326", "-99.1332"),
    "distrito federal": ("19.4326", "-99.1332"),
    "durango": ("24.0277", "-104.6532"),
    "puebla": ("19.0414", "-98.2063"),
    "queretaro": ("20.5888", "-100.3899"),
    "baja california": ("32.5149", "-117.0382"),
    "quintana roo": ("21.1619", "-86.8515"),
    "yucatan": ("20.9674", "-89.5926"),
    "veracruz": ("19.1738", "-96.1342"),
    "chiapas": ("16.7569", "-93.1292"),
    "guanajuato": ("21.1221", "-101.6826"),
    "sinaloa": ("24.8091", "-107.3940"),
    "sonora": ("29.0729", "-110.9559"),
    "chihuahua": ("28.6353", "-106.0889"),
    "coahuila": ("25.4260", "-101.0053"),
    "san luis potosi": ("22.1565", "-100.9855"),
    "aguascalientes": ("21.8853", "-102.2916"),
    "morelos": ("18.9242", "-99.2216"),
    "estado de mexico": ("19.2826", "-99.6557"),
    "mexico": ("19.2826", "-99.6557"),
    "hidalgo": ("20.1011", "-98.7591"),
    "oaxaca": ("17.0608", "-96.7253"),
}


def get_coords_for_state(state_name: str) -> tuple[str, str]:
    if not state_name:
        return ("19.4326", "-99.1332")
    s = state_name.strip().lower()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")]:
        s = s.replace(a, b)
    for k, v in STATE_COORDS.items():
        if k in s or s in k:
            return v
    return ("19.4326", "-99.1332")


def _execute_attempt(
    curp: str,
    proxy: Optional[Dict[str, str]] = None,
    state: str = "NUEVO LEON",
    lat: Optional[str] = None,
    lon: Optional[str] = None
) -> Dict[str, Any]:
    t0 = time.time()
    if proxy is None:
        proxy = get_default_residential_proxy()

    if not lat or not lon:
        lat, lon = get_coords_for_state(state)

    srv = proxy.get("server", "").replace("http://", "").replace("https://", "")
    usr = proxy.get("username", "")
    pwd = proxy.get("password", "")
    if usr and pwd:
        proxy_url = f"http://{usr}:{pwd}@{srv}"
    else:
        proxy_url = f"http://{srv}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-419,es;q=0.9",
        "Referer": "https://onboarding.santander.com.mx/cuenta-digital-lite/personal-data",
        "Origin": "https://onboarding.santander.com.mx",
        "Content-Type": "application/json"
    }

    proxies = {"http": proxy_url, "https": proxy_url}
    session = requests.Session(impersonate="chrome120", proxies=proxies)

    try:
        # Paso 1: Inicializar sesión en onboarding
        r1 = session.get(
            "https://onboarding.santander.com.mx/api/v1/obu/N2/multitask/session/init",
            headers=headers,
            timeout=8
        )
        if r1.status_code != 200:
            return {
                "curp": curp,
                "status": "RETRY",
                "detail": f"Init HTTP {r1.status_code}",
                "time": round(time.time() - t0, 1)
            }

        # Paso 2: Aceptar términos y condiciones
        r2 = session.post(
            "https://onboarding.santander.com.mx/api/v1/obu/N2/multitask/agreements/accept",
            headers=headers,
            json={
                "data": {
                    "privacy": True,
                    "termsAndConditions": True,
                    "originFlow": "/cuenta-digital-lite/personal-data"
                }
            },
            timeout=8
        )

        if r2.status_code != 200:
            return {
                "curp": curp,
                "status": "RETRY",
                "detail": f"Agreements HTTP {r2.status_code}",
                "time": round(time.time() - t0, 1)
            }

        # Paso 3: Consultar CURP en RENAPO
        r3 = session.post(
            "https://onboarding.santander.com.mx/api/v1/obu/N2/multitask/curp/consulta",
            headers=headers,
            json={"data": {"birthCountry": "052", "mainPersonalIdentifier": curp}},
            timeout=10
        )
        if r3.status_code != 200:
            err_msg = ""
            err_code = ""
            try:
                notif = r3.json().get("notifications", [{}])[0]
                err_msg = notif.get("message", "")
                err_code = notif.get("code", "")
            except Exception:
                pass

            is_permanent_reject = (
                r3.status_code in (400, 404, 422, 423)
                or err_code in ("OB-ORQ-05", "OB-ORQ-06")
                or any(k in err_msg.lower() for k in ["invalid", "invalida", "blocked", "bloqueado", "no encontrada", "not found"])
            )
            if is_permanent_reject:
                return {
                    "curp": curp,
                    "status": "OFF",
                    "detail": f"Rechazo RENAPO/Bloqueado ({r3.status_code}: {err_code or err_msg})",
                    "time": round(time.time() - t0, 1)
                }
            return {
                "curp": curp,
                "status": "RETRY",
                "detail": f"Consulta HTTP {r3.status_code}",
                "time": round(time.time() - t0, 1)
            }

        d3 = r3.json().get("data", {})
        client_name = f"{d3.get('name', '')} {d3.get('lastName', '')} {d3.get('secondLastName', '')}".strip()

        # Paso 4: Validar preexistencia contra el Core Bancario Santander
        r4 = session.post(
            "https://onboarding.santander.com.mx/api/v1/obu/case/registrada/N2/preexistence/validar",
            headers=headers,
            json={
                "data": {
                    "state": state,
                    "os": "Android",
                    "deviceVersion": "Android Google Pixel 9 15",
                    "browserSize": "400x850",
                    "resolutionScreen": "800x1700",
                    "latitude": lat,
                    "longitude": lon
                }
            },
            timeout=28
        )
        if r4.status_code != 200:
            pe_code = ""
            pe_msg = ""
            try:
                notif4 = r4.json().get("notifications", [{}])[0]
                pe_code = notif4.get("code", "")
                pe_msg = notif4.get("message", "")
            except Exception:
                pass
            if pe_code.startswith("PE") or r4.status_code in (400, 422, 423):
                return {
                    "curp": curp,
                    "status": "OFF",
                    "detail": f"Rechazo bancario ({pe_code or r4.status_code})",
                    "time": round(time.time() - t0, 1)
                }
            return {
                "curp": curp,
                "status": "RETRY",
                "detail": f"Preexistence HTTP {r4.status_code}",
                "time": round(time.time() - t0, 1)
            }

        d4 = r4.json().get("data", {})
        pantalla = d4.get("pantallaSiguiente")
        folio = d4.get("folio")
        dur = round(time.time() - t0, 1)

        if pantalla == "datos_contacto_02":
            return {
                "curp": curp,
                "status": "ON",
                "detail": "Elegible: avanzó a contact-data",
                "pantallaSiguiente": pantalla,
                "folio": folio,
                "name": client_name,
                "time": dur
            }
        elif pantalla in ("datos_contacto_01", "datos_contacto_03"):
            return {
                "curp": curp,
                "status": "OFF",
                "detail": "Contacto preexistente (/confirm-contact)",
                "pantallaSiguiente": pantalla,
                "folio": folio,
                "time": dur
            }
        elif pantalla in ("derivation-pro", "derivacion_01"):
            return {
                "curp": curp,
                "status": "OFF",
                "detail": "Derivación LikeU Pro (/derivation-pro)",
                "pantallaSiguiente": pantalla,
                "folio": folio,
                "time": dur
            }
        elif any(k in str(pantalla).lower() for k in ["derivacion", "sucursal", "rechazo"]):
            return {
                "curp": curp,
                "status": "OFF",
                "detail": f"Rechazo en pantalla ({pantalla})",
                "pantallaSiguiente": pantalla,
                "folio": folio,
                "time": dur
            }
        else:
            return {
                "curp": curp,
                "status": "RETRY",
                "detail": f"Pantalla inesperada ({pantalla})",
                "pantallaSiguiente": pantalla,
                "folio": folio,
                "time": dur
            }

    except Exception as ex:
        return {
            "curp": curp,
            "status": "RETRY",
            "detail": f"Excepción red: {str(ex)[:60]}",
            "time": round(time.time() - t0, 1)
        }
    finally:
        session.close()


def _check_curp_sync(
    curp: str,
    proxy: Optional[Dict[str, str]] = None,
    state: str = "NUEVO LEON",
    lat: Optional[str] = None,
    lon: Optional[str] = None
) -> Dict[str, Any]:
    for attempt in range(3):
        p = proxy if (proxy and attempt == 0) else get_default_residential_proxy()
        res = _execute_attempt(curp, proxy=p, state=state, lat=lat, lon=lon)
        if res.get("status") in ("ON", "OFF"):
            return res
        if attempt < 2 and "Excepción red" in str(res.get("detail", "")):
            time.sleep(0.3)
            continue
        return res
    return res


async def check_single_curp(
    curp: str,
    proxy: Optional[dict] = None,
    state: str = "NUEVO LEON",
    lat: Optional[str] = None,
    lon: Optional[str] = None
) -> dict:
    """Verifica un CURP vía pipeline HTTP directo (Chrome 120 TLS) en ~5-7 segundos sin navegadores."""
    return await asyncio.to_thread(_check_curp_sync, curp, proxy=proxy, state=state, lat=lat, lon=lon)


async def run_batch(curps: list[str], concurrency: int = 3) -> list[dict]:
    queue = asyncio.Queue()
    for i, c in enumerate(curps, 1):
        queue.put_nowait((i, c))

    results = [None] * len(curps)

    async def worker():
        while not queue.empty():
            try:
                idx, curp = await queue.get()
            except Exception:
                break
            res = await check_single_curp(curp)
            results[idx - 1] = res
            queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(min(concurrency, len(curps)))]
    await queue.join()
    for w in workers:
        w.cancel()
    return results

# ---------------------------------------------------------------------------
# Flujo web real (Playwright headful, directo, sin proxy, geolocalización forzada).
# El nombre y la ubicación son obligados por el sitio: sin geolocation + permiso,
# el input de tarjeta no se habilita y no hay forma de continuar.
#
# MEDIDO (no estimado) con sonda de instrumentación el 2026-10-02:
#   sync_playwright() startup ....... 0.79s
#   chromium.launch() .............. 0.19s   <-- GRATIS si se reusa browser
#   goto(login) .................... 3.47s
#   respuesta anonymous_invoke ..... 5.57s   (espera de la pagina, unavoidable)
#   escribir 16 digitos ............ 1.05s   (delay=55ms por caracter)
#   press(Enter) -> /assert ........ 0.43s
#   /assert -> /login .............. 0.47s
#   => el veredicto esta disponible 0.90s despues de Enter.
# El codigo anterior dormia 14000ms fijos: 13s de wasted wait por tarjeta, y ademas
# relanzaba Chromium desde cero (3.54s medidos) en CADA llamada. Bajo carga eso es
# lo que hace que el purger "no saque nada": ~18s de CPU por tarjeta para un dato
# que se resuelve en 0.9s.
# ---------------------------------------------------------------------------

_URL = "https://santanderweb.santander.com.mx/public/ts/login/"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

# Cotas del sitio, NO negociables: el rafagueo de la sesion anterior provoco que nos
# cerraran la VPS. Estos numeros son el freno explicito; subirlos es decision de Robert,
# no una optimization que yoFaire de mas.
_WEB_MIN_INTERVAL_SEC = 4.0     # minimo entre dos tarjetas contra santanderweb
_WEB_LAUNCH_ARGS = ["--window-position=1900,0", "--window-size=900,700"]

_browser_singleton = {"pw": None, "browser": None, "last_call": 0.0}
_web_lock = None


def _get_web_lock():
    """Lock global: Playwright sync API no es thread-safe, un solo lock serializa
    todos los workers del purger contra la misma ventana de Chromium."""
    global _web_lock
    if _web_lock is None:
        import threading
        _web_lock = threading.Lock()
    return _web_lock


def _acquire_web_browser():
    """Devuelve un Chromium vivo y reutilizable, relanzandolo solo si murio.
    Reutilizarlo es lo que elimina los 3.54s de startup medidos por llamada."""
    from playwright.sync_api import sync_playwright

    st = _browser_singleton
    if st["pw"] is None:
        st["pw"] = sync_playwright().start()
    if st["browser"] is None or not st["browser"].is_connected():
        st["browser"] = st["pw"].chromium.launch(headless=False, args=_WEB_LAUNCH_ARGS)
    return st["browser"]


def _close_web_browser():
    """Cierra y libera el Chromium compartido. Llamar solo al apagar el daemon:
    cada check crea/destruye contextos, pero el proceso de navegador se queda vivo."""
    st = _browser_singleton
    try:
        if st["browser"] is not None:
            st["browser"].close()
    except Exception:
        pass
    try:
        if st["pw"] is not None:
            st["pw"].stop()
    except Exception:
        pass
    st["pw"] = None
    st["browser"] = None


def _throttle_web():
    """Impone el intervalo minimo entre tarjetas para no rafallar al banco."""
    wait = _WEB_MIN_INTERVAL_SEC - (time.time() - _browser_singleton["last_call"])
    if wait > 0:
        time.sleep(wait)
    _browser_singleton["last_call"] = time.time()


def check_card_existence(
    card_number: str,
    proxy: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Verifica si un cliente sigue activo en Santander Web.

    Flujo real en Chromium headful (Playwright):
      1. Cargar la página de login (geolocation + permission concedidos).
      2. Localizar el campo `#buc-input` (tarjeta, placeholder "No. de tarjeta").
      3. Escribir los 16 dígitos y dar Enter.
      4. Capturar el response del assert y del /login.
      5. Devolver status ACTIVE / INACTIVE / ERROR + detail + tiempo.

    Restricciones medidas (no son suposiciones):
      - headless SIEMPRE bloqueado por Akamai (403). headful es obligatorio.
      - geolocation + permissions=["geolocation"] son obligatorios: sin ellos el
        input nunca se habilita.
      - no usa proxy: estamos en la PC de Robert, direct connection.
      - cada tarjeta abre su propio contexto (cookies limpias, aisladas).

    Returns:
        dict con status: "ACTIVE", "INACTIVE" o "ERROR", más detail y time.
    """
    t0 = time.time()

    card_digits = "".join(c for c in card_number if c.isdigit())
    if len(card_digits) < 16:
        return {"status": "ERROR", "detail": f"tarjeta incompleta ({len(card_digits)} digitos)", "time": round(time.time() - t0, 1)}

    card_16 = card_digits[:16]

    # Cada llamada abre su propio browser + contexto para aislar cookies.
    # Se cierra al terminar para liberar memoria.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as ex:
        return {"status": "ERROR", "detail": f"playwright no disponible: {ex}", "time": round(time.time() - t0, 1)}

    resultado = {"status": "ERROR", "detail": "fallo interno", "time": round(time.time() - t0, 1)}
    try:
        with _get_web_lock():
            _throttle_web()
            browser = _acquire_web_browser()
            resultado = _run_flow(browser, card_16)
    except Exception as ex:
        return {"status": "ERROR", "detail": f"navegador: {str(ex).splitlines()[0][:70]}", "time": round(time.time() - t0, 1)}

    return resultado


def _run_flow(browser, card_16: str) -> Dict[str, Any]:
    """Ejecuta el flujo completo de una sola tarjeta dentro del navegador dado."""
    t0 = time.time()
    ctx = browser.new_context(
        user_agent=_UA,
        locale="es-MX",
        viewport={"width": 1920, "height": 1080},
        geolocation={"latitude": 20.78770839612377, "longitude": -103.46146732811971},
        permissions=["geolocation"],
    )
    page = ctx.new_page()

    visto = {}

    def on_response(resp):
        u = resp.url
        for tag, path in (
            ("invoke", "/tsm/api/v2/auth/anonymous_invoke"),
            ("assert", "/tsm/api/v2/auth/assert"),
            ("login", "/tsm/api/v2/auth/login"),
        ):
            if path in u and tag not in visto:
                try:
                    visto[tag] = json.loads(resp.text())
                except Exception:
                    visto[tag] = None

    page.on("response", on_response)

    # 1. Cargar login. networkidle nunca se calma por los beacons infinitos de Dynatrace,
    #    asi que solo esperamos domcontentloaded y dejamos que el paso 2 espere al input.
    page.goto(_URL, wait_until="domcontentloaded", timeout=60000)

    # 2. Localizar campo de tarjeta. El DOM real usa #buc-input con placeholder
    #    "No. de tarjeta / Código de cliente". Se espera al elemento real en vez de
    #    dormir 8s a ciegas: si el input aparece en 4s o en 9s, ambos casos funcionan
    #    igual y se ahorra el tiempo muerto.
    campo = None
    try:
        campo = page.locator("#buc-input").first
        campo.wait_for(state="visible", timeout=20000)
    except Exception:
        campo = None

    if not campo:
        # Fallback: barrido por placeholder/aria-label de los inputs visibles.
        candidatos = page.locator("input:visible")
        for i in range(candidatos.count()):
            el = candidatos.nth(i)
            ph = (el.get_attribute("placeholder") or "") + (el.get_attribute("aria-label") or "")
            if "tarjeta" in ph.lower() or "cliente" in ph.lower() or "número" in ph.lower():
                campo = el
                break

    if not campo:
        ctx.close()
        return {
            "status": "ERROR",
            "detail": "no encontre campo de tarjeta (buc-input) en la página",
            "time": round(time.time() - t0, 1),
        }

    # 3. Escribir tarjeta y Enter. En vez de dormir 14s a ciegas, esperamos la
    #    respuesta real de /login con expect_response (medido: llega 0.90s tras Enter).
    #    El timeout de 25s es solo el techo de seguridad si el banco nunca contesta.
    campo.click()
    campo.fill("")
    campo.type(card_16, delay=55)
    try:
        with page.expect_response(
            lambda r: "/tsm/api/v2/auth/login" in r.url, timeout=25000
        ):
            campo.press("Enter")
    except Exception:
        # Banco no devolvio /login dentro del techo: no se puede affirmar nada.
        # Se devuelve ERROR (nunca INACTIVE) para que el purger no queme el lead.
        ctx.close()
        return {
            "status": "ERROR",
            "detail": "sin respuesta de /login tras enviar la tarjeta",
            "time": round(time.time() - t0, 1),
        }

    # Pequena gracia para que el listener `on_response` termine de volcar el JSON.
    time.sleep(0.4)

    # 4. Leer respuestas capturadas.
    d = ((visto.get("assert") or {}).get("data") or {})
    state = d.get("state", "")
    uid = ((d.get("data") or {}).get("redirect") or {}).get("target", {}).get("user_id", "")

    # 5. Veredicto: REGLA DE ORO.
    # SOLO es HIT si llega a pedir contraseña (password_authenticate_form).
    # Si da you_cannot_continue, manda a SuperLínea o cualquier error -> DESCARTADO.
    ld = ((visto.get("login") or {}).get("data") or {})
    form_str = ""
    for cf in (ld.get("control_flow") or []):
        form_str = (cf.get("strings", {}) or {}).get("form", "")
        if form_str:
            break

    if "password_authenticate_form" in form_str:
        nombre = ""
        m = re.search(r'"user_id"\s*:\s*"([^"]+)"', form_str)
        if m:
            nombre = m.group(1)
        detalle = f"user_id={uid}"
        if nombre:
            detalle += f" | nombre={nombre}"
        ctx.close()
        return {"status": "ACTIVE", "detail": detalle, "time": round(time.time() - t0, 1)}

    ctx.close()
    return {
        "status": "INACTIVE",
        "detail": "no pide password (bloqueada o no cliente)",
        "time": round(time.time() - t0, 1),
    }