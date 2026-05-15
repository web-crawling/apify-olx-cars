"""Inspect RO BMW offers for raw fuel/transmission/body param values."""
import io
import json
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

url = "https://www.olx.ro/api/v1/offers/?category_id=183&limit=3&offset=0"
req = urllib.request.Request(url, headers={
    "Accept": "application/json",
    "Accept-Language": "ro-RO,ro;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
})
with urllib.request.urlopen(req, timeout=15) as resp:
    body = json.loads(resp.read().decode("utf-8"))

for i, offer in enumerate(body.get("data", [])):
    title = offer.get("title", "").encode("ascii", errors="replace").decode("ascii")
    print(f"\n=== RO Offer {i}: {title} ===")
    params = offer.get("params") or []
    for p in params:
        key = p.get("key", "")
        val = p.get("value", {})
        if key in ("petrol", "gearbox", "car_body", "state", "enginesize",
                   "engine_power", "color", "door_count", "steering_wheel",
                   "registration_state", "rulaj_pana"):
            val_str = json.dumps(val, ensure_ascii=True)
            print(f"  param key={key!r} value={val_str}")
