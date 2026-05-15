"""QA: Identify normalization misses for fuel/transmission/body/condition across countries.

Fetches 5 offers per country and reports unmapped keys (those that would resolve to 'other').
"""

import io
import json
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ACTOR_ROOT_STR = str(__file__).split("scripts")[0]
sys.path.insert(0, ACTOR_ROOT_STR)

from src.data.param_maps import (
    PARAM_KEY_MAP, FUEL_NORMALIZATION, TRANSMISSION_NORMALIZATION,
    BODY_NORMALIZATION, CONDITION_NORMALIZATION, UA_COLOR_MAP, KZ_COLOR_MAP,
)

COUNTRIES = {
    "ro": {"domain": "www.olx.ro", "cat_id": 84},
    "pl": {"domain": "www.olx.pl", "cat_id": 84},
    "bg": {"domain": "www.olx.bg", "cat_id": 1117},
    "pt": {"domain": "www.olx.pt", "cat_id": 378},
    "ua": {"domain": "www.olx.ua", "cat_id": 108},
    "kz": {"domain": "www.olx.kz", "cat_id": 108},
}

ACCEPT_LANGUAGE = {
    "ro": "ro-RO,ro;q=0.9",
    "pl": "pl-PL,pl;q=0.9",
    "bg": "bg-BG,bg;q=0.9",
    "pt": "pt-PT,pt;q=0.9",
    "ua": "uk-UA,uk;q=0.9",
    "kz": "ru-KZ,ru;q=0.9",
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

NORM_FIELDS = {
    "fuel":         ("fuel_raw", FUEL_NORMALIZATION),
    "transmission": ("trans_raw", TRANSMISSION_NORMALIZATION),
    "body":         ("body_raw", BODY_NORMALIZATION),
    "condition":    ("cond_raw", CONDITION_NORMALIZATION),
}

print("=== Normalization Gap Analysis ===\n")

# Collect all seen raw keys and their normalization status
gaps = {}

for country, cfg in COUNTRIES.items():
    domain = cfg["domain"]
    cat_id = cfg["cat_id"]
    url = f"https://{domain}/api/v1/offers/?category_id={cat_id}&limit=10&offset=0"

    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Accept-Language": ACCEPT_LANGUAGE[country],
        "User-Agent": USER_AGENT,
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"[{country.upper()}] ERROR: {exc}")
        continue

    offers = body.get("data") or []
    print(f"[{country.upper()}] {len(offers)} offers")

    for offer in offers:
        params = offer.get("params") or []
        params_by_key = {p.get("key"): p.get("value") or {} for p in params if p.get("key")}

        for conceptual_field, (_, norm_dict) in NORM_FIELDS.items():
            api_key = PARAM_KEY_MAP.get(conceptual_field, {}).get(country)
            if not api_key:
                continue
            val = params_by_key.get(api_key)
            if not val:
                continue

            raw_key = val.get("key")
            if raw_key is None:
                continue

            # Handle array-valued condition fields (UA condition is a list)
            if isinstance(raw_key, list):
                raw_keys = raw_key
            else:
                raw_keys = [str(raw_key)]

            for rk in raw_keys:
                rk_lower = str(rk).lower()
                normalised = norm_dict.get(rk_lower, "other")
                if normalised == "other" and rk_lower not in norm_dict:
                    gap_key = (country, conceptual_field, api_key, rk_lower)
                    gaps[gap_key] = gaps.get(gap_key, 0) + 1

    # Also check engine size for KZ (potential litre vs cm3 issue)
    if country == "kz":
        print(f"\n  KZ motor_engine_size raw values:")
        for offer in offers:
            params = offer.get("params") or []
            for p in params:
                if p.get("key") == "motor_engine_size":
                    v = p.get("value") or {}
                    raw = v.get("key")
                    label = v.get("label", "")
                    print(f"    key={raw!r} label={label!r}")
                    break

print("\n=== Normalisation Gaps (keys that map to 'other') ===")
if not gaps:
    print("NONE found in sample.")
else:
    for (country, field, api_key, raw_key), count in sorted(gaps.items()):
        print(f"  [{country.upper()}] {field} (api_key={api_key!r}): raw={raw_key!r} count={count}")
