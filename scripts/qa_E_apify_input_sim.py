"""QA Test E -- Apify input simulation.

Build JSON matching the EXACT schema prefill (the one Apify's automated QA submits)
and verify it doesn't cause HTTP 400 or input validation failures.

The prefill from input_schema.json is:
  startUrls: [{"url": "https://www.olx.ro/auto-masini-moto-ambarcatiuni/autoturisme/"}]
  brands: ["BMW", "Volkswagen"]
  sortBy: "created_at:desc"
  maxItems: 1000

Apify's QA submits the schema prefill as run input. We simulate this by:
1. Reading the actual prefill from input_schema.json
2. Posting it to https://www.olx.ro/api/v1/offers/ with limit=1
3. Verifying HTTP 200 (not 400)
4. Also testing the exampleRunInput from architecture: {"country":"ro","brands":["BMW"],"maxItems":50}
"""

import io
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ACTOR_ROOT = Path(__file__).parent.parent
ok = True

def check(label, condition, details=""):
    global ok
    status = "PASS" if condition else "FAIL"
    if not condition:
        ok = False
    msg = f"{status} -- {label}"
    if details:
        msg += f"\n    {details}"
    print(msg)

# ---- Read schema prefill ----
input_schema = json.loads((ACTOR_ROOT / ".actor" / "input_schema.json").read_text())
props = input_schema.get("properties", {})

prefill_start_urls = props.get("startUrls", {}).get("prefill", [])
prefill_brands = props.get("brands", {}).get("prefill", [])
prefill_sort_by = props.get("sortBy", {}).get("default", "created_at:desc")
prefill_max_items = props.get("maxItems", {}).get("prefill", 1000)

print("=== Schema Prefill Summary ===")
print(f"startUrls prefill: {prefill_start_urls}")
print(f"brands prefill: {prefill_brands}")
print(f"sortBy default: {prefill_sort_by!r}")
print(f"maxItems prefill: {prefill_max_items}")

# ---- Validate prefill shape ----
# startUrls must be list of {"url": "..."} objects (not plain strings)
all_objects = all(isinstance(e, dict) and "url" in e for e in prefill_start_urls) if prefill_start_urls else True
check(
    "startUrls prefill entries are {url:...} objects (Apify input validation check)",
    all_objects,
    f"Values: {prefill_start_urls!r}"
)

# brands must be list of strings
all_strings = all(isinstance(e, str) for e in prefill_brands) if prefill_brands else True
check(
    "brands prefill entries are plain strings",
    all_strings,
    f"Values: {prefill_brands!r}"
)

# ---- Simulate: Apify QA posts schema prefill as run input ----
# The actor would parse this and hit the OLX API.
# We simulate by making one real API call with the prefill URL.
print("\n=== E1: Live simulation with startUrls prefill ===")
if prefill_start_urls:
    first_url = prefill_start_urls[0]["url"]
    # The spider would:
    # 1. Detect country from URL -> ro
    # 2. Extract category_id (none from URL -> use parent cat 84)
    # 3. Request /api/v1/offers/?category_id=84&limit=50&offset=0
    api_url = "https://www.olx.ro/api/v1/offers/?category_id=84&limit=1&offset=0&sort_by=created_at%3Adesc"
    print(f"Simulating API call for startUrl: {first_url}")
    print(f"Expected API URL: {api_url}")

    try:
        req = urllib.request.Request(api_url, headers={
            "Accept": "application/json",
            "Accept-Language": "ro-RO,ro;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = {}

    check(
        "Prefill startUrls API call returns HTTP 200 (not 400)",
        status == 200,
        f"Got HTTP {status}"
    )
    if status == 200:
        data_count = len(body.get("data") or [])
        check(
            "Prefill startUrls API call returns data items",
            data_count > 0,
            f"data count: {data_count}"
        )

# ---- E2: exampleRunInput simulation ----
print("\n=== E2: exampleRunInput simulation ===")
example_input = {"country": "ro", "brands": ["BMW"], "maxItems": 50}
print(f"exampleRunInput: {json.dumps(example_input)}")

# Simulate: brand BMW resolves to cat_id=183 for ro
# API call: /api/v1/offers/?category_id=183&limit=1&offset=0
api_url2 = "https://www.olx.ro/api/v1/offers/?category_id=183&limit=1&offset=0"
try:
    req2 = urllib.request.Request(api_url2, headers={
        "Accept": "application/json",
        "Accept-Language": "ro-RO,ro;q=0.9",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    })
    with urllib.request.urlopen(req2, timeout=15) as resp:
        status2 = resp.status
        body2 = json.loads(resp.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    status2 = exc.code
    body2 = {}

check(
    "exampleRunInput API call (BMW ro cat=183) returns HTTP 200",
    status2 == 200,
    f"Got HTTP {status2}"
)
if status2 == 200:
    data2 = body2.get("data") or []
    check(
        "exampleRunInput API call returns BMW listings",
        len(data2) > 0,
        f"data count: {len(data2)}"
    )
    targeting2 = body2.get("metadata", {}).get("adverts", {}).get("config", {}).get("targeting", {})
    cat_l2 = targeting2.get("cat_l2_name")
    check(
        "exampleRunInput API call returns cat_l2_name for make field",
        cat_l2 is not None,
        f"cat_l2_name: {cat_l2!r}"
    )

# ---- E3: Verify "br" country is rejected by input schema ----
print("\n=== E3: country=br rejected by input schema enum ===")
country_enum = props.get("country", {}).get("enum", [])
check(
    'country enum does not include "br"',
    "br" not in country_enum,
    f"Enum: {country_enum}"
)
check(
    'country enum includes all 6 supported countries',
    sorted(country_enum) == sorted(["ro", "pl", "bg", "pt", "ua", "kz"]),
    f"Enum: {sorted(country_enum)}"
)

print(f"\nResult: {'ALL PASS' if ok else 'FAILURES FOUND'}")
sys.exit(0 if ok else 1)
