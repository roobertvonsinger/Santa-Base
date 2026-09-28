import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

# Set testing environment
os.environ["SANTANDER_PASSWORD"] = "Santabase"
os.environ["SANTANDER_SECRET"] = "test-secret"

# Import app from root
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, AUTH_PASSWORD, get_db_connection

client = TestClient(app)

def test_auth_status_unauthenticated():
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    assert res.json() == {"authenticated": False}

def test_login_invalid_password():
    res = client.post("/api/auth/login", json={"username": "Robertvs", "password": "WrongPassword"})
    assert res.status_code == 401

def test_login_success():
    res = client.post("/api/auth/login", json={"username": "Robertvs", "password": AUTH_PASSWORD})
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert "token" in res.json()

def test_root_html_page():
    res = client.get("/")
    assert res.status_code == 200
    assert "Santander DB" in res.text
    assert "col-resizer" in res.text
    assert "rfc-date" in res.text

def test_get_records_with_db_columns():
    # Verify that get_records runs without NameError (DB_COLUMNS defined)
    login_res = client.post("/api/auth/login", json={"username": "Robertvs", "password": AUTH_PASSWORD})
    token = login_res.json()["token"]
    client.cookies.set("santabase_session", token)
    res = client.get("/api/records?limit=50")
    assert res.status_code == 200
    data = res.json()
    assert "records" in data
    assert "total" in data
