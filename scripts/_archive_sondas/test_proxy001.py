"""¿proxy001 responde, o lo que falla es el proxy-gate de la VPS?

Contexto: el purger mostraba 'CONNECT tunnel failed' en bucle. proxy-gate vive
en la VPS Karen (2.25.98.162:8888) y la VPS esta caida/inaccesible. Pero
get_default_residential_proxy() NO usa el gate: va directo a proxy001.com:7878.

Hay que separar:
  A) proxy001 alcanzable  -> el fallo era del gate, que este purger ni usa
  B) proxy001 caido       -> el bucle era real y no hay salida

FORMATO: curl_cffi no acepta el dict {server,username,password} en `proxies=`
(dio 'initializer for ctype void* must be a cdata pointer, not dict'). Hay que
armar la URL con las credenciales embebidas, como hace santander_runner.
"""
import os
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from curl_cffi import requests  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
from santander_runner import get_default_residential_proxy  # noqa: E402

p = get_default_residential_proxy()
srv = p["server"]
if srv.startswith("http://"):
    srv = srv[len("http://"):]
# Formato que curl_cffi si entiende: http://user:pass@host:puerto
proxy_url = "http://%s:%s@%s" % (p["username"], p["password"], srv)

print("=== A) PROXY DIRECTO (proxy001) — el que usa el purger ===")
print("URL (parcial): ...%s@%s" % (p["username"][-24:], srv))
t0 = time.time()
try:
    r = requests.get("https://api.ipify.org?format=json",
                     proxies={"http": proxy_url, "https": proxy_url},
                     timeout=25, impersonate="chrome120")
    print("RESPUESTA %s en %.1fs -> %s"
          % (r.status_code, time.time() - t0, r.text[:90]))
    print("VEREDICTO: proxy001 FUNCIONA")
except Exception as e:
    print("FALLO en %.1fs: %s" % (time.time() - t0, str(e)[:200]))
    print("VEREDICTO: proxy001 CAIDO")

print()
print("=== B) PROXY-GATE (VPS Karen) — el que NO usa este purger ===")
for url in ("http://127.0.0.1:8888/proxy", "http://2.25.98.162:8888/proxy"):
    t0 = time.time()
    try:
        r = requests.get(url, timeout=8)
        print("%-34s %s en %.1fs" % (url, r.status_code, time.time() - t0))
    except Exception as e:
        print("%-34s SIN RESPUESTA %.1fs: %s"
              % (url, time.time() - t0, str(e)[:88]))

print()
print("=== C) DIRECTO (sin proxy) — referencia ===")
t0 = time.time()
try:
    r = requests.get("https://api.ipify.org?format=json", timeout=20,
                     impersonate="chrome120")
    print("DIRECTO %s en %.1fs -> %s"
          % (r.status_code, time.time() - t0, r.text[:90]))
except Exception as e:
    print("DIRECTO FALLO: %s" % str(e)[:120])