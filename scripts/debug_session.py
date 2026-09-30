import time
import random
import json
from curl_cffi import requests

sid = random.randint(10000000, 99999999)
p = f"http://santabase1_custom_zone_MX_ssid_{sid}_time_10:Santabase123@us.proxy001.com:7878"

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-419,es;q=0.9",
    "Referer": "https://onboarding.santander.com.mx/cuenta-digital-lite/personal-data",
    "Origin": "https://onboarding.santander.com.mx",
    "Content-Type": "application/json"
}

proxies = {"http": p, "https": p}
s = requests.Session(impersonate="chrome120", proxies=proxies)

t0 = time.time()
print(f"Testing with sid={sid}...")
try:
    r1 = s.get("https://onboarding.santander.com.mx/api/v1/obu/N2/multitask/session/init", headers=headers, timeout=15)
    print(f"r1: {r1.status_code} ({time.time()-t0:.2f}s)")
    print(f"r1 cookies: {dict(s.cookies)}")
    print(f"r1 body: {r1.text[:150]}")
    
    t1 = time.time()
    r2 = s.post(
        "https://onboarding.santander.com.mx/api/v1/obu/N2/multitask/agreements/accept",
        headers=headers,
        json={"data": {"privacy": True, "termsAndConditions": True, "originFlow": "/cuenta-digital-lite/personal-data"}},
        timeout=15
    )
    print(f"r2: {r2.status_code} ({time.time()-t1:.2f}s)")
    
    t2 = time.time()
    r3 = s.post(
        "https://onboarding.santander.com.mx/api/v1/obu/N2/multitask/curp/consulta",
        headers=headers,
        json={"data": {"birthCountry": "052", "mainPersonalIdentifier": "GUPP790601HJCTDD07"}},
        timeout=15
    )
    print(f"r3: {r3.status_code} ({time.time()-t2:.2f}s)")
    print(f"r3 body: {r3.text[:150]}")

    t3 = time.time()
    r4 = s.post(
        "https://onboarding.santander.com.mx/api/v1/obu/case/registrada/N2/preexistence/validar",
        headers=headers,
        json={
            "data": {
                "state": "JALISCO",
                "os": "Android",
                "deviceVersion": "Android Google Pixel 9 15",
                "browserSize": "400x850",
                "resolutionScreen": "800x1700",
                "latitude": "20.659",
                "longitude": "-103.349"
            }
        },
        timeout=25
    )
    print(f"r4: {r4.status_code} ({time.time()-t3:.2f}s)")
    print(f"r4 body: {r4.text[:200]}")
    print(f"Total time: {time.time()-t0:.2f}s")
except Exception as e:
    print(f"Error after {time.time()-t0:.2f}s: {e}")
finally:
    s.close()
