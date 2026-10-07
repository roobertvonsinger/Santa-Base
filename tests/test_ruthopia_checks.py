import os
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app, AUTH_PASSWORD, ACTIVE_CHECKS, USER_CHECK_HISTORY
from santander_runner import format_short_reason

client = TestClient(app)

def test_format_short_reason_mappings():
    assert format_short_reason("No cumple requisitos (Modal PE1002)") == "PE1002"
    assert format_short_reason("Contacto preexistente (/confirm-contact)") == "Reg. previo"
    assert format_short_reason("Derivación LikeU Pro (/derivation-pro)") == "LikeU Pro"
    assert format_short_reason("Rechazo en pantalla (Sucursal)") == "Sucursal"
    assert format_short_reason("Timeout en confirm-data") == "Timeout"
    assert format_short_reason("Fallo desconocido") == "Fallo desconoci"
    assert format_short_reason("") == "Rechazo"

def test_operator_concurrency_limit():
    # Login as Magdiel (operator)
    res_login = client.post("/api/auth/login", json={"username": "Magdiel", "password": AUTH_PASSWORD})
    assert res_login.status_code == 200
    token = res_login.json()["token"]
    
    # Simulate Magdiel already having 3 checks active
    ACTIVE_CHECKS["Magdiel"] = 3
    try:
        res = client.post(
            "/api/check_curp",
            json={"curp": "GOMA800101HDFRRN01"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 429
        assert "Límite alcanzado: Máximo 3 verificaciones simultáneas" in res.json()["detail"]
    finally:
        ACTIVE_CHECKS["Magdiel"] = 0

def test_superadmin_bypasses_operator_concurrency():
    # Login as Robertvs (superadmin)
    res_login = client.post("/api/auth/login", json={"username": "Robertvs", "password": AUTH_PASSWORD})
    assert res_login.status_code == 200
    token = res_login.json()["token"]
    
    # Simulate Robertvs having 3 checks active
    ACTIVE_CHECKS["Robertvs"] = 3
    try:
        with patch("app.check_single_curp", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"curp": "GOMA800101HDFRRN01", "status": "ON", "detail": "Elegible"}
            res = client.post(
                "/api/check_curp",
                json={"curp": "GOMA800101HDFRRN01"},
                headers={"Authorization": f"Bearer {token}"}
            )
            # Superadmin is NOT blocked by 429
            assert res.status_code == 200
            assert res.json()["status"] == "ON"
    finally:
        ACTIVE_CHECKS["Robertvs"] = 0

def test_ui_has_glimmer_check_and_no_desktop_redirect():
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    
    # Verify the check button with glimmer and contour exists
    assert "btn-check-curp" in html
    assert "checkGlimmerSweep" in html
    assert "btn-check-retry" in html
    
    # Verify Ruthopia short reasons logic is in the script
    assert "formatShortReason" in html
    assert "isNegativeResult" in html
    assert "Reg. previo" in html
    assert "PE1002" in html
    
    # Verify NO external desktop tab redirect anchor to Santander onboarding
    assert '<a href="https://onboarding.santander.com.mx' not in html

def test_age_filter_1963_in_sql():
    # Verify that the query construction in app.py strictly excludes birth years before 1963 (18 to 63 years old in 2026)
    with open("app.py", "r", encoding="utf-8") as f:
        code = f.read()
    assert "SUBSTR(u6rfc, 5, 2) >= '63' OR SUBSTR(u6rfc, 5, 2) <= '08'" in code
