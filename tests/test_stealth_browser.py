"""Tests de las funciones puras del Stealth Mobile Browser (sin abrir ventanas ni navegador —
esas requieren display/Chrome y se validan manualmente, ver scripts/stealth_browser/README.md)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "stealth_browser"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "launch_mobile_browser",
    os.path.join(os.path.dirname(__file__), "..", "scripts", "stealth_browser", "launch_mobile_browser.py"),
)
lmb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lmb)


def test_parse_proxy_host_port_user_pass():
    p = lmb.parse_proxy("us.proxy001.com:7878:santabase1_custom_zone_MX_ssid_123:Santabase123")
    assert p["host"] == "us.proxy001.com"
    assert p["port"] == 7878
    assert p["username"] == "santabase1_custom_zone_MX_ssid_123"
    assert p["password"] == "Santabase123"
    assert p["server"] == "http://us.proxy001.com:7878"


def test_parse_proxy_user_pass_at_host():
    p = lmb.parse_proxy("user:pass@1.2.3.4:9999")
    assert p["host"] == "1.2.3.4"
    assert p["port"] == 9999
    assert p["username"] == "user"
    assert p["password"] == "pass"


def test_parse_proxy_empty_returns_empty_dict():
    assert lmb.parse_proxy("") == {}
    assert lmb.parse_proxy("   ") == {}


def test_parse_proxy_password_with_colons_preserved():
    # La password puede traer ":" (ej. bases64-like); no debe truncarse en el primer ":".
    p = lmb.parse_proxy("host:1234:user:pa:ss:word")
    assert p["password"] == "pa:ss:word"


def test_normalize_estado_strips_accents_and_case():
    assert lmb.normalize_estado("Jalísco") == "jalisco"
    assert lmb.normalize_estado("  CIUDAD DE MÉXICO ") == "ciudad de mexico"
    assert lmb.normalize_estado("") == ""
    assert lmb.normalize_estado(None) == ""


def test_lookup_region_coords_matches_known_state():
    loc = lmb.lookup_region_coords("JALISCO")
    assert loc is not None
    assert loc["region"] == "Jalisco"

    loc2 = lmb.lookup_region_coords("Ciudad de México")
    assert loc2 is not None
    assert loc2["region"] == "CDMX"


def test_lookup_region_coords_unknown_returns_none():
    assert lmb.lookup_region_coords("Marte") is None
    assert lmb.lookup_region_coords("") is None


def test_get_proxy_location_prefers_region_hint_match():
    proxy = {"username": "santabase1_region_jalisco_ssid_123"}
    loc = lmb.get_proxy_location(proxy, region_hint="Jalisco")
    assert loc["region"] == "Jalisco"
    assert loc["matched_hint"] is True


def test_get_proxy_location_falls_back_to_oaxaca_when_no_match():
    proxy = {"username": "some_generic_username_no_region"}
    loc = lmb.get_proxy_location(proxy, region_hint="Jalisco")
    assert loc["region"] == "Oaxaca"
    assert loc["matched_hint"] is False


def test_proxy_manager_caps_at_10_and_keeps_active():
    mgr = lmb.ProxyManager([f"host{i}.com:1000:user:pass" for i in range(10)])
    assert len(mgr.proxies) == 10
    mgr.set_index(9)  # activo el ultimo
    added = mgr.add_and_select("nuevo.com:2000:u:p")
    assert added is not None
    assert len(mgr.proxies) == 10  # nunca crece mas de 10
    assert mgr.get_current()["host"] == "nuevo.com"  # el nuevo queda activo
    # el que estaba activo (host9.com) se preserva, se descarta uno viejo no-activo
    hosts = [p["host"] for p in mgr.proxies]
    assert "host9.com" in hosts


def test_proxy_manager_direct_mode_returns_none():
    mgr = lmb.ProxyManager(["host.com:1000:u:p"], direct_mode=True)
    assert mgr.get_current() is None


def test_proxy_manager_add_invalid_returns_none_and_does_not_corrupt_state():
    mgr = lmb.ProxyManager(["host.com:1000:u:p"])
    before = list(mgr.proxies)
    result = mgr.add_and_select("")
    assert result is None
    assert mgr.proxies == before  # no se corrompe la lista con un input vacio/invalido


def test_parse_cli_args_flags():
    old_argv = sys.argv
    try:
        sys.argv = ["prog", "--curp=OIRM840921HDFRMR05", "--estado=JALISCO", "--operator-estado=Jalisco"]
        args = lmb._parse_cli_args()
        assert args["curp"] == "OIRM840921HDFRMR05"
        assert args["estado"] == "JALISCO"
        assert args["operator_estado"] == "Jalisco"
    finally:
        sys.argv = old_argv


def test_parse_cli_args_uri_scheme():
    old_argv = sys.argv
    try:
        sys.argv = ["prog", "santabase-stealth://open?curp=OIRM840921HDFRMR05&estado=Durango"]
        args = lmb._parse_cli_args()
        assert args["curp"] == "OIRM840921HDFRMR05"
        assert args["estado"] == "Durango"
    finally:
        sys.argv = old_argv


def test_parse_cli_args_malformed_uri_does_not_crash():
    old_argv = sys.argv
    try:
        sys.argv = ["prog", "santabase-stealth://%%%invalid%%%"]
        args = lmb._parse_cli_args()  # no debe lanzar excepcion
        assert args["curp"] is None
    finally:
        sys.argv = old_argv


def test_parse_cli_args_no_args_returns_all_none():
    old_argv = sys.argv
    try:
        sys.argv = ["prog"]
        args = lmb._parse_cli_args()
        assert args == {"curp": None, "estado": None, "operator_estado": None}
    finally:
        sys.argv = old_argv
