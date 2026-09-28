import asyncio
import sys
import time
import json
import re
from playwright.async_api import async_playwright

START_URL = "https://onboarding.santander.com.mx/cuenta-digital-lite/product-page?utm_source=google-pmax&utm_medium=multi-channel&utm_campaign=MX_RCB_ACC_DEB_NA_AO_N2-PMAX_CVN_CVN_MLT_GAD_PMX_PMAX_NA_CPA&utm_content=multiple_bonif200"

async def check_single_curp(curp: str) -> dict:
    t0 = time.time()
    browser = None
    ctx = None
    pg = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-zygote",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--window-size=430,900"
                ]
            )
            try:
                ctx = await browser.new_context(
                    user_agent="Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
                    viewport={"width": 430, "height": 900},
                    geolocation={"latitude": 20.6639, "longitude": -103.359},
                    permissions=["geolocation"]
                )
                try:
                    pg = await ctx.new_page()
                    await pg.goto(START_URL, wait_until="domcontentloaded", timeout=20000)
                    
                    # Click initial 'aquí' / esperar campo
                    for _ in range(25):
                        if await pg.locator("#onb-page-main-personal-identifier").count() > 0:
                            break
                        try:
                            await pg.evaluate("document.querySelector('a.onb-link__target')?.click()")
                        except Exception:
                            pass
                        await asyncio.sleep(0.6)
                    
                    await pg.wait_for_selector("#onb-page-main-personal-identifier", timeout=15000)
                    inp = pg.locator("#onb-page-main-personal-identifier")
                    await inp.click()
                    await pg.keyboard.type(curp, delay=15)
                    await asyncio.sleep(0.3)
                    
                    # Checkbox
                    await pg.wait_for_selector(".onb-checkbox__container-check", timeout=8000)
                    await pg.evaluate("document.querySelector('.onb-checkbox__container-check')?.click()")
                    await asyncio.sleep(0.5)
                    
                    # Click real active Continuar button
                    await pg.evaluate('''() => {
                        const btns = Array.from(document.querySelectorAll('button')).filter(b => b.textContent && b.textContent.includes('Continuar'));
                        const active = btns.find(b => !b.disabled && b.offsetParent !== null) || btns[btns.length - 1];
                        if (active) active.click();
                    }''')
                    
                    # Polling results
                    for s in range(1, 35):
                        await asyncio.sleep(1)
                        try:
                            u = pg.url
                            c = await pg.content()
                        except Exception:
                            continue
                        
                        # Caso directo: Contacto preexistente
                        if "confirm-contact" in u or "Tus datos de contacto" in c:
                            return {"curp": curp, "status": "OFF", "detail": "Contacto preexistente (/confirm-contact)", "time": round(time.time()-t0, 1)}
                        
                        # Caso directo: LikeU Pro
                        if "derivation-pro" in u or "LikeU Pro" in c or "Porque eres especial" in c:
                            return {"curp": curp, "status": "OFF", "detail": "Derivación LikeU Pro (/derivation-pro)", "time": round(time.time()-t0, 1)}
                        
                        # Caso confirm-data
                        if "confirm-data" in u:
                            await pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            for _ in range(12):
                                await asyncio.sleep(0.7)
                                dis = await pg.evaluate('''() => {
                                    const btns = Array.from(document.querySelectorAll('button')).filter(b => b.textContent && b.textContent.includes('Continuar'));
                                    const active = btns.find(b => !b.disabled && b.offsetParent !== null) || btns[btns.length - 1];
                                    return active ? active.disabled : true;
                                }''')
                                if not dis:
                                    break
                            
                            await pg.evaluate('''() => {
                                const btns = Array.from(document.querySelectorAll('button')).filter(b => b.textContent && b.textContent.includes('Continuar'));
                                const active = btns.find(b => !b.disabled && b.offsetParent !== null) || btns[btns.length - 1];
                                if (active) active.click();
                            }''')
                            
                            for s2 in range(1, 15):
                                await asyncio.sleep(1)
                                try:
                                    u2 = pg.url
                                    c2 = await pg.content()
                                except Exception:
                                    continue
                                if "confirm-contact" in u2 or "Tus datos de contacto" in c2:
                                    return {"curp": curp, "status": "OFF", "detail": "Contacto preexistente (/confirm-contact)", "time": round(time.time()-t0, 1)}
                                if "derivation-pro" in u2 or "LikeU Pro" in c2 or "Porque eres especial" in c2:
                                    return {"curp": curp, "status": "OFF", "detail": "Derivación LikeU Pro", "time": round(time.time()-t0, 1)}
                                if "contact-data" in u2 or "Escribe tu celular" in c2:
                                    return {"curp": curp, "status": "ON", "detail": "Elegible: avanzó a contact-data", "time": round(time.time()-t0, 1)}
                                if "No cumples con los requisitos" in c2 or "PE1002" in c2 or "acuda a sucursal" in c2.lower():
                                    return {"curp": curp, "status": "OFF", "detail": "No cumple requisitos (Modal PE1002)", "time": round(time.time()-t0, 1)}
                            
                            if "confirm-data" not in pg.url:
                                return {"curp": curp, "status": "ON", "detail": f"Avanzó a {pg.url}", "time": round(time.time()-t0, 1)}
                            else:
                                txt = await pg.inner_text("body")
                                if "requisitos" in txt.lower() or "sucursal" in txt.lower():
                                    return {"curp": curp, "status": "OFF", "detail": "Rechazo en pantalla (Sucursal)", "time": round(time.time()-t0, 1)}
                                return {"curp": curp, "status": "OFF", "detail": "No avanzó de confirm-data", "time": round(time.time()-t0, 1)}
                        
                        if "No cumples" in c or "PE1002" in c:
                            return {"curp": curp, "status": "OFF", "detail": "Modal PE1002", "time": round(time.time()-t0, 1)}
                            
                    return {"curp": curp, "status": "OFF", "detail": "Timeout en confirm-data", "time": round(time.time()-t0, 1)}
                finally:
                    if pg:
                        try:
                            await asyncio.shield(pg.close())
                        except Exception:
                            pass
            finally:
                if ctx:
                    try:
                        await asyncio.shield(ctx.close())
                    except Exception:
                        pass
                if browser:
                    try:
                        await asyncio.shield(browser.close())
                    except Exception:
                        pass
    except Exception as ex:
        return {"curp": curp, "status": "ERROR", "detail": str(ex)[:80], "time": round(time.time()-t0, 1)}

async def run_batch(curps: list[str], concurrency: int = 3) -> list[dict]:
    queue = asyncio.Queue()
    for i, c in enumerate(curps, 1):
        queue.put_nowait((i, c))
    
    results = [None] * len(curps)
    
    async def worker():
        while not queue.empty():
            try:
                idx, curp = await queue.get()
            except Exception:
                break
            res = await check_single_curp(curp)
            results[idx - 1] = res
            queue.task_done()
    
    workers = [asyncio.create_task(worker()) for _ in range(min(concurrency, len(curps)))]
    await queue.join()
    for w in workers:
        w.cancel()
    return results

def format_markdown_table(results: list[dict]) -> str:
    lines = [
        f"**Reporte Santander ({len(results)}/{len(results)})**\n",
        "| # | CURP | Estado | Detalle | Tiempo |",
        "|:---:|:---|:---:|:---|:---:|"
    ]
    for i, r in enumerate(results, 1):
        badge = "ON ✅" if r["status"] == "ON" else f"{r['status']} ❌"
        lines.append(f"| {i} | `{r['curp']}` | **{badge}** | {r['detail']} | {r['time']}s |")
    return "\n".join(lines)

if __name__ == "__main__":
    test_curp = sys.argv[1] if len(sys.argv) > 1 else "OIRM840921HDFRMR05"
    print(f"Testing CURP: {test_curp}...", flush=True)
    res = asyncio.run(run_batch([test_curp]))
    print(format_markdown_table(res))
