import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

# Configurar entorno de pruebas
os.environ["SANTABASE_SECRET"] = "test-secret"
os.environ["SANTANDER_SECRET"] = "test-secret"

from app import app, get_db_connection, DB_PATH, generate_session_token

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_santa.db")
    monkeypatch.setattr("app.DB_PATH", test_db)
    
    conn = sqlite3.connect(test_db)
    conn.execute("""
        CREATE TABLE santander_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            u6rfc TEXT, curp TEXT, curp_status TEXT, curp_falta TEXT, dmname TEXT,
            genero TEXT, fecha_nacimiento TEXT, ciudad TEXT, estado TEXT, codigo_postal TEXT,
            results TEXT, u6acct TEXT, u6cvereg TEXT, u6numcto TEXT, dmssnum TEXT,
            dmaddr1 TEXT, dmaddr2 TEXT, u6delomu TEXT, u6estado TEXT, dmcity TEXT,
            dmzip TEXT, u6ladte1 TEXT, u6tel1 TEXT, u6ladte2 TEXT, u6tel2 TEXT, u6licrea TEXT
        );
    """)
    conn.execute("""
        CREATE TABLE santander_hits (
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
            telefono TEXT,
            direccion TEXT,
            work_status TEXT DEFAULT 'NUEVO',
            operador TEXT,
            notas TEXT,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Insertar registros de prueba en santander_records
    conn.execute("""
        INSERT INTO santander_records (id, u6rfc, curp, dmname, estado, results, u6licrea)
        VALUES (1, 'ROVR880101XYZ', 'ROVR880101HDFR01', 'ROBERTO TEST', 'CIUDAD DE MEXICO', 'HIT', '$150,000'),
               (2, 'GOMA920512ABC', 'GOMA920512MDFR02', 'MARIA TEST', 'DURANGO', NULL, '$80,000'),
               (3, 'PEPR750304DEF', 'PEPR750304HDFR03', 'PEDRO TEST', 'DURANGO', 'OFF', '$40,000')
    """)
    
    # Insertar en santander_hits
    conn.execute("""
        INSERT INTO santander_hits (id, u6acct, curp, u6rfc, dmname, estado, ciudad, u6licrea, work_status)
        VALUES (1, '1234567812345678', 'ROVR880101HDFR01', 'ROVR880101XYZ', 'ROBERTO TEST', 'CIUDAD DE MEXICO', 'BENITO JUAREZ', '$150,000', 'NUEVO')
    """)
    conn.commit()
    conn.close()

def auth_cookies():
    token = generate_session_token("Robertvs")
    return {"santabase_session": token}

def test_api_stats_includes_hits():
    res = client.get("/api/stats", cookies=auth_cookies())
    assert res.status_code == 200
    data = res.json()
    assert data["hits_total"] == 1
    assert data["hits_nuevos"] == 1

def test_get_hits_endpoint():
    res = client.get("/api/hits", cookies=auth_cookies())
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert len(data["hits"]) == 1
    assert data["hits"][0]["curp"] == "ROVR880101HDFR01"
    assert data["hits"][0]["work_status"] == "NUEVO"
    assert data["stats"]["nuevo"] == 1

def test_patch_hit_work_status_and_notes():
    payload = {
        "work_status": "EN_GESTION",
        "notas": "Cliente interesado, contactar 5pm"
    }
    res = client.patch("/api/hits/1", json=payload, cookies=auth_cookies())
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["hit"]["work_status"] == "EN_GESTION"
    assert data["hit"]["notas"] == "Cliente interesado, contactar 5pm"
    assert data["hit"]["operador"] == "RobertVS"

def test_records_destillation_excludes_hits_by_default():
    # En /api/records, el registro id=1 (HIT) no debe aparecer por defecto
    res = client.get("/api/records", cookies=auth_cookies())
    assert res.status_code == 200
    data = res.json()
    ids = [r["id"] for r in data["records"]]
    assert 1 not in ids
    assert 2 in ids

def test_hits_export_csv():
    res = client.get("/api/hits/export", cookies=auth_cookies())
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "ROVR880101HDFR01" in res.text

def other_operator_cookies():
    token = generate_session_token("Luisito")
    return {"santabase_session": token}

def test_claim_hit_assigns_operador_and_status():
    res = client.post("/api/hits/1/claim", cookies=auth_cookies())
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["claimed"] is True
    assert data["hit"]["work_status"] == "EN_GESTION"
    assert data["hit"]["operador"] == "RobertVS"

def test_claim_hit_idempotent_for_same_operator():
    res1 = client.post("/api/hits/1/claim", cookies=auth_cookies())
    res2 = client.post("/api/hits/1/claim", cookies=auth_cookies())
    assert res1.json()["claimed"] is True
    assert res2.json()["claimed"] is True
    assert res2.json()["hit"]["operador"] == "RobertVS"

def test_claim_hit_does_not_steal_from_another_operator():
    # RobertVS lo reclama primero
    first = client.post("/api/hits/1/claim", cookies=auth_cookies())
    assert first.json()["claimed"] is True
    assert first.json()["hit"]["operador"] == "RobertVS"

    # Luisito intenta reclamar el mismo hit -> NO debe pisarlo (evita duplicar chamba)
    second = client.post("/api/hits/1/claim", cookies=other_operator_cookies())
    data = second.json()
    assert data["claimed"] is False
    assert data["hit"]["operador"] == "RobertVS"
    assert data["hit"]["work_status"] == "EN_GESTION"

def test_claim_hit_requires_auth():
    res = client.post("/api/hits/1/claim")
    assert res.status_code == 401

def test_claim_hit_404_for_missing_id():
    res = client.post("/api/hits/9999/claim", cookies=auth_cookies())
    assert res.status_code == 404
