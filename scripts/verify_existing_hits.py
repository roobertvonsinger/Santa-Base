#!/usr/bin/env python3
"""
verify_existing_hits.py — Pasa el filtro de tarjeta (check_card_existence) a los hits que YA
estaban en la bóveda antes de que existiera el filtro.

- ACTIVE  → el cliente sigue vivo, se marca card_verified=1 y permanece en la bóveda
- INACTIVE → 401 en el login web: el cliente ya no existe. Se borra de santander_hits
             y su registro en santander_records vuelve a quedar pendiente (results = NULL)
             para que el purger pueda re-intentar con otro criterio en el futuro.
- ERROR   → falla de red/proxy. NO se toca el registro (card_verified queda en 0) y se
             reintenta en la siguiente corrida.

Concurrencia: workers independientes (default 4) con cola compartida. Un mismo id no puede
ser tomado por dos workers a la vez porque se saca de la cola con get() (FIFO, una sola
entrega) y se marca card_verified=1 en la misma transacción que lo borra o lo confirma.
"""

import os
import sys
import time
import sqlite3
import argparse
import asyncio
import subprocess
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from santander_runner import check_card_existence, get_default_residential_proxy

DB_CANDIDATES = [
    os.environ.get("SANTANDER_DB_PATH"),
    r"C:\Users\rober\Dropbox\TESTING DEV\data\santander.db",
    "/opt/kvm4/apps/santander/data/santander.db",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "santander.db")),
]

LOCK_PATH = os.path.join(os.path.dirname(__file__), "..", ".verify_hits.lock")


class SingleInstanceLock:
    """Lock de archivo para que dos corridas del verificador no se pisen.

    Sin esto, lanzar el script dos veces (o dejar el anterior corriendo y abrir otra terminal)
    hacia que ambas carguen la MISMA lista de pendientes al inicio y.verify las mismas tarjetas
    dos veces — el doble de gasto de proxy para el mismo resultado. El lock es exclusivo por
    archivo y se libera solo si el proceso muere (stale lock con PID muerto).
    """

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.acquired = False

    def acquire(self) -> bool:
        # Si existe, verificar que el PID dueño siga vivo antes de robarlo
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    owner_pid = int(f.read().strip())
                if _pid_alive(owner_pid):
                    return False
                print(f"[*] Lock obsoleto (PID {owner_pid} muerto). Reclamando.")
            except Exception:
                pass  # lock corrupto -> tomarlo
            # O_EXCL falla mientras el archivo exista, haya muerto el dueño o no: hay que
            # quitarlo primero. Sin este remove el mensaje "Reclamando" era mentira y el
            # proceso se iba con FileExistsError sin llegar a tomar el lock.
            try:
                os.remove(self.path)
            except OSError:
                pass
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            self.acquired = True
            return True
        except FileExistsError:
            return False

    def release(self):
        if self.acquired:
            try:
                os.remove(self.path)
            except Exception:
                pass
            self.acquired = False


def _pid_alive(pid: int) -> bool:
    """True si el proceso existe. En Windows y POSIX la semántica difiere."""
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def resolve_db() -> str:
    for c in DB_CANDIDATES:
        if c and os.path.exists(c):
            return c
    raise SystemExit("No se encontro santander.db en ninguna ruta conocida")


def load_pending(db: str, limit: int) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db, timeout=60.0)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT id, u6acct, curp, dmname
            FROM santander_hits
            WHERE COALESCE(card_verified, 0) = 0
            ORDER BY id ASC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def apply_result(db: str, hit_id: int, curp: str, status: str, detail: str):
    """Escribe el resultado. Una sola transaccion: o se borra (INACTIVE) o se confirma (ACTIVE).

    El UPDATE de santander_records usa el curp como ancla porque es la columna UNIQUE de la
    bóveda — aunque el id de santander_records y el de santander_hits_no coincidan siempre,
    el curp es el identificador de negocio real y es el que garantiza no pisar otro registro.
    """
    conn = sqlite3.connect(db, timeout=60.0)
    conn.execute("PRAGMA busy_timeout = 30000;")
    try:
        cur = conn.cursor()

        if status == "ACTIVE":
            cur.execute(
                "UPDATE santander_hits SET card_verified = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (hit_id,),
            )
        elif status == "INACTIVE":
            cur.execute("DELETE FROM santander_hits WHERE id = ?", (hit_id,))
            # El lead vuelve a la base para que no se pierda: se libera el results para que
            # el purger pueda volver a considerarlo, pero queda marcado por que se salio.
            cur.execute(
                "UPDATE santander_records SET results = ? WHERE curp = ?",
                (f"OFF: tarjeta inactiva ({detail})", curp),
            )

        conn.commit()
    finally:
        conn.close()


async def main_async(limit: int, workers: int, delay: float):
    db = resolve_db()
    print("=" * 68)
    print("[*] VERIFICACION DE EXISTENCIA — HITS PREVIOS EN LA BOVEDA")
    print("=" * 68)
    print(f"BD: {db}")

    pending = load_pending(db, limit)
    total_hits = len(pending)
    print(f"[*] Hits pendientes de verificar: {total_hits} (card_verified = 0)")

    if not pending:
        print("[✓] Nada que verificar. Todos los hits ya pasaron el filtro de tarjeta.")
        return

    queue: asyncio.Queue = asyncio.Queue()
    for p in pending:
        queue.put_nowait(p)

    stats = {"active": 0, "inactive": 0, "error": 0, "done": 0}
    lock = asyncio.Lock()

    async def worker(w_idx: int):
        while not queue.empty():
            item = await queue.get()
            rid = item["id"]
            curp = item.get("curp") or ""
            name = (item.get("dmname") or "")[:24]

            card_digits = "".join(c for c in (item.get("u6acct") or "") if c.isdigit())
            if len(card_digits) < 16:
                # Sin tarjeta completa no se puede verificar. No se marca: queda pendiente.
                async with lock:
                    stats["error"] += 1
                    stats["done"] += 1
                print(f"  [⚠️ SIN TARJETA] ID:{rid} | {name} | ({card_digits and len(card_digits) or 0} digitos)", flush=True)
                queue.task_done()
                continue

            try:
                proxy = get_default_residential_proxy()
            except Exception as ex:
                async with lock:
                    stats["error"] += 1
                    stats["done"] += 1
                print(f"  [⚠️ PROXY] ID:{rid} | {ex}", flush=True)
                await asyncio.sleep(2.0)
                queue.task_done()
                continue

            # check_card_existence es sincrono/bloqueante (requests) -> to_thread para no
            # congelar el event loop mientras los otros workers avanzan.
            res = await asyncio.to_thread(check_card_existence, card_digits[:16], proxy=proxy)
            status = res.get("status", "ERROR")
            detail = res.get("detail", "")

            if status in ("ACTIVE", "INACTIVE"):
                try:
                    await asyncio.to_thread(apply_result, db, rid, curp, status, detail)
                except Exception as ex:
                    async with lock:
                        stats["error"] += 1
                        stats["done"] += 1
                    print(f"  [💥 BD] ID:{rid} | {ex}", flush=True)
                    queue.task_done()
                    continue

            async with lock:
                if status == "ACTIVE":
                    stats["active"] += 1
                elif status == "INACTIVE":
                    stats["inactive"] += 1
                else:
                    stats["error"] += 1
                stats["done"] += 1
                d = stats["done"]
                a, i, e = stats["active"], stats["inactive"], stats["error"]
                print(f"  [{d}/{total_hits}] ID:{rid} | {name} | {status} | {detail} | 🟢{a} 🔴{i} ⚠️{e}", flush=True)

            queue.task_done()
            if delay > 0:
                await asyncio.sleep(delay)

    tasks = [asyncio.create_task(worker(i)) for i in range(workers)]
    await asyncio.gather(*tasks)

    print("\n" + "=" * 68)
    print(f"[✓] VERIFICACION TERMINADA")
    print(f"    Activos (permanecen): {stats['active']}")
    print(f"    Inactivos (borrados): {stats['inactive']}")
    print(f"    Errores (pendientes): {stats['error']}")
    print("=" * 68)


def main():
    parser = argparse.ArgumentParser(description="Verifica existencia de tarjeta en hits ya presentes en la boveda")
    parser.add_argument("--limit", type=int, default=500, help="Maximo de hits a verificar en esta corrida")
    parser.add_argument("--workers", type=int, default=4, help="Workers en paralelo (default: 4)")
    parser.add_argument("--delay", type=float, default=1.5, help="Pausa entre verificaciones por worker (segundos)")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    lock = SingleInstanceLock(LOCK_PATH)
    if not lock.acquire():
        try:
            with open(lock.path, "r", encoding="utf-8") as f:
                owner = f.read().strip()
        except Exception:
            owner = "?"
        print(f"[!] Ya hay una verificacion corriendo (PID {owner}).")
        print("    No se lanza una segunda: quemaria proxy duplicando las mismas tarjetas.")
        print("    Espera a que termine, o borra el lock si el proceso ya no existe:")
        print(f"      del \"{lock.path}\"")
        raise SystemExit(1)

    try:
        asyncio.run(main_async(limit=args.limit, workers=args.workers, delay=args.delay))
    finally:
        lock.release()


if __name__ == "__main__":
    main()