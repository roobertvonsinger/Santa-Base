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
    res = client.post("/api/auth/login", json={"password": "WrongPassword"})
    assert res.status_code == 401

def test_login_success():
    res = client.post("/api/auth/login", json={"password": AUTH_PASSWORD})
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert "token" in res.json()

def test_root_html_page():
    res = client.get("/")
    assert res.status_code == 200
    assert "Santander DB" in res.text
    assert "col-resizer" in res.text
    assert "rfc-date" in res.text
