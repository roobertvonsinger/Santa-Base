import time
import random
from curl_cffi import requests

success = 0
fail = 0
for i in range(10):
    sid = random.randint(10000000, 99999999)
    p = f"http://santabase1_custom_zone_MX_ssid_{sid}_time_10:Santabase123@us.proxy001.com:7878"
    try:
        t0 = time.time()
        r = requests.get(
            "https://onboarding.santander.com.mx/api/v1/obu/N2/multitask/session/init",
            impersonate="chrome120",
            proxies={"http": p, "https": p},
            headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://onboarding.santander.com.mx/cuenta-digital-lite/personal-data",
                "Origin": "https://onboarding.santander.com.mx"
            },
            timeout=8
        )
        print(f"[{i+1}/10] Status: {r.status_code} ({time.time()-t0:.2f}s)")
        if r.status_code == 200:
            success += 1
        else:
            fail += 1
    except Exception as e:
        print(f"[{i+1}/10] Error ({time.time()-t0:.2f}s): {str(e)[:60]}")
        fail += 1

print(f"\nResultado: {success}/10 exitosos, {fail}/10 fallidos")
