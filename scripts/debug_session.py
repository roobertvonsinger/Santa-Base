import sys
import time
import random
import json
from curl_cffi import requests

curp_test = sys.argv[1] if len(sys.argv) > 1 else "GUPP790601HJCTDD07"
state_test = sys.argv[2] if len(sys.argv) > 2 else "JALISCO"

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
print(f"Testing CURP={curp_test} State={state_test} with sid={sid}...")
try:
    r1 = s.get("https://onboarding.santander.com.mx/api/v1/obu/N2/multitask/session/init", headers=headers, timeout=10)
    print(f"r1: {r1.status_code} ({time.time()-t0:.2f}s)")
    
    t1 = time.time()
    r2 = s.post(
        "https://onboarding.santander.com.mx/api/v1/obu/N2/multitask/agreements/accept",
        headers=headers,
        json={"data": {"privacy": True, "termsAndConditions": True, "originFlow": "/cuenta-digital-lite/personal-data"}},
        timeout=10
    )
    print(f"r2: {r2.status_code} ({time.time()-t1:.2f}s)")
    
    t2 = time.time()
    r3 = s.post(
        "https://onboarding.santander.com.mx/api/v1/obu/N2/multitask/curp/consulta",
        headers=headers,
        json={"data": {"birthCountry": "052", "mainPersonalIdentifier": curp_test}},
        timeout=12
    )
    print(f"r3: {r3.status_code} ({time.time()-t2:.2f}s)")
    print(f"r3 body: {r3.text[:200]}")

    t3 = time.time()
    r4 = s.post(
        "https://onboarding.santander.com.mx/api/v1/obu/case/registrada/N2/preexistence/validar",
        headers=headers,
        json={
            "data": {
                "state": state_test,
                "os": "Android",
                "deviceVersion": "Android Google Pixel 9 15",
                "browserSize": "400x850",
                "resolutionScreen": "800x1700",
                "latitude": "19.4326",
                "longitude": "-99.1332"
            }
        },
        timeout=28
    )
    print(f"r4: {r4.status_code} ({time.time()-t3:.2f}s)")
    print(f"r4 body: {r4.text[:200]}")
    print(f"Total time: {time.time()-t0:.2f}s")
except Exception as e:
    print(f"Error after {time.time()-t0:.2f}s: {e}")
finally:
    s.close()

