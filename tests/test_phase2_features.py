import os
import pytest
from fastapi.testclient import TestClient

os.environ["SANTANDER_PASSWORD"] = "Santabase"
os.environ["SANTANDER_SECRET"] = "test-secret"

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app

client = TestClient(app)

def test_phase2_enhancements():
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    # 1. Branding SANTA 🙏🏻 BASE en Lock Screen y Top Bar
    assert 'class="brand-santa">SANTA</span>' in html
    assert 'class="brand-base">BASE</span>' in html

    # 2. Buscador con atajo Ctrl+K y botón de limpieza instantánea
    assert 'class="search-input-wrap"' in html
    assert 'id="btn-clear-search"' in html
    assert 'clearGlobalSearch()' in html
    assert 'toggleSearchClearBtn()' in html
    assert '(Ctrl+K)' in html

    # 3. Menú contextual enriquecido con atajos y soporte de rangos
    assert 'class="ctx-header">Acciones Rápidas</div>' in html
    assert 'id="ctx-range-item"' in html
    assert 'id="ctx-range-badge"' in html
    assert 'class="ctx-shortcut">Ctrl+C</span>' in html
    assert 'class="ctx-shortcut">Ctrl+V</span>' in html

    # 4. Reglas de Responsive Design (Zero Overlaps)
    assert '@media (max-width: 1280px)' in html
    assert '@media (max-width: 1050px)' in html
