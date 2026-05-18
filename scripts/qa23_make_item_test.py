"""Test conditionRaw extraction logic from _make_item() — Issue #23.

Instead of running the full spider, this extracts the extraction code path
(the condition param → cond_raw logic) and verifies it produces correct
shapes for each country's real sample data from qa23_probe_responses.jsonl.

Post-fix (BLOCKER B1 resolved): conditionRaw is now ALWAYS a string.
UA multi-element arrays are ';'-joined by the spider after load_item().
The loader is no longer involved in setting conditionRaw.
"""

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ACTOR_ROOT = Path(__file__).parent.parent
PROJECT_ROOT = ACTOR_ROOT.parent
sys.path.insert(0, str(ACTOR_ROOT))


results = []

def check(label, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    results.append((status, label, detail))
    mark = "  OK  " if ok else " FAIL "
    extra = f" -- {detail}" if detail else ""
    print(f"[{mark}] {label}{extra}")


# ---------------------------------------------------------------------------
# Part 1: Spider post-load direct assignment (BLOCKER B1 fix verification)
# ---------------------------------------------------------------------------
print("--- Part 1: Spider post-load direct assignment (B1 fix) ---")
# BLOCKER B1 FIX: conditionRaw is now set directly on the item dict after
# loader.load_item() in the spider, bypassing the loader entirely.
# The spider's serialization logic:
#   if isinstance(cond_raw, list): item['conditionRaw'] = ';'.join(str(x) for x in cond_raw)
#   else:                          item['conditionRaw'] = str(cond_raw)
#
# This guarantees conditionRaw is always a str, never a list.
# UA multi-element arrays become ';'-joined strings (e.g. "first-owner;fine_condition").

def simulate_spider_assignment(cond_raw):
    """Replicate the spider's post-load conditionRaw assignment logic."""
    if cond_raw is None:
        return None
    if isinstance(cond_raw, list):
        return ';'.join(str(x) for x in cond_raw)
    return str(cond_raw)

# Scalar string: preserved as-is
result_scalar = simulate_spider_assignment("used")
check("Fix: scalar 'used' -> 'used' (str)",
      result_scalar == "used" and isinstance(result_scalar, str),
      f"got: {result_scalar!r}")

result_scalar2 = simulate_spider_assignment("first-owner")
check("Fix: scalar 'first-owner' -> 'first-owner' (str, correct for BG)",
      result_scalar2 == "first-owner" and isinstance(result_scalar2, str),
      f"got: {result_scalar2!r}")

# UA multi-element list: joined to string, first-owner flag preserved
result_ua_multi = simulate_spider_assignment(["fine_condition", "first-owner"])
check(
    "Fix: UA list ['fine_condition','first-owner'] -> 'fine_condition;first-owner' "
    "(str, first-owner flag preserved)",
    result_ua_multi == "fine_condition;first-owner",
    f"got: {result_ua_multi!r}"
)

result_ua_single = simulate_spider_assignment(["fine_condition"])
check(
    "Fix: UA single-element list ['fine_condition'] -> 'fine_condition' (str)",
    result_ua_single == "fine_condition",
    f"got: {result_ua_single!r}"
)

# None stays absent (no item key set)
result_none = simulate_spider_assignment(None)
check("Fix: None -> None (field absent, DropNonesPipeline strips it)",
      result_none is None,
      f"got: {result_none!r}"
)


# ---------------------------------------------------------------------------
# Part 2: Extract cond_raw from probe data per country
# ---------------------------------------------------------------------------
print("\n--- Part 2: conditionRaw extraction from probe sample data ---")

# The extraction logic from _make_item():
#   cond_val = get_param_value('condition') or {}
#   cond_raw = cond_val.get('key') if isinstance(cond_val, dict) else None
#
# get_param_value('condition') looks up PARAM_KEY_MAP['condition'][country] in params_by_key.
# Let's use the actual PARAM_KEY_MAP to do this properly.

from src.data.param_maps import PARAM_KEY_MAP

def extract_cond_raw_from_params(params: list, country: str):
    """Replicate the spider's cond_raw extraction logic."""
    # Build params_by_key
    params_by_key = {}
    for p in params:
        k = p.get('key')
        if k:
            params_by_key[k] = p.get('value') or {}

    # get_param_value for 'condition'
    cond_key = PARAM_KEY_MAP.get('condition', {}).get(country)
    if not cond_key:
        return None  # no condition field mapped for this country
    cond_val = params_by_key.get(cond_key)
    if cond_val is None:
        return None  # param not present in this offer

    cond_raw = cond_val.get('key') if isinstance(cond_val, dict) else None
    return cond_raw  # str, list[str], or None


# Load probe data
jsonl_path = PROJECT_ROOT / "scripts" / "qa23_probe_responses.jsonl"
baseline_by_country = {}
with open(jsonl_path, encoding='utf-8') as f:
    for line in f:
        rec = json.loads(line)
        if rec.get('type') == 'baseline':
            baseline_by_country[rec['country']] = rec.get('samples', [])

print(f"  Loaded baseline samples for: {list(baseline_by_country.keys())}")

# Test each country
COUNTRY_EXPECTATIONS = {
    'ro': {'type': str, 'expected_values': {'used', 'damaged', 'new'}},
    'pl': {'type': str, 'expected_values': {'notdamaged', 'damaged', 'nowe'}},
    'bg': {'type': None, 'note': 'bg condition maps to technical_condition via PARAM_KEY_MAP'},
    'pt': {'type': str, 'expected_values': {'usado', 'danificado', 'novo'}},
    'ua': {'type': list, 'note': 'ua condition is array-valued'},
    'kz': {'type': str, 'expected_values': {'mediocre', 'good', 'perfect', 'needs_repairs'}},
}

for country, samples in baseline_by_country.items():
    exp = COUNTRY_EXPECTATIONS.get(country, {})
    cond_raws = []
    nones = 0

    for sample in samples:
        params = sample.get('params', [])
        cr = extract_cond_raw_from_params(params, country)
        if cr is None:
            nones += 1
        else:
            cond_raws.append(cr)

    if not cond_raws and nones == len(samples):
        # Check if it's an unmapped country (BG uses 'technical_condition' not 'condition')
        # Let's check what PARAM_KEY_MAP says for this country
        mapped_key = PARAM_KEY_MAP.get('condition', {}).get(country)
        print(f"  {country}: PARAM_KEY_MAP condition key = {mapped_key!r}")
        if mapped_key is None:
            check(f"{country}: no condition key in PARAM_KEY_MAP (expected for some countries)",
                  True, "N/A -- field absent from PARAM_KEY_MAP for this country")
        else:
            check(f"{country}: condition param present in at least 1 sample",
                  False, f"all {nones} samples returned None with key={mapped_key!r}")
        continue

    print(f"  {country}: {len(cond_raws)} with value, {nones} None. "
          f"Sample values: {cond_raws[:3]}")

    expected_type = exp.get('type')
    if expected_type is not None:
        # Check that non-None values have correct type
        type_ok = all(isinstance(cr, expected_type) for cr in cond_raws)
        check(f"{country}: conditionRaw is {expected_type.__name__} (not list-of-list)",
              type_ok,
              f"sample: {cond_raws[:2]!r}")

        if expected_type == list:
            # UA: check that each element within the list is a string
            all_strings = all(
                isinstance(k, str) for cr in cond_raws for k in cr
            )
            check(f"{country} (UA): list elements are all strings",
                  all_strings,
                  f"sample list: {cond_raws[0]!r}")
        elif expected_type == str:
            # Non-UA: scalar string, not a list
            all_scalars = all(not isinstance(cr, list) for cr in cond_raws)
            check(f"{country}: conditionRaw is scalar (not a list)",
                  all_scalars,
                  f"sample: {cond_raws[:2]!r}")
    else:
        check(f"{country}: conditionRaw extraction ran (type check N/A)",
              True, exp.get('note', ''))


# ---------------------------------------------------------------------------
# Part 3: Verify cond_raw None case (no condition param in offer)
# ---------------------------------------------------------------------------
print("\n--- Part 3: cond_raw=None when no condition param present ---")
params_no_cond = [
    {"key": "price", "value": {"value": 5000, "currency": "EUR"}},
    {"key": "model", "value": {"key": "x5", "label": "X5"}},
]
cr_ro_none = extract_cond_raw_from_params(params_no_cond, 'ro')
check("RO: cond_raw=None when state param absent", cr_ro_none is None,
      f"got: {cr_ro_none!r}")

cr_kz_none = extract_cond_raw_from_params(params_no_cond, 'kz')
check("KZ: cond_raw=None when condition param absent", cr_kz_none is None,
      f"got: {cr_kz_none!r}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
total = len(results)
passed = sum(1 for s, *_ in results if s == "PASS")
failed = total - passed
print(f"Results: {passed}/{total} passed, {failed} failed")
if failed:
    print("\nFailed:")
    for status, label, detail in results:
        if status == "FAIL":
            print(f"  FAIL: {label} -- {detail}")
    sys.exit(1)
else:
    print("ALL PASS")
    sys.exit(0)
