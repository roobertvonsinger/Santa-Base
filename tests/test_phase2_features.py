import os
import pytest
from fastapi.testclient import TestClient

os.environ["SANTANDER_PASSWORD"] = "Santabase"
os.environ["SANTANDER_SECRET"] = "test-secret"

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, DEFAULT_PASSWORDS

client = TestClient(app)

def test_phase2_enhancements():
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    # 1. Branding SANTA 🙏🏻 BASE en Lock Screen y Top Bar (Unified Logo)
    assert 'brand-santa' in html
    assert 'brand-base' in html
    assert 'santa-brand-logo' in html

    # 2. Mega-Buscador con atajo Ctrl+K, badge de filtro y botón de limpieza instantánea
    assert 'mega-search-bar' in html
    assert 'id="mega-filter-badge"' in html
    assert 'id="btn-clear-search"' in html
    assert 'clearGlobalSearch()' in html
    assert 'toggleSearchClearBtn()' in html
    assert 'Ctrl+K' in html

    # 3. Menú contextual enriquecido con atajos y soporte de rangos
    assert 'class="ctx-header">Acciones Rápidas</div>' in html
    assert 'id="ctx-range-item"' in html
    assert 'id="ctx-range-badge"' in html
    assert 'class="ctx-shortcut">Ctrl+C</span>' in html
    assert 'class="ctx-shortcut">Ctrl+V</span>' in html

    # 4. Reglas de Responsive Design (Zero Overlaps)
    assert '@media (max-width: 1280px)' in html
    assert '@media (max-width: 1050px)' in html

    # 5. Lock screen: input de texto estricto sin menú desplegable select
    assert '<input type="text" id="login-username"' in html
    assert '<select id="login-username"' not in html

def test_santabase_routing_and_redirects():
    # Canonical /santabase
    res = client.get("/santabase")
    assert res.status_code == 200
    assert "SANTA" in res.text

    # Legacy /santander redirect 302
    res_redir = client.get("/santander", follow_redirects=False)
    assert res_redir.status_code == 302
    assert res_redir.headers["location"] == "/santabase"

def test_rbac_botmex_multiuser_auth():
    # 1. Superadmin (Robertvs)
    res = client.post("/api/auth/login", json={"username": "Robertvs", "password": "Santabase"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["user"]["username"] == "Robertvs"
    assert data["user"]["role"] == "superadmin"

    # 2. Operador (Magdiel)
    res_mag = client.post("/api/auth/login", json={"username": "Magdiel", "password": "Santabase"})
    assert res_mag.status_code == 200
    assert res_mag.json()["user"]["role"] == "operator"

    # 3. Operador (Luisito)
    res_lui = client.post("/api/auth/login", json={"username": "Luisito", "password": "Santabase"})
    assert res_lui.status_code == 200
    assert res_lui.json()["user"]["role"] == "operator"

    # 4. Validación estricta: primer letra minúscula debe RECHAZARSE
    res_lower = client.post("/api/auth/login", json={"username": "robertvs", "password": "Santabase"})
    assert res_lower.status_code == 400
    assert "primera letra" in res_lower.json()["detail"].lower()

    # 5. Usuario desconocido rechazado
    res_fake = client.post("/api/auth/login", json={"username": "Hacker", "password": "any"})
    assert res_fake.status_code == 401

def test_security_directory_traversal_blocked():
    # Test directory traversal attacks
    res = client.get("/santabase/../../etc/passwd")
    assert res.status_code in (400, 404)
