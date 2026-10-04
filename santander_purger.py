#!/usr/bin/env python3
"""
santander_purger.py — Motor de Depuración Segmentada de Alta Velocidad para SantaBase.
Arquitectura Dialéctica Mitigada (Smartplan v2):
- Segmentación por Estado, Límite de Crédito (Casting Seguro) y Juventud (Fecha de Nacimiento).
- Ráfagas (Burst) de 3.5 min y Enfriamiento (Cooldown) de 1.5 min.
- Rotación de proxy residencial MX vía Proxy001 (sid aleatorio por request); ver santander_runner.get_default_residential_proxy.
- Cero Falsos Negativos: Solo se descartan registros con confirmación bancaria explícita; fallas de red se preservan.
- Cero Pérdida de Datos: Inserción directa e inmediata en tabla VIP `santander_hits` para registros HIT, sin pisar trabajo ya asignado por un operador.
- Alta Concurrencia Playwright: Bloqueo de imágenes/fuentes/tracking, preservación de CSS para botones WebComponents.
"""

import os
import sys
import time
import json
import signal
import atexit
import sqlite3
import argparse
import asyncio
import threading
import queue
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Tuple, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# La consola de Windows es cp1252 y el ciclo imprime flechas/emoji (✓, 💥).
# Sin esto, print() lanza UnicodeEncodeError DENTRO del ciclo, el except lo
# captura como "CYCLE ERROR", reintenta 5 veces y se rinde -- medido el
# 2026-10-02, el purger no procesaba ni un registro en local. Es un fallo de
# arranque, no de logica: se arregla aqui y no con PYTHONIOENCODING en el
# comando, para que el daemon de la VPS tampoco dependa de como se invoque.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # stream sin reconfigure (jupyter/pipe raro): no es bloqueante

def _resolve_db_path() -> str:
    """Elige la BD real, priorizando la que TIENE filas.

    El orden anterior probaba `data/santander.db` del repo antes que el
    `../../data/` de la BD de trabajo. En local eso resolvia a un archivo de
    41 KB con la tabla VACIA (medido 2026-10-02: 0 candidatos, purger
    "Sesion finalizada | Total procesados: 0"), mientras la BD buena --
    4,891,788 filas, 1,472,971 con CURP -- quedaba dos niveles mas arriba y
    nunca se miraba. Ahora se elige por contenido: la primera ruta que exista
    Y tenga filas en santander_records; si ninguna, la primera que exista.
    """
    repo = os.path.dirname(os.path.abspath(__file__))
    candidatas = [
        "/opt/kvm4/apps/santander/data/santander.db",
        os.path.join(repo, "data", "santander.db"),
        os.path.abspath(os.path.join(repo, "..", "..", "data", "santander.db")),
    ]
    import sqlite3 as _sq
    primera_existente = None
    for ruta in candidatas:
        if not os.path.exists(ruta):
            continue
        if primera_existente is None:
            primera_existente = ruta
        try:
            c = _sq.connect("file:%s?mode=ro" % ruta.replace("\\", "/"), uri=True).cursor()
            n = c.execute("SELECT COUNT(*) FROM santander_records").fetchone()[0]
            if n:
                return ruta
        except Exception:
            continue  # no es una BD nuestra (permisos, corrupta, otro schema)
    return primera_existente or candidatas[0]


DEFAULT_DB_PATH = _resolve_db_path()

# Circuit breaker de infraestructura. Ver el uso en el worker_loop: si se
# acumulan estos reintentos seguidos SIN un solo resultado real, la Red (proxy
# caido, Santander bloqueando) esta caida y seguir gastando workers no sirve.
# Medido: 9,611 reintentos en una hora con el proxy muerto, cero resultados.
RETRY_CIRCUIT_LIMIT = 30

# Umbral de edad canonico. Vive aqui como constante para que `--born-after` lo
# consuma y las sondas (scripts/sondas/umbral.py) lo importen de una sola fuente.
# Si esto cambia, el conteo de "material disponible" de las sondas cambia con el.
# Antes estaba pegado a mano como '600101' en tres sondas mientras el purger
# corria con 1963-01-01 -- las sondas contaban filas que el purger jamas tocaba.
BORN_AFTER_DEFAULT = "1963-01-01"

PROXY_GATE_URL = "http://127.0.0.1:8888/proxy"
# El status JSON vive siempre junto a la BD activa (mismo directorio que DEFAULT_DB_PATH ya resolvió),
# nunca hardcodeado por separado — evita que purger y app.py apunten a rutas distintas en VPS.
STATUS_JSON_PATH = os.path.join(os.path.dirname(DEFAULT_DB_PATH), "purger_status.json")
START_URL = "https://onboarding.santander.com.mx/cuenta-digital-lite/product-page?utm_source=google-pmax&utm_medium=multi-channel&utm_campaign=MX_RCB_ACC_DEB_NA_AO_N2-PMAX_CVN_CVN_MLT_GAD_PMX_PMAX_NA_CPA&utm_content=multiple_bonif200"


# ==============================================================================
# 1. SQL QUERY BUILDER (SEGMENTACIÓN ROBUSTA)
# ==============================================================================
def parse_estados_quotas(arg_str: str) -> Dict[str, int]:
    """Parsea formatos como 'DURANGO:250,CIUDAD DE MEXICO:250' o 'DURANGO,CDMX'."""
    quotas = {}
    for part in arg_str.split(","):
        p = part.strip()
        if not p:
            continue
        if ":" in p:
            edo, q = p.split(":", 1)
            quotas[edo.strip().upper()] = int(q.strip())
        else:
            quotas[p.upper()] = 100
    return quotas

def build_segment_query(
    estado: Optional[str] = None,
    min_credito: int = 0,
    born_after: Optional[str] = None,
    prioridad: str = "credito_desc",
    limit: Optional[int] = 100
) -> Tuple[str, List[Any]]:
    """Construye consulta parametrizada con sanitización de moneda y campos completos para hits.

    NOTA: el filtro de estado va contra `u6estado`, NO contra `estado`. La columna
    `estado` solo está poblada en las 717 filas ya procesadas (1 estado, Jalisco)
    y es NULL en las 4,861,640 filas del pool; usar `estado` hacía que el purger
    viera cero candidatos. `u6estado` tiene 1,115 valores distintos y es el dato
    real de la entidad de registro.
    """
    sql = """
        SELECT id, u6acct, curp, u6rfc, dmname, u6estado, dmcity, dmzip,
               u6licrea, NULL AS fecha_nacimiento, NULL AS genero,
               u6ladte1, u6tel1, dmaddr1, dmaddr2
        FROM santander_records
        WHERE curp IS NOT NULL AND TRIM(curp) != ''
          AND results IS NULL
    """
    params: List[Any] = []

    if estado:
        sql += " AND UPPER(u6estado) = UPPER(?)"
        params.append(estado)
        
    if min_credito > 0:
        sql += " AND CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER) >= ?"
        params.append(min_credito)
        
    if born_after:
        # `fecha_nacimiento` solo existe en las 717 filas procesadas (NULL en el
        # pool). En el pool la edad sale del RFC: u6rfc[4:10] es YYMMDD.
        sql += " AND SUBSTR(u6rfc, 5, 6) >= ?"
        params.append(born_after[2:4] + born_after[5:7] + born_after[8:10])

    if prioridad == "credito_desc":
        sql += " ORDER BY CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER) DESC"
    elif prioridad == "edad_desc":
        # Mayor edad = fecha de nacimiento mas temprano. El RFC va por century:
        # losNacidos antes de 2000 tienen prefijo YY >= 30 en este corpus.
        sql += " ORDER BY SUBSTR(u6rfc, 5, 2) DESC"
    elif prioridad == "mixto":
        sql += (" ORDER BY CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER) DESC,"
                " SUBSTR(u6rfc, 5, 2) DESC")
    else:
        sql += " ORDER BY id ASC"
        
    if limit and limit > 0:
        sql += " LIMIT ?"
        params.append(limit)
        
    return sql, params


# ==============================================================================
# 2. CLIENTE PROXY-GATE RESIDENCIAL
# ==============================================================================
def parse_proxy_endpoint(data: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Parsea el formato proxy devuelto por proxy-gate:8888."""
    raw = data.get("proxy", "").strip()
    if not raw:
        return None
        
    # Limpiar scheme
    scheme = "http://"
    if raw.startswith("http://"):
        raw = raw[7:]
    elif raw.startswith("https://"):
        scheme = "https://"
        raw = raw[8:]
        
    # Formato A: user:pass@host:port
    if "@" in raw:
        creds, hp = raw.split("@", 1)
        u, p = creds.split(":", 1) if ":" in creds else (creds, "")
        return {"server": f"{scheme}{hp}", "username": u, "password": p}
        
    # Formato B: host:port:user:pass
    parts = raw.split(":")
    if len(parts) >= 4:
        host, port = parts[0], parts[1]
        user = parts[2]
        pwd = ":".join(parts[3:])
        return {"server": f"{scheme}{host}:{port}", "username": user, "password": pwd}
    elif len(parts) == 2:
        return {"server": f"{scheme}{parts[0]}:{parts[1]}", "username": "", "password": ""}
        
    return None

from santander_runner import get_default_residential_proxy, check_single_curp, check_card_existence, format_short_reason

def fetch_proxy_from_gate(gate_url: str = PROXY_GATE_URL, timeout: float = 4.0) -> Optional[Dict[str, str]]:
    """Obtiene una IP residencial mexicana rotatoria. Fuente única: santander_runner.get_default_residential_proxy
    (antes esta credencial estaba hardcodeada y duplicada literal en este archivo y en santander_runner.py —
    cualquier rotación de credenciales requería tocar 2 lugares; ahora hay una sola fuente de verdad)."""
    return get_default_residential_proxy()


# ==============================================================================
# 3. BUFFER ASÍNCRONO DE ESCRITURA SQLITE WAL Y BÓVEDA HITS VIP
# ==============================================================================
class SqliteBatchWriter:
    """Maneja escrituras en SQLite desde un único hilo dedicado para evitar locks y destilar HITS."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.queue: queue.Queue = queue.Queue()
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True, name="SqliteWriterThread")
        self.thread.start()

    def _init_db(self, conn: sqlite3.Connection):
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS santander_hits (
                id INTEGER PRIMARY KEY,
                u6acct TEXT,
                curp TEXT NOT NULL UNIQUE,
                u6rfc TEXT,
                dmname TEXT,
                estado TEXT,
                ciudad TEXT,
                codigo_postal TEXT,
                u6licrea TEXT,
                fecha_nacimiento TEXT,
                genero TEXT,
                direccion TEXT,
                work_status TEXT DEFAULT 'ACTIVE',
                operador TEXT,
                notas TEXT,
                card_verified INTEGER DEFAULT 0,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hits_status ON santander_hits(work_status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hits_estado ON santander_hits(estado);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hits_curp ON santander_hits(curp);")
        conn.commit()

    def enqueue(self, record_dict: Dict[str, Any], result: str, is_green: bool):
        self.queue.put({
            "record": record_dict,
            "result": result,
            "is_green": is_green
        })

    def _worker_loop(self):
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        self._init_db(conn)
        
        batch_off = []
        last_flush = time.time()
        
        while self.running or not self.queue.empty():
            try:
                item = self.queue.get(timeout=0.2)
            except queue.Empty:
                if batch_off and (time.time() - last_flush > 1.5):
                    self._flush_batch(conn, batch_off)
                    batch_off.clear()
                    last_flush = time.time()
                continue
                
            rec = item["record"]
            rid = rec["id"]
            
            if item.get("is_green"):
                # HIT: Escritura directa e inmediata en santander_hits y actualización en santander_records
                try:
                    conn.execute("UPDATE santander_records SET results = ? WHERE id = ?", (item["result"], rid))
                    
                    dir_str = rec.get("direccion")
                    if not dir_str:
                        a1 = rec.get("dmaddr1") or ""
                        a2 = rec.get("dmaddr2") or ""
                        dir_str = f"{a1} {a2}".strip()

                    # INSERT OR IGNORE (no OR REPLACE): si el id/curp ya existe en santander_hits porque un
                    # operador ya lo trabajó (work_status/operador/notas asignados), NO se pisa. OR REPLACE
                    # borraba la fila vieja y la reinsertaba con work_status='ACTIVE', perdiendo ese trabajo
                    # en cualquier carrera entre el purger y la edición manual del mismo id.
                    conn.execute("""
                        INSERT OR IGNORE INTO santander_hits (
                            id, u6acct, curp, u6rfc, dmname, estado, ciudad, codigo_postal,
                            u6licrea, fecha_nacimiento, genero, direccion,
                            work_status, card_verified, checked_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (
                        rid,
                        rec.get("u6acct"),
                        rec.get("curp"),
                        rec.get("u6rfc"),
                        rec.get("dmname"),
                        rec.get("estado"),
                        rec.get("ciudad"),
                        rec.get("codigo_postal"),
                        rec.get("u6licrea"),
                        rec.get("fecha_nacimiento"),
                        rec.get("genero"),
                        dir_str
                    ))
                    conn.commit()
                except Exception as e:
                    print(f"[Writer Error] Error al persistir HIT {rec.get('curp')}: {e}", file=sys.stderr)
            else:
                # OFF: Acumular para batch commit en santander_records
                batch_off.append((item["result"], rid))
                if len(batch_off) >= 10 or (time.time() - last_flush > 2.0):
                    self._flush_batch(conn, batch_off)
                    batch_off.clear()
                    last_flush = time.time()
                    
            self.queue.task_done()
            
        if batch_off:
            self._flush_batch(conn, batch_off)
            batch_off.clear()
            
        conn.close()

    def _flush_batch(self, conn: sqlite3.Connection, batch: List[Tuple[str, int]]):
        try:
            conn.executemany("UPDATE santander_records SET results = ? WHERE id = ?", batch)
            conn.commit()
        except Exception as e:
            print(f"[Writer Error] Error en batch commit: {e}", file=sys.stderr)

    def close(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)


async def execute_curp_check(curp: str, proxy: Optional[Dict[str, str]] = None,
                              state: Optional[str] = None,
                              use_proxy: bool = True) -> Dict[str, Any]:
    """Ejecuta la función canónica de verificación HTTP con hard-timeout y protección.

    `use_proxy=False` propaga hasta santander_runner para correr directo.
    """
    try:
        kwargs: Dict[str, Any] = {"proxy": proxy, "use_proxy": use_proxy}
        if state:
            kwargs["state"] = state
        res = await asyncio.wait_for(check_single_curp(curp, **kwargs), timeout=55.0)
        return res
    except asyncio.TimeoutError:
        return {"curp": curp, "status": "RETRY", "detail": "Timeout (55s excedido)"}
    except Exception as e:
        return {"curp": curp, "status": "RETRY", "detail": f"Error: {str(e)[:60]}"}


# ==============================================================================
# 5. ORQUESTADOR DE RÁFAGAS Y TELEMETRÍA (BURST / COOLDOWN DAEMON)
# ==============================================================================
class SegmentedPurgerDaemon:
    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        estado: Optional[str] = None,
        estados: Optional[str] = None,
        min_credito: int = 0,
        born_after: Optional[str] = None,
        prioridad: str = "credito_desc",
        limit: int = 500,
        workers: int = 5,
        burst_sec: float = 210.0,    # 3.5 minutos
        cooldown_sec: float = 90.0,   # 1.5 minutos
        daemon_mode: bool = False,
        hits_pool_max: int = 12,       # pausa el gasto de proxies si hay >= esto de hits sin trabajar
        hits_pool_resume: int = 10,    # retoma cuando el pool baja a esto o menos (histeresis: nunca
                                       # baja de 10 hits disponibles; si los operadores los mueven a
                                       # SUCCESS/OFF, un hit abre el hueco y el ciclo reactiva el chequeo)
        pause_check_sec: float = 60.0,  # cada cuanto re-checa el pool mientras esta pausado
        use_proxy: bool = True          # False = directo desde la IP de la maquina
    ):
        self.db_path = db_path
        self.use_proxy = use_proxy
        self.estado = estado
        self.estados = estados
        self.min_credito = min_credito
        self.born_after = born_after
        self.prioridad = prioridad
        self.limit = limit
        self.workers = workers
        self.burst_sec = burst_sec
        self.cooldown_sec = cooldown_sec
        self.daemon_mode = daemon_mode
        self.hits_pool_max = hits_pool_max
        self.hits_pool_resume = hits_pool_resume
        self.pause_check_sec = pause_check_sec
        self._paused_for_pool = False  # histeresis: una vez pausado, no retoma hasta llegar a hits_pool_resume

        self.writer = SqliteBatchWriter(self.db_path)
        self.running = True
        self.stats = {
            "total_processed": 0,
            "hits": 0,
            "offs": 0,
            "retries": 0,
            "state": "INIT",
            "rate_per_min": 0.0,
            "active_workers": 0
        }
        # Lo enciende el worker cuando los reintentos seguidos superan
        # RETRY_CIRCUIT_LIMIT sin que haya un solo resultado real.
        self._circuit_tripped = False

    def _count_unworked_hits(self) -> int:
        """Cuenta hits en santander_hits con work_status='ACTIVE' (el pool real que ven los operadores,
        sin contar los que ya estan SUCCESS/OFF). Si la tabla aun no existe, cuenta 0."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=15.0)
            try:
                cur = conn.execute("SELECT COUNT(*) FROM santander_hits WHERE work_status = 'ACTIVE'")
                return cur.fetchone()[0]
            finally:
                conn.close()
        except Exception:
            return 0

    def _migrate_existing_hits(self):
        """Migración única: hits con work_status viejo (NUEVO/EN_GESTION/CERRADO/DESCARTADO)
        se normalizan a ACTIVE. Los que ya tienen card_verified=1 no se tocan."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=15.0)
            try:
                # Verificar si la columna card_verified existe
                cols = [r[1] for r in conn.execute("PRAGMA table_info(santander_hits)").fetchall()]
                if "card_verified" not in cols:
                    conn.execute("ALTER TABLE santander_hits ADD COLUMN card_verified INTEGER DEFAULT 0")
                    conn.commit()
                # Migrar statuses viejos a ACTIVE
                conn.execute("""
                    UPDATE santander_hits SET work_status = 'ACTIVE'
                    WHERE work_status IN ('NUEVO', 'EN_GESTION', 'CERRADO', 'DESCARTADO')
                """)
                migrated = conn.total_changes
                conn.commit()
                print(f"[✓] Migración completada: hits normalizados a ACTIVE")
            finally:
                conn.close()
        except Exception as e:
            print(f"[!] Error en migración: {e}")

    def _write_status_file(self, extra: Optional[Dict[str, Any]] = None):
        """Emite telemetría viva a purger_status.json."""
        payload = dict(self.stats)
        payload["updated_at"] = time.time()
        payload["timestamp_str"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if extra:
            payload.update(extra)
        try:
            os.makedirs(os.path.dirname(STATUS_JSON_PATH), exist_ok=True)
            temp_file = STATUS_JSON_PATH + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(temp_file, STATUS_JSON_PATH)
        except Exception:
            pass

    async def run(self):
        self._migrate_existing_hits()
        self.writer.start()
        print(f"[*] SantaPurger iniciado | BD: {self.db_path} | Workers: {self.workers}")
        if self.estados:
            print(f"[*] Lote Multi-Estado activo: {self.estados} | Min Crédito=${self.min_credito:,}")
        elif self.estado:
            print(f"[*] Filtros: Estado='{self.estado}' | Min Crédito=${self.min_credito:,} | Nacidos >= '{self.born_after or 'Cualquiera'}'")

        # Info sensible de mucho peso operativo (4.9M registros): un error transitorio en un solo
        # ciclo (BD lockeada, red caída, excepción no prevista en un worker) NO debe tumbar el proceso
        # completo. Cada ciclo corre aislado en try/except; si falla, se loguea, se espera con backoff
        # y se reintenta — el daemon solo se detiene por SIGINT/SIGTERM (self.running=False) o por
        # agotar el segmento (COMPLETED).
        consecutive_cycle_errors = 0
        while self.running:
            # Control de cuota: si ya hay suficiente inventario de hits sin trabajar (work_status='ACTIVE'),
            # pausar el gasto de proxy/CPU en vez de seguir acumulando mas de los que los operadores pueden
            # atender. Histeresis (pausa en hits_pool_max, retoma en hits_pool_resume) evita prender/apagar
            # el purger en cada re-chequeo cuando el conteo ronda el umbral.
            unworked = self._count_unworked_hits()
            if self._paused_for_pool and unworked > self.hits_pool_resume:
                self.stats["state"] = "PAUSED_HITS_POOL"
                self._write_status_file({"unworked_hits": unworked, "hits_pool_max": self.hits_pool_max, "hits_pool_resume": self.hits_pool_resume})
                await self._sleep_interruptible(self.pause_check_sec)
                continue
            elif not self._paused_for_pool and unworked >= self.hits_pool_max:
                self._paused_for_pool = True
                print(f"[⏸️] Pool de hits sin trabajar llegó a {unworked} (>= {self.hits_pool_max}). Pausando para no quemar cuota de proxy.", flush=True)
                self.stats["state"] = "PAUSED_HITS_POOL"
                self._write_status_file({"unworked_hits": unworked, "hits_pool_max": self.hits_pool_max, "hits_pool_resume": self.hits_pool_resume})
                await self._sleep_interruptible(self.pause_check_sec)
                continue
            elif self._paused_for_pool and unworked <= self.hits_pool_resume:
                self._paused_for_pool = False
                print(f"[▶️] Pool de hits bajó a {unworked} (<= {self.hits_pool_resume}). Reanudando.", flush=True)

            try:
                keep_going = await self._run_one_cycle()
                consecutive_cycle_errors = 0
                if not keep_going:
                    break
            except Exception as e:
                consecutive_cycle_errors += 1
                backoff = min(60.0, 5.0 * consecutive_cycle_errors)
                print(f"[💥 CYCLE ERROR] Ciclo falló ({consecutive_cycle_errors}x consecutivas): {e} | reintentando en {backoff:.0f}s", file=sys.stderr, flush=True)
                self.stats["state"] = "ERROR"
                self._write_status_file({"last_error": str(e)[:200], "consecutive_cycle_errors": consecutive_cycle_errors})
                if not self.running:
                    break
                await asyncio.sleep(backoff)

        self.writer.close()
        self.stats["state"] = "STOPPED"
        self._write_status_file()
        print(f"\n[🏁] Sesión finalizada | Total procesados: {self.stats['total_processed']} | HITS: {self.stats['hits']} | OFF: {self.stats['offs']}")

    async def _sleep_interruptible(self, total_sec: float, step_sec: float = 5.0):
        """Duerme en pasos cortos para que SIGINT/SIGTERM (self.running=False) corte la espera casi de
        inmediato, en vez de bloquear hasta pause_check_sec completo (puede ser 10 min)."""
        elapsed = 0.0
        while elapsed < total_sec and self.running:
            await asyncio.sleep(min(step_sec, total_sec - elapsed))
            elapsed += step_sec

    async def _run_one_cycle(self) -> bool:
        """Un ciclo completo (lote -> ráfaga -> cooldown). Devuelve False si el daemon debe detenerse
        (segmento agotado, o no es --daemon y ya no queda cola), True para continuar en el while de run()."""
        # 1. Obtener lote de candidatos desde SQLite
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        rows = []
        if self.estados:
            quotas = parse_estados_quotas(self.estados)
            for edo, q in quotas.items():
                sql, params = build_segment_query(
                    estado=edo,
                    min_credito=self.min_credito,
                    born_after=self.born_after,
                    prioridad=self.prioridad,
                    limit=q
                )
                sub_rows = conn.execute(sql, params).fetchall()
                rows.extend(sub_rows)
                print(f"  --> {edo}: {len(sub_rows)}/{q} registros cargados")
        else:
            sql, params = build_segment_query(
                estado=self.estado,
                min_credito=self.min_credito,
                born_after=self.born_after,
                prioridad=self.prioridad,
                limit=self.limit
            )
            rows = conn.execute(sql, params).fetchall()
        conn.close()

        if not rows:
            print("[✓] No hay más registros pendientes en este segmento.")
            self.stats["state"] = "COMPLETED"
            self._write_status_file()
            return False

        print(f"\n[🚀] Lote de {len(rows)} registros obtenido. Iniciando ráfaga ({self.burst_sec/60:.1f} min)...")
        t_burst_start = time.time()
        self.stats["state"] = "BURST"

        # Cola de registros para la ráfaga
        queue_records = asyncio.Queue()
        for r in rows:
            queue_records.put_nowait(r)

        consecutive_proxy_errors = 0

        # Worker individual
        async def worker_loop(w_idx: int):
            nonlocal consecutive_proxy_errors
            while not queue_records.empty() and self.running:
                # Verificar tiempo de ráfaga
                if time.time() - t_burst_start >= self.burst_sec:
                    break

                # Circuit Breaker: si hay 3 fallas de proxy seguidas, pausar
                if consecutive_proxy_errors >= 3:
                    await asyncio.sleep(5)
                    continue

                r = await queue_records.get()
                rec = {
                    "id": r[0],
                    "u6acct": r[1],
                    "curp": r[2],
                    "u6rfc": r[3],
                    "dmname": r[4],
                    "estado": r[5],
                    "ciudad": r[6],
                    "codigo_postal": r[7],
                    "u6licrea": r[8],
                    "fecha_nacimiento": r[9],
                    "genero": r[10],
                    "u6ladte1": r[11],
                    "u6tel1": r[12],
                    "dmaddr1": r[13],
                    "dmaddr2": r[14]
                }
                rid = rec["id"]
                curp = rec["curp"]
                name = rec["dmname"]
                lim = rec["u6licrea"]

                # Obtener proxy residencial fresco (ver santander_runner.get_default_residential_proxy)
                #
                # Con --sin-proxy NO se pide ninguno: se corre directo desde la IP
                # de la maquina. Hace falta porque proxy001 ahora rechaza la cuenta
                # (403/431) y el proxy-gate vive en una VPS inaccesible.
                if self.use_proxy:
                    try:
                        proxy_dict = fetch_proxy_from_gate()
                    except Exception:
                        proxy_dict = None
                    if not proxy_dict:
                        consecutive_proxy_errors += 1
                        await asyncio.sleep(4.0)
                        queue_records.put_nowait(r)
                        queue_records.task_done()
                        continue
                else:
                    proxy_dict = None

                consecutive_proxy_errors = max(0, consecutive_proxy_errors - 1)

                # Ejecutar check canónico con proxy residencial
                res = await execute_curp_check(curp, proxy=proxy_dict,
                                           state=rec.get("estado"),
                                           use_proxy=self.use_proxy)
                status = res.get("status")
                detail = res.get("detail", "")
                dur = res.get("time", 0)

                if status == "ON":
                    # Verificación de existencia: meter los 16 dígitos de la tarjeta en el login web
                    # para confirmar que el cliente sigue activo. Si da 401, se descarta (no entra a la bóveda).
                    card_digits = "".join(c for c in (rec.get("u6acct") or "") if c.isdigit())
                    if len(card_digits) >= 16:
                        card_res = await asyncio.to_thread(check_card_existence, card_digits[:16], proxy=proxy_dict)
                        card_status = card_res.get("status", "ERROR")
                        card_detail = card_res.get("detail", "")
                        if card_status == "INACTIVE":
                            self.stats["offs"] += 1
                            self.stats["total_processed"] += 1
                            self.writer.enqueue(rec, f"OFF: tarjeta inactiva ({card_detail})", is_green=False)
                            print(f"  [🔴 CARD INACTIVE] ID:{rid} | {curp} | tarjeta {card_digits[:16][-4:]}... | {card_detail} ({dur}s)", flush=True)
                            queue_records.task_done()
                            continue
                        elif card_status == "ERROR":
                            print(f"  [⚠️ CARD ERROR] ID:{rid} | {curp} | {card_detail} — no se quema lead", flush=True)
                            queue_records.task_done()
                            continue
                        # ACTIVE → proceder a guardar como HIT
                    self.stats["hits"] += 1
                    self.stats["total_processed"] += 1
                    self.writer.enqueue(rec, "HIT", is_green=True)
                    print(f"  [🟢 HIT #{self.stats['hits']}] ID:{rid} | {curp} | {name} | ${lim} | ({dur}s)", flush=True)
                elif status == "OFF":
                    self.stats["offs"] += 1
                    self.stats["total_processed"] += 1
                    short_detail = f"OFF: {detail[:20]}"
                    self.writer.enqueue(rec, short_detail, is_green=False)
                    print(f"  [🔴 OFF] ID:{rid} | {curp} | {detail} ({dur}s)", flush=True)
                else:
                    # RETRY: No quemar lead, no escribir en BD
                    self.stats["retries"] += 1
                    print(f"  [⚠️ RETRY] ID:{rid} | {curp} | {detail}", flush=True)
                    # CIRCUIT BREAKER.
                    #
                    # Antes: RETRY solo contaba y el ciclo seguia. Medido: con
                    # el proxy caido (CONNECT tunnel failed) el daemon hizo
                    # 9,611 reintentos seguidos en ~1 hora, cero resultados, y
                    # el tramo >= $484k no avanzo NADA en ese tiempo. Cuatro
                    # workers gastados en llamadas que no pueden funcionar.
                    #
                    # Ahora: N reintentos seguidos sin un solo resultado real
                    # significa que la infraestructura esta caida, no que el
                    # registro sea malo. Se para la rafaga y se aborta, para
                    # que quien lo supervise lo vea en vez de quemarlo.
                    if (self.stats["retries"] >= RETRY_CIRCUIT_LIMIT
                            and self.stats["total_processed"] == 0):
                        self._circuit_tripped = True
                        print(f"  [🚫 CIRCUITO] {RETRY_CIRCUIT_LIMIT} reintentos "
                              f"seguidos sin un solo resultado -> infraestructura "
                              f"caida. Se aborta la rafaga.", flush=True)
                        break

                queue_records.task_done()

        # Lanzar workers paralelos
        tasks = [asyncio.create_task(worker_loop(i)) for i in range(self.workers)]

        # Monitor de progreso en ráfaga
        while any(not t.done() for t in tasks):
            # El circuito se disparó: la infraestructura está caída. No tiene
            # sentido seguir al monitor hasta que expire la ráfaga.
            if self._circuit_tripped:
                break
            elapsed = time.time() - t_burst_start
            remain = max(0.0, self.burst_sec - elapsed)
            if elapsed > 0:
                self.stats["rate_per_min"] = round((self.stats["total_processed"] / elapsed) * 60, 1)
            self._write_status_file({"burst_remaining_sec": round(remain, 1)})

            if remain <= 0:
                break
            await asyncio.sleep(3.0)

        # Cancelar y esperar terminación de workers
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        # 3. Fase de Enfriamiento (Cooldown) y Limpieza de Huérfanos
        if self._circuit_tripped:
            # Infraestructura caída: volver False detiene el daemon. Sin esto
            # entraba al cooldown y al siguiente ciclo repetía el bucle.
            print("[🚫] Circuito abierto: se detiene el daemon para no "
                  "quemar más cuota. Revisar el proxy antes de relanzar.",
                  flush=True)
            self.running = False
            self._write_status_file({"state": "CIRCUIT_OPEN"})
            return False

        if not self.daemon_mode and queue_records.empty():
            return False

        self.stats["state"] = "COOLDOWN"
        print(f"\n[❄️] Ráfaga concluida. Enfriando sockets por {self.cooldown_sec:.0f}s...")

        # Zombie Watchdog
        if os.name == 'posix':
            try:
                import subprocess
                subprocess.run(["pkill", "-f", "chromium.*--headless"], check=False)
            except Exception:
                pass

        t_cool_start = time.time()
        while time.time() - t_cool_start < self.cooldown_sec and self.running:
            cool_remain = max(0.0, self.cooldown_sec - (time.time() - t_cool_start))
            self._write_status_file({"cooldown_remaining_sec": round(cool_remain, 1)})
            await asyncio.sleep(2.0)

        return True

        self.writer.close()
        self.stats["state"] = "STOPPED"
        self._write_status_file()
        print(f"\n[🏁] Sesión finalizada | Total procesados: {self.stats['total_processed']} | HITS: {self.stats['hits']} | OFF: {self.stats['offs']}")


# ==============================================================================
# 6. ENTRADA PRINCIPAL CLI
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="SantaBase — Motor de Depuración Segmentada de Alta Velocidad")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Ruta a la base de datos santander.db")
    parser.add_argument("--estado", default=None, help="Filtrar por un estado canónico único (ej. 'CIUDAD DE MEXICO')")
    parser.add_argument("--estados", default=None, help="Lote multi-estado con cuotas (ej. 'DURANGO:250,CIUDAD DE MEXICO:250')")
    parser.add_argument("--min-credito", type=int, default=0, help="Límite de crédito mínimo en pesos")
    parser.add_argument("--born-after", default=BORN_AFTER_DEFAULT, help="Fecha de nacimiento mínima YYYY-MM-DD (default: '%s', excluye 1962 y anteriores)" % BORN_AFTER_DEFAULT)
    parser.add_argument("--prioridad", choices=["credito_desc", "edad_desc", "mixto"], default="credito_desc", help="Criterio de ordenación")
    parser.add_argument("--limit", type=int, default=100, help="Cantidad de registros a procesar por ráfaga")
    parser.add_argument("--workers", type=int, default=5, help="Cantidad de navegadores paralelos (default: 5)")
    parser.add_argument("--burst-min", type=float, default=3.5, help="Duración de la ráfaga activa en minutos")
    parser.add_argument("--cooldown-min", type=float, default=1.5, help="Duración del enfriamiento en minutos")
    parser.add_argument("--daemon", action="store_true", help="Modo continuo desatendido (repite ráfagas indefinidamente)")
    parser.add_argument("--hits-pool-max", type=int, default=12, help="Pausa el purger si hay >= esto de hits work_status=ACTIVE sin trabajar (no quema cuota de proxy de más)")
    parser.add_argument("--hits-pool-resume", type=int, default=10, help="Retoma solo cuando el pool de hits sin trabajar baja a esto o menos")
    parser.add_argument("--pause-check-min", type=float, default=1.0, help="Cada cuánto re-checa el pool mientras está pausado (minutos)")
    parser.add_argument("--status", action="store_true", help="Consulta el estado actual de purger_status.json y sale")
    parser.add_argument("--sin-proxy", dest="use_proxy", action="store_false",
                        help="Corre DIRECTO desde la IP de esta maquina, sin proxy residencial. "
                             "Hace falta cuando proxy001 rechaza la cuenta (403/431) o el proxy-gate "
                             "esta caido. Riesgo: Santander puede bloquear esta IP.")
    
    args = parser.parse_args()
    
    if args.status:
        if os.path.exists(STATUS_JSON_PATH):
            with open(STATUS_JSON_PATH, "r", encoding="utf-8") as f:
                print(f.read())
        else:
            print("No hay telemetría activa en purger_status.json")
        return

    daemon = SegmentedPurgerDaemon(
        db_path=args.db_path,
        estado=args.estado,
        estados=args.estados,
        min_credito=args.min_credito,
        born_after=args.born_after,
        prioridad=args.prioridad,
        limit=args.limit,
        workers=args.workers,
        burst_sec=args.burst_min * 60,
        cooldown_sec=args.cooldown_min * 60,
        daemon_mode=args.daemon,
        hits_pool_max=args.hits_pool_max,
        hits_pool_resume=args.hits_pool_resume,
        pause_check_sec=args.pause_check_min * 60,
        use_proxy=args.use_proxy
    )
    
    # Manejo de señales de parada limpia
    def handle_signal(sig, frame):
        print("\n[!] Señal de interrupción recibida. Finalizando limpiamente...")
        daemon.running = False
        
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    asyncio.run(daemon.run())

if __name__ == "__main__":
    main()
