"""Regression test for issue #44 — MISSING items pipeline-bypass fix.

Tests that `_drop_nones` (imported from src/pipelines.py) correctly strips None
values from the partial item dicts produced by `compute_missing`, which bypass
the Scrapy pipeline chain and are pushed directly via `dataset.push_data`.

Pre-fix: bare `dataset.push_data(missing_item)` sent dicts containing None values
         → Apify schema validator HTTP 400 "Schema validation failed" → silent FAIL.
Post-fix: `dataset.push_data(_drop_nones(missing_item))` → None keys stripped,
          typed fields absent (not null) → Apify validator accepts.

This test also mirrors the `isRepost=False` injection in main.py (False is not
None and must survive the strip — asserted explicitly).

Usage:
  python scripts/qa_pr44_drop_nones.py
  (or via a virtualenv: .venv/Scripts/python scripts/qa_pr44_drop_nones.py)

No network, no Apify SDK, no Scrapy — pure Python.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure actor root is on sys.path
ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

from src.pipelines import _drop_nones

PASS = "PASS"
FAIL = "FAIL"

results: list[tuple[str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = PASS if condition else FAIL
    results.append((name, status))
    marker = "  OK" if condition else "  FAIL"
    extra = f" ({detail})" if detail else ""
    print(f"{marker}  {name}{extra}")


# ---------------------------------------------------------------------------
# Build a representative compute_missing output dict.
#
# `compute_missing` in state.py builds items from the compact KV snapshot.
# Snapshot entries store: price, currency, condition, mileageKm, title,
# firstSeenAt, lastSeenAt, priceHistory (and optionally _missingCount which
# is stripped before emission). Fields absent from the snapshot (offerId is
# added by compute_missing; all full-item fields like make, model, images,
# location etc. are NOT stored) produce absent keys, not None.
# BUT: some snapshot entries may legitimately have None for optional fields
# (e.g. mileageKm for a listing that never had mileage; price for undisclosed
# price). These None values reach _drop_nones and must be stripped.
#
# We simulate a realistic worst-case missing_item dict:
# ---------------------------------------------------------------------------

MISSING_ITEM_WITH_NONES: dict = {
    # offerId added by compute_missing (always a string from snapshot key)
    "offerId": "123456789",
    "changeType": "MISSING",
    # Snapshot-stored fields, some legitimately None
    "price": None,
    "currency": None,
    "mileageKm": 50000,
    "condition": "used",
    "title": None,
    # Timestamps always present (state.py guarantees these)
    "firstSeenAt": "2026-05-15T08:00:00+00:00",
    "lastSeenAt": "2026-05-16T08:00:00+00:00",
    # priceHistory is a list of dicts — nested None values can also appear
    # (e.g. price=None when seller hid the price, currency=None in same case)
    "priceHistory": [
        {"seenAt": "2026-05-15T08:00:00+00:00", "price": 5000, "currency": "EUR"},
        {"seenAt": "2026-05-16T08:00:00+00:00", "price": None, "currency": None},
    ],
    # location dict — may be partial from some snapshot versions
    "location": {
        "city": "Bucharest",
        "district": None,  # not available in RO snapshot
        "region": "Ilfov",
    },
}

# Mirror main.py: inject isRepost=False before calling _drop_nones
MISSING_ITEM_WITH_NONES["isRepost"] = False

# Apply the fix
result = _drop_nones(MISSING_ITEM_WITH_NONES)

# ---------------------------------------------------------------------------
# Assertions: None removal
# ---------------------------------------------------------------------------

check(
    "no_top_level_None_values",
    all(v is not None for v in result.values()),
    f"keys with None: {[k for k, v in result.items() if v is None]}",
)

check("price_None_stripped", "price" not in result, f"price={result.get('price')!r}")
check("currency_None_stripped", "currency" not in result, f"currency={result.get('currency')!r}")
check("title_None_stripped", "title" not in result, f"title={result.get('title')!r}")

# ---------------------------------------------------------------------------
# Assertions: non-None values are preserved unchanged
# ---------------------------------------------------------------------------

check("offerId_preserved", result.get("offerId") == "123456789", f"got {result.get('offerId')!r}")
check("changeType_preserved", result.get("changeType") == "MISSING", f"got {result.get('changeType')!r}")
check("mileageKm_preserved", result.get("mileageKm") == 50000, f"got {result.get('mileageKm')!r}")
check("condition_preserved", result.get("condition") == "used", f"got {result.get('condition')!r}")
check("firstSeenAt_preserved", result.get("firstSeenAt") == "2026-05-15T08:00:00+00:00")
check("lastSeenAt_preserved", result.get("lastSeenAt") == "2026-05-16T08:00:00+00:00")

# ---------------------------------------------------------------------------
# Assertions: isRepost=False survives (False is not None)
# ---------------------------------------------------------------------------

check(
    "isRepost_survives_as_False",
    "isRepost" in result and result["isRepost"] is False,
    f"isRepost={result.get('isRepost')!r}",
)

# ---------------------------------------------------------------------------
# Assertions: nested structures handled correctly
# ---------------------------------------------------------------------------

ph = result.get("priceHistory")
check("priceHistory_is_list", isinstance(ph, list), f"got {type(ph).__name__}")
check("priceHistory_length_unchanged", len(ph) == 2, f"got {len(ph)}")

# First entry has real values — must be fully preserved
entry0 = ph[0]
check("priceHistory[0].price_preserved", entry0.get("price") == 5000, f"got {entry0.get('price')!r}")
check("priceHistory[0].currency_preserved", entry0.get("currency") == "EUR", f"got {entry0.get('currency')!r}")
check("priceHistory[0].seenAt_preserved", "seenAt" in entry0)

# Second entry has None price/currency — those keys must be stripped
entry1 = ph[1]
check("priceHistory[1].price_None_stripped", "price" not in entry1, f"price={entry1.get('price')!r}")
check("priceHistory[1].currency_None_stripped", "currency" not in entry1, f"currency={entry1.get('currency')!r}")
check("priceHistory[1].seenAt_preserved", "seenAt" in entry1)

# location dict: city and region preserved, district (None) stripped
loc = result.get("location", {})
check("location_city_preserved", loc.get("city") == "Bucharest", f"got {loc.get('city')!r}")
check("location_region_preserved", loc.get("region") == "Ilfov", f"got {loc.get('region')!r}")
check("location_district_None_stripped", "district" not in loc, f"district={loc.get('district')!r}")

# ---------------------------------------------------------------------------
# Assertions: scalar / integer / list types are unchanged
# ---------------------------------------------------------------------------

check("mileageKm_is_int", isinstance(result.get("mileageKm"), int), f"got {type(result.get('mileageKm')).__name__}")
check("offerId_is_str", isinstance(result.get("offerId"), str), f"got {type(result.get('offerId')).__name__}")
check("priceHistory_is_list_type", isinstance(result.get("priceHistory"), list))
check("isRepost_is_bool", isinstance(result.get("isRepost"), bool), f"got {type(result.get('isRepost')).__name__}")

# ---------------------------------------------------------------------------
# Verify _drop_nones is non-mutating (original dict unchanged)
# ---------------------------------------------------------------------------

check(
    "original_dict_not_mutated",
    MISSING_ITEM_WITH_NONES.get("price") is None,
    "original price should still be None",
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

total = len(results)
passed = sum(1 for _, s in results if s == PASS)
failed = total - passed

print()
print(f"Results: {passed}/{total} passed")
if failed:
    print("FAILED tests:")
    for name, status in results:
        if status == FAIL:
            print(f"  - {name}")
    sys.exit(1)
else:
    print("ALL PASS")
    sys.exit(0)
