"""Verdad del 431 de proxy001: ¿saldo, credenciales o formato?

proxy001 responde con 'CONNECT tunnel failed, response 431'. El 431 suele ser
saldo agotado o credenciales invalidas, pero eso hay que leerlo, no suponerlo
(la regla: no a la presuncion, sí a la hipotesis testeada).

Ademas hay una variable de sesion en el usuario: `_ssid_<random>_time_10`.
Si el gate de proxy001 invalida la sesion tras 10 min, el `random` nuevo en
cada llamada podria ser justo lo que lo rompe. Se prueba con y sin `time_`.
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

USER = "santabase1_custom_zone_MX"
PASS = "Santabase123"
HOST = "us.proxy001.com:7878"

# Variantes: la que usa el runner, y las que descartan una a una las partes
# sospechosas del usuario.
VARIANTES = [
    ("como el runner (ssid+time_10)", "%s_ssid_12345678_time_10" % USER),
    ("sin time_",                    "%s_ssid_12345678" % USER),
    ("sin ssid, con time_10",        "%s_time_10" % USER),
    ("solo zona",                    USER),
]

print("%-30s %-9s %s" % ("variante", "codigo", "detalle"))
print("-" * 92)
for etq, u in VARIANTES:
    url = "http://%s:%s@%s" % (u, PASS, HOST)
    t0 = time.time()
    try:
        r = requests.get("https://api.ipify.org?format=json",
                         proxies={"http": url, "https": url},
                         timeout=22, impersonate="chrome120")
        print("%-30s %-9s OK ip=%s  (%.1fs)"
              % (etq, r.status_code, r.text[:34], time.time() - t0))
    except Exception as e:
        msg = str(e)
        cod = ""
        if "response 4" in msg or "response 5" in msg:
            cod = msg.split("response ")[1].split(".")[0]
        elif "response 4" in msg:
            cod = "4xx"
        print("%-30s %-9s %s  (%.1fs)"
              % (etq, cod or "ERR", msg[:74], time.time() - t0))

print()
print("Si TODAS devuelven 431 -> la cuenta (saldo/credenciales) esta muerta y")
print("no hay variacion de formato que lo arregle: hay que recargar proxy001.")
print("Si solo falla la del runner -> es la sesion/time_ lo que lo rompe.")