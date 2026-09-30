import pytest
import sqlite3
import tempfile
import os
import time

def test_query_builder():
    from santander_purger import build_segment_query
    
    # 1. Filtro básico por estado y orden de crédito
    sql, params = build_segment_query(
        estado="CIUDAD DE MEXICO",
        min_credito=50000,
        born_after="1985-01-01",
        prioridad="credito_desc",
        limit=100
    )
    assert "FROM santander_records" in sql
    assert "UPPER(estado) = UPPER(?)" in sql
    assert "curp IS NOT NULL" in sql
    assert "results IS NULL" in sql
    assert "CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER) >= ?" in sql
    assert "fecha_nacimiento >= ?" in sql
    assert "ORDER BY CAST(REPLACE(REPLACE(COALESCE(u6licrea, '0'), '$', ''), ',', '') AS INTEGER) DESC" in sql
    assert params == ["CIUDAD DE MEXICO", 50000, "1985-01-01", 100]

def test_query_builder_edad():
    from santander_purger import build_segment_query
    
    sql, params = build_segment_query(
        estado="JALISCO",
        min_credito=0,
        born_after=None,
        prioridad="edad_desc",
        limit=50
    )
    assert "UPPER(estado) = UPPER(?)" in sql
    assert "ORDER BY fecha_nacimiento DESC" in sql
    assert params == ["JALISCO", 50]

def test_parse_multistate_arg():
    from santander_purger import parse_estados_quotas
    
    quotas = parse_estados_quotas("DURANGO:250,CIUDAD DE MEXICO:250")
    assert quotas == {"DURANGO": 250, "CIUDAD DE MEXICO": 250}
    
    quotas2 = parse_estados_quotas("DURANGO,CDMX")
    assert quotas2 == {"DURANGO": 100, "CDMX": 100}

def test_parse_proxy_string_formats():
    from santander_purger import parse_proxy_endpoint
    
    # Formato 1: http://host:port:user:pass
    data1 = {
        "provider": "nodemaven",
        "proxy": "http://gate.nodemaven.com:8080:RuthopiaRvs-country-mx:RuthGates"
    }
    p1 = parse_proxy_endpoint(data1)
    assert p1["server"] == "http://gate.nodemaven.com:8080"
    assert p1["username"] == "RuthopiaRvs-country-mx"
    assert p1["password"] == "RuthGates"

    # Formato 2: http://user:pass@host:port
    data2 = {
        "provider": "litport",
        "proxy": "http://myuser:mypass@1.2.3.4:9999"
    }
    p2 = parse_proxy_endpoint(data2)
    assert p2["server"] == "http://1.2.3.4:9999"
    assert p2["username"] == "myuser"
    assert p2["password"] == "mypass"

def test_sqlite_batch_writer_with_hits():
    from santander_purger import SqliteBatchWriter
    
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE santander_records (
                id INTEGER PRIMARY KEY,
                u6acct TEXT,
                curp TEXT,
                u6rfc TEXT,
                dmname TEXT,
                estado TEXT,
                ciudad TEXT,
                codigo_postal TEXT,
                u6licrea TEXT,
                fecha_nacimiento TEXT,
                genero TEXT,
                u6ladte1 TEXT,
                u6tel1 TEXT,
                dmaddr1 TEXT,
                dmaddr2 TEXT,
                results TEXT
            );
        """)
        conn.execute("""
            INSERT INTO santander_records VALUES 
            (1, '41523134', 'CURP01', 'RFC01', 'JUAN PEREZ', 'DURANGO', 'DURANGO', '34000', '$50,000', '1990-01-01', 'H', '618', '1234567', 'CALLE 1', 'COL 1', NULL),
            (2, '41523135', 'CURP02', 'RFC02', 'ANA GOMEZ', 'CIUDAD DE MEXICO', 'CDMX', '06000', '$20,000', '1988-05-10', 'M', '55', '9876543', 'CALLE 2', 'COL 2', NULL);
        """)
        conn.commit()
        conn.close()
        
        writer = SqliteBatchWriter(path)
        writer.start()
        
        rec1 = {
            "id": 1,
            "u6acct": "41523134",
            "curp": "CURP01",
            "u6rfc": "RFC01",
            "dmname": "JUAN PEREZ",
            "estado": "DURANGO",
            "ciudad": "DURANGO",
            "codigo_postal": "34000",
            "u6licrea": "$50,000",
            "fecha_nacimiento": "1990-01-01",
            "genero": "H",
            "telefono": "618 1234567",
            "direccion": "CALLE 1 COL 1"
        }
        
        # HIT (Verde) debe escribirse de inmediato en santander_hits con work_status='NUEVO'
        writer.enqueue(record_dict=rec1, result="HIT", is_green=True)
        time.sleep(0.1) # Breve tiempo para flush
        
        # OFF (Descarte)
        rec2 = {"id": 2, "curp": "CURP02"}
        writer.enqueue(record_dict=rec2, result="OFF: PE1002", is_green=False)
        
        writer.close()
        
        # Verificar resultados en santander_records y santander_hits
        conn = sqlite3.connect(path)
        r1 = conn.execute("SELECT results FROM santander_records WHERE id=1").fetchone()[0]
        r2 = conn.execute("SELECT results FROM santander_records WHERE id=2").fetchone()[0]
        hit_row = conn.execute("SELECT curp, dmname, estado, telefono, work_status FROM santander_hits WHERE id=1").fetchone()
        conn.close()
        
        assert r1 == "HIT"
        assert r2 == "OFF: PE1002"
        assert hit_row == ("CURP01", "JUAN PEREZ", "DURANGO", "618 1234567", "NUEVO")
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_sqlite_batch_writer_insert_or_ignore_preserves_operator_work():
    """OR REPLACE pisaba work_status/operador/notas de un hit ya trabajado por un operador ante
    colision de id. OR IGNORE debe preservarlos."""
    from santander_purger import SqliteBatchWriter

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE santander_records (
                id INTEGER PRIMARY KEY, u6acct TEXT, curp TEXT, u6rfc TEXT, dmname TEXT,
                estado TEXT, ciudad TEXT, codigo_postal TEXT, u6licrea TEXT,
                fecha_nacimiento TEXT, genero TEXT, u6ladte1 TEXT, u6tel1 TEXT,
                dmaddr1 TEXT, dmaddr2 TEXT, results TEXT
            );
        """)
        conn.execute("INSERT INTO santander_records (id, curp, results) VALUES (1, 'CURP01', NULL)")
        # Simula un hit ya trabajado por un operador (insertado antes, fuera del writer)
        conn.execute("""
            CREATE TABLE santander_hits (
                id INTEGER PRIMARY KEY, u6acct TEXT, curp TEXT NOT NULL UNIQUE, u6rfc TEXT,
                dmname TEXT, estado TEXT, ciudad TEXT, codigo_postal TEXT, u6licrea TEXT,
                fecha_nacimiento TEXT, genero TEXT, telefono TEXT, direccion TEXT,
                work_status TEXT DEFAULT 'NUEVO', operador TEXT, notas TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            INSERT INTO santander_hits (id, curp, dmname, work_status, operador, notas)
            VALUES (1, 'CURP01', 'JUAN PEREZ', 'CERRADO', 'Luisito', 'Cliente ya contactado')
        """)
        conn.commit()
        conn.close()

        writer = SqliteBatchWriter(path)
        writer.start()
        rec = {"id": 1, "curp": "CURP01", "dmname": "JUAN PEREZ"}
        writer.enqueue(record_dict=rec, result="HIT", is_green=True)
        writer.close()

        conn = sqlite3.connect(path)
        row = conn.execute("SELECT work_status, operador, notas FROM santander_hits WHERE id=1").fetchone()
        conn.close()

        assert row == ("CERRADO", "Luisito", "Cliente ya contactado")
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_count_unworked_hits_and_pool_thresholds():
    from santander_purger import SegmentedPurgerDaemon

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE santander_hits (
                id INTEGER PRIMARY KEY, curp TEXT, work_status TEXT DEFAULT 'NUEVO'
            );
        """)
        for i in range(1, 6):
            conn.execute("INSERT INTO santander_hits (id, curp, work_status) VALUES (?, ?, 'NUEVO')", (i, f"CURP{i}"))
        for i in range(6, 9):
            conn.execute("INSERT INTO santander_hits (id, curp, work_status) VALUES (?, ?, 'CERRADO')", (i, f"CURP{i}"))
        conn.commit()
        conn.close()

        daemon = SegmentedPurgerDaemon(db_path=path, hits_pool_max=5, hits_pool_resume=2)
        # Solo cuenta work_status='NUEVO' (5), no los CERRADO (3)
        assert daemon._count_unworked_hits() == 5
        assert daemon._count_unworked_hits() >= daemon.hits_pool_max  # dispararia la pausa
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_count_unworked_hits_missing_table_returns_zero():
    from santander_purger import SegmentedPurgerDaemon

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        daemon = SegmentedPurgerDaemon(db_path=path)
        # Tabla santander_hits no existe todavia -> no debe tronar, debe devolver 0
        assert daemon._count_unworked_hits() == 0
    finally:
        if os.path.exists(path):
            os.remove(path)
