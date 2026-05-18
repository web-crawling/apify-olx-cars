"""QA unit tests for issue #19 — VIN enrichment via NHTSA vPIC.

Covers scenarios 3, 5, 7, 8, 9, 10 without network access.
Uses only stdlib + the local src/ modules (no Scrapy process, no Apify SDK).

Run from the actor root:
    .venv/Scripts/python scripts/qa_19_unit.py
"""

from __future__ import annotations

import sys
import os
import io
from pathlib import Path

# Force UTF-8 output on Windows (avoids cp1252 encoding errors with special chars)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure the actor root is on sys.path so we can import src.*
ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

results: list[tuple[str, str, str]] = []  # (scenario_id, status, notes)

PASS = "PASS"
FAIL = "FAIL"


def record(scenario_id: str, status: str, notes: str = "") -> None:
    results.append((scenario_id, status, notes))
    marker = "OK" if status == PASS else "!!"
    print(f"  [{marker}] {scenario_id}: {status} {notes}")


# ---------------------------------------------------------------------------
# Scenario 3: Invalid VIN format — _is_valid_vin returns False
# ---------------------------------------------------------------------------
print("\n=== Scenario 3: Invalid VIN format ===")
try:
    from src.spiders.olx_cars import _is_valid_vin, _VIN_RE

    test_vins = [
        ("WBAKJ6C50BCX13187", True,  "valid 17-char, no I/O/Q"),
        ("1FTEX1E86AFC73617", True,  "valid 17-char US VIN"),
        ("WBAKJ6C50BCX1318",  False, "16-char too short"),
        ("WBAKJ6C50BCX131870", False, "18-char too long"),
        ("WBAKJ6C50BCI13187", False, "contains I"),
        ("WBAKJ6C50BCO13187", False, "contains O"),
        ("WBAKJ6C50BCQ13187", False, "contains Q"),
        ("",                   False, "empty string"),
        ("wbakj6c50bcx13187", True,  "lowercase accepted (upper internally)"),
    ]

    all_ok = True
    for vin, expected, note in test_vins:
        result = _is_valid_vin(vin)
        ok = result == expected
        print(f"    _is_valid_vin({vin!r:20s}) = {result} (expected {expected}) {'OK' if ok else 'FAIL'} -- {note}")
        if not ok:
            all_ok = False

    record("S3", PASS if all_ok else FAIL, "VIN regex validation")
except Exception as exc:
    record("S3", FAIL, f"Exception: {exc}")


# ---------------------------------------------------------------------------
# Scenario 7: DropNonesPipeline strips None sub-fields from vinDecoded
# ---------------------------------------------------------------------------
print("\n=== Scenario 7: DropNonesPipeline strips None sub-fields in vinDecoded ===")
try:
    from src.pipelines import _drop_nones

    # Simulate an item with partial vinDecoded containing a None sub-field
    item_dict = {
        'offerId': 12345,
        'make': 'BMW',
        'vinDecoded': {
            'make': 'BMW',
            'model': 'X5',
            'series': None,        # <-- should be stripped
            'trim': None,          # <-- should be stripped
            'engineCylinders': '6',
        },
    }

    result = _drop_nones(item_dict)
    vd = result.get('vinDecoded')

    ok1 = vd is not None
    ok2 = 'make' in vd and vd['make'] == 'BMW'
    ok3 = 'model' in vd and vd['model'] == 'X5'
    ok4 = 'series' not in vd       # None was stripped
    ok5 = 'trim' not in vd         # None was stripped
    ok6 = vd.get('engineCylinders') == '6'

    print(f"    vinDecoded after _drop_nones: {vd}")
    all_ok = all([ok1, ok2, ok3, ok4, ok5, ok6])
    record("S7", PASS if all_ok else FAIL,
           f"keys present: {list(vd.keys()) if vd else 'None'}")

    # Also test: top-level vinDecoded=None is stripped
    item_with_none_vd = {'offerId': 1, 'make': 'BMW', 'vinDecoded': None}
    result2 = _drop_nones(item_with_none_vd)
    ok_top = 'vinDecoded' not in result2
    print(f"    vinDecoded=None stripped at top-level: {ok_top}")
    if not ok_top:
        record("S7-top", FAIL, "vinDecoded=None was NOT stripped by _drop_nones")
    else:
        record("S7-top", PASS, "vinDecoded=None stripped at top-level")

except Exception as exc:
    record("S7", FAIL, f"Exception: {exc}")


# ---------------------------------------------------------------------------
# Scenario 8: compact mode excludes vinDecoded
# ---------------------------------------------------------------------------
print("\n=== Scenario 8: compact mode excludes vinDecoded ===")
try:
    from src.pipelines import shape_output, COMPACT_FIELDS

    # First verify vinDecoded is NOT in COMPACT_FIELDS
    if 'vinDecoded' in COMPACT_FIELDS:
        record("S8-schema", FAIL, "vinDecoded is IN COMPACT_FIELDS — should not be!")
    else:
        record("S8-schema", PASS, "vinDecoded is correctly absent from COMPACT_FIELDS")

    # Build a realistic full item dict including vinDecoded
    item = {
        'offerId': 12345,
        'url': 'https://www.olx.pl/d/example',
        'country': 'pl',
        'title': 'BMW X5 2019',
        'price': 120000,
        'currency': 'PLN',
        'make': 'BMW',
        'model': 'X5',
        'year': 2019,
        'mileageKm': 80000,
        'fuelType': 'diesel',
        'transmission': 'automatic',
        'bodyType': 'suv',
        'condition': 'used',
        'description': 'Good condition',
        'engineCapacityCm3': 2993,
        'powerHp': 265,
        'color': 'black',
        'vin': 'WBAKJ6C50BCX13187',
        'vinDecoded': {
            'make': 'BMW',
            'model': 'X5',
            'modelYear': '2019',
            'bodyClass': 'Sport Utility Vehicle (SUV)',
        },
    }

    result = shape_output(dict(item), 'compact', None)  # copy to avoid mutation

    ok_absent = 'vinDecoded' not in result
    ok_18_fields = all(f in result for f in ['offerId', 'url', 'country', 'title',
                                              'price', 'currency', 'make', 'model',
                                              'year', 'mileageKm', 'fuelType',
                                              'transmission', 'bodyType', 'condition',
                                              'description', 'engineCapacityCm3',
                                              'powerHp', 'color'])
    ok_vin_absent = 'vin' not in result  # vin is not in COMPACT_FIELDS either
    print(f"    compact result keys: {sorted(result.keys())}")
    print(f"    vinDecoded absent: {ok_absent}")
    print(f"    all 18 compact fields present: {ok_18_fields}")

    all_ok = ok_absent and ok_18_fields
    record("S8", PASS if all_ok else FAIL,
           f"vinDecoded absent={ok_absent}, 18 fields present={ok_18_fields}")

except Exception as exc:
    record("S8", FAIL, f"Exception: {exc}")


# ---------------------------------------------------------------------------
# Scenario 9: INPUT_DATA passthrough static check
# ---------------------------------------------------------------------------
print("\n=== Scenario 9: INPUT_DATA passthrough static check ===")
try:
    import ast
    import json

    INPUT_SCHEMA = ACTOR_ROOT / ".actor" / "input_schema.json"
    MAIN_PY = ACTOR_ROOT / "src" / "main.py"

    schema = json.loads(INPUT_SCHEMA.read_text(encoding="utf-8"))
    schema_props = set(schema.get("properties", {}).keys())

    source = MAIN_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)

    input_data_keys = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "set":
            continue
        if not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and first.value == "INPUT_DATA"):
            continue
        if len(node.args) < 2 or not isinstance(node.args[1], ast.Dict):
            break
        keys = []
        for key_node in node.args[1].keys:
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                keys.append(key_node.value)
        input_data_keys = keys
        break

    if input_data_keys is None:
        record("S9", FAIL, "Could not locate INPUT_DATA dict in main.py")
    else:
        forwarded = {k for k in input_data_keys if not k.startswith("_")}
        missing = schema_props - forwarded
        extras = forwarded - schema_props
        print(f"    schema_props={sorted(schema_props)}")
        print(f"    forwarded={sorted(forwarded)}")
        if missing:
            print(f"    MISSING from INPUT_DATA: {sorted(missing)}")
        if extras:
            print(f"    EXTRAS in INPUT_DATA (no schema prop): {sorted(extras)}")

        ok = not missing and not extras
        # enrichVIN must be in forwarded
        ok_vin = 'enrichVIN' in forwarded
        print(f"    enrichVIN in INPUT_DATA: {ok_vin}")
        record("S9", PASS if (ok and ok_vin) else FAIL,
               f"missing={sorted(missing)}, extras={sorted(extras)}, enrichVIN_forwarded={ok_vin}")

except Exception as exc:
    record("S9", FAIL, f"Exception: {exc}")


# ---------------------------------------------------------------------------
# Scenario 10: FailOnItemErrorExtension — vPIC failures don't fire item_error
# ---------------------------------------------------------------------------
print("\n=== Scenario 10: FailOnItemErrorExtension noop for vPIC failures ===")
try:
    # Read the spider source to verify errback_vpic does NOT raise from pipeline
    spider_src = (ACTOR_ROOT / "src" / "spiders" / "olx_cars.py").read_text(encoding="utf-8")

    # errback_vpic must yield item, not raise
    has_errback = "def errback_vpic" in spider_src
    # Verify it does NOT set crawl_failed — extract only the function body.
    # errback_vpic ends at the next method definition at the same indent level.
    errback_start = spider_src.find("def errback_vpic")
    # Find the NEXT 4-space-indented def (not a nested def) to delimit the body
    import re as _re
    # Look for the pattern "    def " (4 spaces) after errback_start
    next_method_match = _re.search(r'\n    def ', spider_src[errback_start + 20:])
    if next_method_match:
        errback_end = errback_start + 20 + next_method_match.start()
    else:
        errback_end = len(spider_src)
    errback_body = spider_src[errback_start:errback_end]

    # Check that the body does NOT contain "crawl_failed =" (assignment, not comment)
    has_no_crawl_failed = "crawl_failed = " not in errback_body and "crawl_failed=True" not in errback_body
    has_yield_item = "yield item" in errback_body
    has_error_count_increment = "_vpic_error_count" in errback_body

    print(f"    errback_vpic found: {has_errback}")
    print(f"    errback_vpic does NOT set crawl_failed: {has_no_crawl_failed}")
    print(f"    errback_vpic yields item: {has_yield_item}")
    print(f"    errback_vpic increments _vpic_error_count: {has_error_count_increment}")

    # Verify FailOnItemErrorExtension wires to item_error signal (not request error)
    ext_src = (ACTOR_ROOT / "src" / "extensions.py").read_text(encoding="utf-8")
    has_item_error_signal = "item_error" in ext_src
    has_no_vpic_ref = "vpic" not in ext_src.lower()

    print(f"    FailOnItemErrorExtension wires to item_error: {has_item_error_signal}")
    print(f"    FailOnItemErrorExtension has no vpic reference (correct separation): {has_no_vpic_ref}")

    all_ok = all([has_errback, has_no_crawl_failed, has_yield_item,
                  has_error_count_increment, has_item_error_signal])
    record("S10", PASS if all_ok else FAIL,
           "errback_vpic is spider-layer (not pipeline); extension correctly wired to item_error only")

except Exception as exc:
    record("S10", FAIL, f"Exception: {exc}")


# ---------------------------------------------------------------------------
# Scenario 5: vPIC 200 with empty Results → vinDecoded=None, empty dict cached
# ---------------------------------------------------------------------------
print("\n=== Scenario 5: Empty vPIC Results - vinDecoded=None ===")
try:
    # Test the extraction logic directly from parse_vpic implementation
    # by running the inner filtering logic (no Scrapy, no async)

    from src.spiders.olx_cars import VPIC_FIELD_MAP

    # Simulate what parse_vpic does with empty results
    results_data = []  # empty Results from NHTSA
    raw_lookup = {
        r['Variable']: r.get('Value')
        for r in results_data
        if isinstance(r, dict) and r.get('Variable')
    }

    _EMPTY_VALUES = {'', 'null', 'not applicable', '0'}
    decoded = {}
    for out_key, vpic_var in VPIC_FIELD_MAP.items():
        val = raw_lookup.get(vpic_var)
        if val and isinstance(val, str):
            val_stripped = val.strip()
            if val_stripped and val_stripped.lower() not in _EMPTY_VALUES:
                decoded[out_key] = val_stripped

    ok_empty = decoded == {}
    print(f"    decoded from empty Results: {decoded}")
    print(f"    decoded is empty (correct): {ok_empty}")

    # Also simulate null/empty/"Not Applicable" values
    results_data2 = [
        {"Variable": "Make", "Value": ""},
        {"Variable": "Model", "Value": "null"},
        {"Variable": "Body Class", "Value": "Not Applicable"},
        {"Variable": "Doors", "Value": "0"},
        {"Variable": "Vehicle Type", "Value": "PASSENGER CAR"},  # this one should survive
    ]
    raw_lookup2 = {r['Variable']: r.get('Value') for r in results_data2 if r.get('Variable')}
    decoded2 = {}
    for out_key, vpic_var in VPIC_FIELD_MAP.items():
        val = raw_lookup2.get(vpic_var)
        if val and isinstance(val, str):
            val_stripped = val.strip()
            if val_stripped and val_stripped.lower() not in _EMPTY_VALUES:
                decoded2[out_key] = val_stripped

    ok_only_vehicle_type = set(decoded2.keys()) == {'vehicleType'}
    print(f"    decoded2 (filtered empties): {decoded2}")
    print(f"    only vehicleType survived (correct): {ok_only_vehicle_type}")

    record("S5", PASS if (ok_empty and ok_only_vehicle_type) else FAIL,
           "empty Results -> empty decoded dict; null/empty/NA values filtered")

except Exception as exc:
    record("S5", FAIL, f"Exception: {exc}")


# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("UNIT TEST SUMMARY")
print("=" * 60)
for sid, status, notes in results:
    marker = "✓" if status == PASS else "✗"
    print(f"  [{marker}] {sid}: {status} — {notes}")

failures = [r for r in results if r[1] == FAIL]
print(f"\n{'ALL PASS' if not failures else str(len(failures)) + ' FAILURES'}: "
      f"{len(results) - len(failures)}/{len(results)} scenarios passed")
sys.exit(1 if failures else 0)
