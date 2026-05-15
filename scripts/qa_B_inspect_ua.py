"""Inspect UA offer to verify fuel type, engine size, mileage, transmission raw param keys."""

import io
import json
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

url = "https://www.olx.ua/api/v1/offers/?category_id=108&limit=5&offset=0"
req = urllib.request.Request(url, headers={
    "Accept": "application/json",
    "Accept-Language": "uk-UA,uk;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
})
with urllib.request.urlopen(req, timeout=15) as resp:
    body = json.loads(resp.read().decode("utf-8"))

for i, offer in enumerate(body.get("data", [])):
    title = offer.get("title", "").encode("ascii", errors="replace").decode("ascii")
    print(f"\n=== UA Offer {i}: {title} ===")
    params = offer.get("params") or []
    for p in params:
        key = p.get("key", "")
        val = p.get("value", {})
        if key in ("fuel_type", "transmission_type", "car_body", "condition",
                   "motor_engine_size_litre", "motor_mileage_thou", "power",
                   "color", "car_option", "drive_type", "vin_number",
                   "doors_num", "seats_num", "cleared_customs"):
            val_str = json.dumps(val, ensure_ascii=True)
            print(f"  param key={key!r} value={val_str}")
