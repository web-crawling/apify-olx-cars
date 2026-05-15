"""Inspect BG offer to verify fuel type, transmission, body type raw param keys."""

import io
import json
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

url = "https://www.olx.bg/api/v1/offers/?category_id=1117&limit=5&offset=0"
req = urllib.request.Request(url, headers={
    "Accept": "application/json",
    "Accept-Language": "bg-BG,bg;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
})
with urllib.request.urlopen(req, timeout=15) as resp:
    body = json.loads(resp.read().decode("utf-8"))

for i, offer in enumerate(body.get("data", [])):
    title = offer.get("title", "").encode("ascii", errors="replace").decode("ascii")
    print(f"\n=== BG Offer {i}: {title} ===")
    params = offer.get("params") or []
    for p in params:
        key = p.get("key", "")
        val = p.get("value", {})
        if key in ("auto_engine_type", "auto_transmission_type", "type",
                   "technical_condition", "enginesize", "horsepower", "color",
                   "comfort", "multimedia", "safety", "other", "auto_mileage",
                   "auto_make_year", "vinnomer", "doors", "seats", "import"):
            val_str = json.dumps(val, ensure_ascii=True)
            print(f"  param key={key!r} value={val_str}")
