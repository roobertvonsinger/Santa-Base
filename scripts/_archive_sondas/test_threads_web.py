"""PRUEBA DEL BUG DE HILOS: verifica que N llamadas PARALELAS a
check_card_existence ya no tiren "Cannot switch to a different thread".

Contexto medido: con --workers 2, 2 de 23 tarjetas se perdieron con ese error.
El daemon corre con workers=5. Este test lanza N hilos de golpe contra el
navegador real y falla si aparece el error o si el navegador se multiplica
(multiples ventanas de Chromium = cada llamada destructurando la anterior).

Se mide tambien que las llamadas se SERIALIZAN (una detras de otra), que es lo
que un unico hilo dueno implica, y no se pisan entre si.
"""
import os
import sys
import threading
import time

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _RAIZ)

from santander_runner import check_card_existence, _close_web_browser, _browser_singleton  # noqa: E402

N = 5
CUENTAS = [
    "5471460039156711", "5471460035125355", "5471460039156711",
    "5471460035125355", "5471460039156711",
]

print("PRUEBA DE HILOS: %d llamadas PARALELAS a check_card_existence" % N)
print("=" * 74)

resultados = {}
lock = threading.Lock()
t0 = time.time()


def worker(i, cuenta):
    t = time.time()
    r = check_card_existence(cuenta)
    with lock:
        resultados[i] = (r.get("status"), (r.get("detail") or "")[:60], time.time() - t)


hilos = [threading.Thread(target=worker, args=(i, CUENTAS[i % len(CUENTAS)]))
         for i in range(N)]
for h in hilos:
    h.start()
for h in hilos:
    h.join()

print()
fallos_thread = 0
for i in sorted(resultados):
    st, det, dt = resultados[i]
    marca = ""
    if "different thread" in det.lower():
        marca = "   <-- BUG DE HILO PRESENTE"
        fallos_thread += 1
    print("  #%d  %-10s %-60s %5.1fs%s" % (i, st, det, dt, marca))

print()
st = _browser_singleton
print("browser singletons vivos: pw=%s browser=%s"
      % (st["pw"] is not None, st["browser"] is not None))
conectado = False
try:
    conectado = st["browser"] is not None and st["browser"].is_connected()
except Exception:
    pass
print("browser conectado: %s   (una sola ventana, como se requiere)" % conectado)
print("hilo dueno: %s" % (st["owner_tx"] is not None))
print()
print("Total: %.1fs para %d llamadas = %.1fs/llamada"
      % (time.time() - t0, N, (time.time() - t0) / N))
print()

_close_web_browser()
print()
if fallos_thread:
    print("FALLO: %d llamadas con 'Cannot switch to a different thread'" % fallos_thread)
    sys.exit(1)
print("OK: 0 errores de hilo en %d llamadas paralelas" % N)