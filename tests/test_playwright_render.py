import asyncio
import os
import sys
import pytest
import uvicorn
import multiprocessing
import time
from playwright.async_api import async_playwright

os.environ["SANTANDER_PASSWORD"] = "Santabase"
os.environ["SANTANDER_SECRET"] = "test-secret"

def run_server():
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from app import app
    uvicorn.run(app, host="127.0.0.1", port=8099, log_level="warning")

@pytest.mark.anyio
async def test_ui():
    p_server = multiprocessing.Process(target=run_server, daemon=True)
    p_server.start()
    time.sleep(2)  # Wait for uvicorn to boot

    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # Intercept /api/stats and /api/records to provide high-fidelity sample data
        await page.route("**/api/stats", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"total": 4891788, "with_curp": 4120300, "without_curp": 771488, "curp_calculada": 3890200, "with_results": 14200}'
        ))

        sample_records = [
            {
                "id": 1,
                "curp": "GOMA800101HDFRRN01",
                "u6rfc": "GOMA800101XXX",
                "dmname": "GONZALEZ MARTINEZ ALEJANDRO",
                "estado": "CIUDAD DE MEXICO",
                "ciudad": "BENITO JUAREZ",
                "codigo_postal": "03100",
                "direccion": "AV INSURGENTES SUR 1234 INT 501",
                "u6licrea": "850000",
                "results": "HIT",
                "u6acct": "4915660012345678",
                "genero": "H",
                "curp_status": "calculada",
                "curp_falta": "",
                "u6tel1": "5512345678",
                "u6tel2": "5587654321",
                "u6cvereg": "001",
                "u6numcto": "987654"
            },
            {
                "id": 2,
                "curp": "",
                "u6rfc": "LOPE920512YY2",
                "dmname": "LOPEZ PEREZ MARIA ELENA",
                "estado": "JALISCO",
                "ciudad": "GUADALAJARA",
                "codigo_postal": "44100",
                "direccion": "CALLE JUAREZ 450 COL CENTRO",
                "u6licrea": "1200000",
                "results": "",
                "u6acct": "4915660098765432",
                "genero": "M",
                "curp_status": "",
                "curp_falta": "SIN_DATOS",
                "u6tel1": "3312345678",
                "u6tel2": "",
                "u6cvereg": "002",
                "u6numcto": "543210"
            }
        ]

        await page.route("**/api/records*", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=f'{{"records": {sample_records}, "total": 4891788, "page": 1, "total_pages": 24459}}'.replace("'", '"')
        ))

        page.on("console", lambda msg: print(f"[CONSOLE {msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: errors.append(str(err)))

        print("Navigating to http://127.0.0.1:8099...")
        await page.goto("http://127.0.0.1:8099")

        # Verify Lock Screen elements
        btn_login = page.locator(".btn-login")
        assert await btn_login.is_visible()
        btn_bg = await btn_login.evaluate("el => window.getComputedStyle(el).backgroundColor")
        print(f"btn-login background-color: {btn_bg}")
        assert "rgb(236, 0, 0)" in btn_bg or "rgb(236,0,0)" in btn_bg.replace(" ", "")

        # Test login
        await page.fill("#login-username", "Robertvs")
        await page.fill("#login-password", "Santabase")
        await page.click(".btn-login")
        await page.wait_for_timeout(1100)

        # Verify Lock screen is hidden
        lock_screen = page.locator("#lock-screen")
        is_hidden = await lock_screen.evaluate("el => el.classList.contains('hidden')")
        print(f"Lock screen hidden after login: {is_hidden}")
        assert is_hidden is True

        # Verify stats populated in KPI cards
        stat_total = await page.inner_text("#stat-total")
        print(f"Stat Total displayed: {stat_total}")
        assert "4,891,788" in stat_total

        # Verify row height
        first_row = page.locator("tr#row-1")
        assert await first_row.is_visible()
        row_height = await first_row.evaluate("el => el.getBoundingClientRect().height")
        print(f"Rendered row height: {row_height}px")
        assert 35.0 <= row_height <= 40.0

        # Verify cell font size
        cell = page.locator("#cell-0-0")
        cell_font = await cell.evaluate("el => window.getComputedStyle(el).fontSize")
        print(f"Cell font size: {cell_font}")
        assert cell_font in ["12.5px", "12px", "13px"]

        # Verify RFC birthdate highlighting
        rfc_date = page.locator(".rfc-date").first
        assert await rfc_date.is_visible()
        rfc_date_color = await rfc_date.evaluate("el => window.getComputedStyle(el).color")
        print(f"RFC date color: {rfc_date_color}")

        # Verify Explorer View layout and scroll container bounds
        gen_display = await page.evaluate("() => window.getComputedStyle(document.getElementById('general-view-container')).display")
        assert gen_display == "flex", f"Expected general-view-container to be flex, got {gen_display}"
        
        pag_visible = await page.evaluate('''() => {
            const pag = document.querySelector('.pagination-bar');
            if (!pag) return false;
            const r = pag.getBoundingClientRect();
            return r.top < window.innerHeight && r.bottom <= window.innerHeight;
        }''')
        assert pag_visible is True, "Pagination bar must be visible inside viewport"

        # Verify view switching maintains display: flex
        await page.click("#nav-btn-hits")
        await page.wait_for_timeout(200)
        assert await page.evaluate("() => window.getComputedStyle(document.getElementById('hits-view-container')).display") == "flex"
        assert await page.evaluate("() => window.getComputedStyle(document.getElementById('general-view-container')).display") == "none"

        await page.click("#nav-btn-general")
        await page.wait_for_timeout(200)
        assert await page.evaluate("() => window.getComputedStyle(document.getElementById('general-view-container')).display") == "flex"

        # Capture populated dashboard screenshot
        screenshot_path = "tests/dashboard_populated.png"
        await page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")

        await browser.close()
    
    p_server.terminate()
    if errors:
        print(f"Page errors: {errors}")
        sys.exit(1)
    print("ALL PLAYWRIGHT TESTS PASSED WITH POPULATED DATA!")

if __name__ == "__main__":
    asyncio.run(test_ui())
