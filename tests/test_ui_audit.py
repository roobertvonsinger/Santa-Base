import os
import pytest
from fastapi.testclient import TestClient

os.environ["SANTANDER_PASSWORD"] = "Santabase"
os.environ["SANTANDER_SECRET"] = "test-secret"

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app

client = TestClient(app)

def test_ui_audit_design_system_tokens():
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    
    # 1. Stack de tokens en :root
    assert "--color-primary: #0284c7;" in html
    assert "--color-danger: #ec0000;" in html
    assert "--font-size-base: 13px;" in html
    assert "--font-size-cell: 12.5px;" in html
    assert "--cell-h: 36px;" in html
    assert "--cell-pad-x: 10px;" in html
    assert "--cell-pad-y: 6px;" in html
    
    # 2. Desbloqueo Bóveda en color Primario (No rojo puro)
    assert ".btn-login {\n      width: 100%;\n      background: var(--color-primary);" in html or "background: var(--color-primary);" in html
    assert ".btn-login:hover {\n      background: var(--color-primary-hover);" in html or "var(--color-primary-hover)" in html
    
    # 3. KPI Cards con jerarquía visual (reemplazo de texto plano)
    assert 'class="kpi-card"' in html
    assert 'class="kpi-label"' in html
    assert 'class="kpi-val" id="stat-total"' in html
    assert 'class="kpi-val" id="stat-curp"' in html
    assert 'class="kpi-val" id="stat-calc"' in html
    assert 'class="kpi-val" id="stat-no-curp"' in html
    assert 'class="kpi-val" id="stat-results"' in html

    # 4. Segmented Control & 4 Clusters Toolbar
    assert 'class="filter-tabs"' in html
    assert 'class="tab-btn active"' in html
    assert 'class="btn btn-primary"' in html
    assert 'class="tb-sep"' in html

    # 5. Altura de fila y padding de respiración
    assert "height: var(--cell-h);" in html
    assert "padding: var(--cell-pad-y) var(--cell-pad-x);" in html
    
    # 6. Preservación estricta de elementos requeridos
    assert "Santander DB" in html
    assert "col-resizer" in html
    assert "rfc-date" in html
