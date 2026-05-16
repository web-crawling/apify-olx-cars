"""Unit tests for priceHistory helpers — olx-cars issue #20.

Tests _append_price_history and compute_diff in isolation (no Scrapy, no Apify).
Covers all 8 architect-specified scenarios from .workflow/olx-cars-20/05-architecture.md.

Usage:
    .venv/Scripts/python scripts/qa_pr_price_history_unit.py

Exit code: 0 = all PASS, 1 = any FAIL.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

from src.state import _append_price_history, compute_diff, MAX_PRICE_HISTORY

# ---------------------------------------------------------------------------
# Test runner helpers
# ---------------------------------------------------------------------------

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        msg = f"  FAIL  {label}" + (f"  [{detail}]" if detail else "")
        print(msg)
        _ERRORS.append(msg)


def section(title: str) -> None:
    print(f"\n=== {title} ===\n")


# ---------------------------------------------------------------------------
# Scenario 1: Empty history + first append → 1 entry with correct shape
# ---------------------------------------------------------------------------
section("Scenario 1: Empty history → first append")

result = _append_price_history([], 12000, "EUR", "2026-05-16T08:00:00+00:00")

check("returns list", isinstance(result, list))
check("length == 1", len(result) == 1)
check("entry has seenAt", result[0].get("seenAt") == "2026-05-16T08:00:00+00:00")
check("entry has price", result[0].get("price") == 12000)
check("entry has currency", result[0].get("currency") == "EUR")

# ---------------------------------------------------------------------------
# Scenario 2: Identical price+currency → no append, length unchanged
# ---------------------------------------------------------------------------
section("Scenario 2: Identical price+currency → no append")

history2 = [{"seenAt": "2026-05-01T00:00:00+00:00", "price": 12000, "currency": "EUR"}]
result2 = _append_price_history(history2, 12000, "EUR", "2026-05-16T08:00:00+00:00")

check("length unchanged (still 1)", len(result2) == 1)
check("same object returned (no mutation)", result2 is history2,
      f"got different list object (len={len(result2)})")

# ---------------------------------------------------------------------------
# Scenario 3: Price-only change → appended
# ---------------------------------------------------------------------------
section("Scenario 3: Price-only change → appended")

history3 = [{"seenAt": "2026-05-01T00:00:00+00:00", "price": 12000, "currency": "EUR"}]
result3 = _append_price_history(history3, 13000, "EUR", "2026-05-16T08:00:00+00:00")

check("length == 2", len(result3) == 2)
check("new entry price == 13000", result3[-1].get("price") == 13000)
check("new entry currency == EUR", result3[-1].get("currency") == "EUR")
check("old entry preserved", result3[0].get("price") == 12000)

# ---------------------------------------------------------------------------
# Scenario 4: Currency-only change → appended (even when price unchanged)
# ---------------------------------------------------------------------------
section("Scenario 4: Currency-only change → appended")

history4 = [{"seenAt": "2026-05-01T00:00:00+00:00", "price": 12000, "currency": "EUR"}]
result4 = _append_price_history(history4, 12000, "USD", "2026-05-16T08:00:00+00:00")

check("length == 2", len(result4) == 2)
check("new entry currency == USD", result4[-1].get("currency") == "USD")
check("price unchanged in new entry", result4[-1].get("price") == 12000)

# ---------------------------------------------------------------------------
# Scenario 5: FIFO cap — pre-seed 50 entries, append a price-change → exactly 50
# ---------------------------------------------------------------------------
section("Scenario 5: FIFO cap at 50 entries")

history5 = [
    {"seenAt": f"2026-01-{i+1:02d}T00:00:00+00:00", "price": i * 100, "currency": "EUR"}
    for i in range(MAX_PRICE_HISTORY)
]
assert len(history5) == 50, "pre-condition: seeded exactly 50 entries"

oldest_price = history5[0]["price"]
result5 = _append_price_history(history5, 99999, "EUR", "2026-06-01T00:00:00+00:00")

check("length still exactly 50", len(result5) == MAX_PRICE_HISTORY,
      f"got {len(result5)}")
check("oldest entry evicted (price 0 gone)",
      result5[0].get("price") != oldest_price,
      f"oldest price {oldest_price} still present at index 0")
check("newest entry is last (price 99999)", result5[-1].get("price") == 99999)
check("input list not mutated", len(history5) == 50)

# ---------------------------------------------------------------------------
# Scenario 6: None-price prior + None-price current → no append
# ---------------------------------------------------------------------------
section("Scenario 6: None+None → no append")

history6 = [{"seenAt": "2026-05-01T00:00:00+00:00", "price": None, "currency": None}]
result6 = _append_price_history(history6, None, None, "2026-05-16T08:00:00+00:00")

check("length unchanged (still 1)", len(result6) == 1)

# ---------------------------------------------------------------------------
# Scenario 7: None-price prior + concrete-price current → appended
# ---------------------------------------------------------------------------
section("Scenario 7: None-price prior + concrete price current → appended")

history7 = [{"seenAt": "2026-05-01T00:00:00+00:00", "price": None, "currency": None}]
result7 = _append_price_history(history7, 15000, "EUR", "2026-05-16T08:00:00+00:00")

check("length == 2", len(result7) == 2)
check("new entry price == 15000", result7[-1].get("price") == 15000)
check("new entry currency == EUR", result7[-1].get("currency") == "EUR")

# Bonus: concrete prior + None current → appended
history7b = [{"seenAt": "2026-05-01T00:00:00+00:00", "price": 15000, "currency": "EUR"}]
result7b = _append_price_history(history7b, None, None, "2026-05-16T08:00:00+00:00")
check("value->None also appended", len(result7b) == 2)

# ---------------------------------------------------------------------------
# Scenario 8: Legacy snapshot seed-on-read via compute_diff
# ---------------------------------------------------------------------------
section("Scenario 8: Legacy snapshot seed-on-read via compute_diff")

# 8a: legacy entry, price unchanged → seeded with 1 historical entry (not duplicated)
# The legacy snapshot stores all 5 TRACKED_FIELDS so _fields_changed returns False.
LEGACY_LAST_SEEN = "2026-04-01T10:00:00+00:00"
legacy_snapshot = {
    "offer-99": {
        "price": 12000,
        "currency": "EUR",
        "condition": "used",
        "mileageKm": 50000,
        "title": "BMW X5",
        "lastSeenAt": LEGACY_LAST_SEEN,
        "firstSeenAt": "2026-03-01T10:00:00+00:00",
        # NO priceHistory key — this is the legacy shape
    }
}

# Simulate current run: same price AND same tracked fields → UNCHANGED
item_no_change = {
    "offerId": "offer-99",
    "price": 12000,
    "currency": "EUR",
    "condition": "used",
    "mileageKm": 50000,
    "title": "BMW X5",
}
RUN_TS = "2026-05-16T08:00:00+00:00"

change_type_a, first_a, last_a, new_entry_a = compute_diff(item_no_change, legacy_snapshot, RUN_TS)

check("8a: changeType is UNCHANGED", change_type_a == "UNCHANGED",
      f"got {change_type_a!r}")
check("8a: priceHistory is a list", isinstance(new_entry_a.get("priceHistory"), list))

ph_a = new_entry_a.get("priceHistory", [])
# Because price is UNCHANGED (12000 == 12000 stored), the seeded entry from lastSeenAt
# is created, then _append_price_history is called with price=12000 which already
# matches the seeded entry → no additional append. So len == 1 (just the seed).
check("8a: exactly 1 entry (seed, no duplicate append for unchanged price)",
      len(ph_a) == 1, f"got {len(ph_a)} entries")
check("8a: seeded entry uses lastSeenAt as seenAt",
      ph_a[0].get("seenAt") == LEGACY_LAST_SEEN,
      f"got {ph_a[0].get('seenAt')!r}")
check("8a: seeded entry price == 12000", ph_a[0].get("price") == 12000)
check("8a: seeded entry currency == EUR", ph_a[0].get("currency") == "EUR")

# 8b: legacy entry, price CHANGED → seeded entry + new append = 2 entries
# Same snapshot, same tracked fields except price → UPDATED (price changed)
item_price_change = dict(item_no_change)
item_price_change["price"] = 11000

change_type_b, first_b, last_b, new_entry_b = compute_diff(item_price_change, legacy_snapshot, RUN_TS)

ph_b = new_entry_b.get("priceHistory", [])
check("8b: changeType is UPDATED", change_type_b == "UPDATED",
      f"got {change_type_b!r}")
check("8b: exactly 2 entries (seed + append for price change)",
      len(ph_b) == 2, f"got {len(ph_b)} entries")
check("8b: first entry is the seeded legacy price (12000)",
      ph_b[0].get("price") == 12000, f"got {ph_b[0].get('price')!r}")
check("8b: second entry has new price (11000)",
      ph_b[1].get("price") == 11000, f"got {ph_b[1].get('price')!r}")
check("8b: second entry seenAt == run_ts",
      ph_b[1].get("seenAt") == RUN_TS,
      f"got {ph_b[1].get('seenAt')!r}")

# ---------------------------------------------------------------------------
# EC1: Corrupted priceHistory in KV snapshot (e.g. stored as a string)
# Expected: compute_diff should NOT crash; should recover to empty history.
# Currently this CRASHES with AttributeError because `or []` doesn't guard
# against a truthy non-list value.
# ---------------------------------------------------------------------------
section("EC1: Corrupted priceHistory (string) in snapshot — crash test")

corrupted_snapshot = {
    "offer-corrupt": {
        "price": 10000,
        "currency": "EUR",
        "condition": "used",
        "mileageKm": 30000,
        "title": "Corrupt Car",
        "firstSeenAt": "2026-01-01T00:00:00+00:00",
        "lastSeenAt": "2026-04-01T00:00:00+00:00",
        "priceHistory": "this-is-a-string-not-a-list",  # corrupted
    }
}
item_corrupt = {
    "offerId": "offer-corrupt",
    "price": 10000,
    "currency": "EUR",
    "condition": "used",
    "mileageKm": 30000,
    "title": "Corrupt Car",
}
try:
    ct_ec1, _, _, entry_ec1 = compute_diff(item_corrupt, corrupted_snapshot, RUN_TS)
    # If it doesn't crash, check result is a valid list
    ph_ec1 = entry_ec1.get("priceHistory")
    check("EC1: compute_diff does NOT crash on corrupted priceHistory", True)
    check("EC1: recovered priceHistory is a list", isinstance(ph_ec1, list),
          f"got type {type(ph_ec1).__name__}: {ph_ec1!r}")
except AttributeError as e:
    check("EC1: compute_diff does NOT crash on corrupted priceHistory", False,
          f"AttributeError raised: {e}")
    check("EC1: recovered priceHistory is a list", False, "not reached (crashed)")
except Exception as e:
    check("EC1: compute_diff does NOT crash on corrupted priceHistory", False,
          f"{type(e).__name__}: {e}")
    check("EC1: recovered priceHistory is a list", False, "not reached (crashed)")

# ---------------------------------------------------------------------------
# EC2: Legacy snapshot entry missing 'lastSeenAt' but has 'price'
# Seed-on-read path does prior['lastSeenAt'] — KeyError if absent.
# ---------------------------------------------------------------------------
section("EC2: Legacy snapshot missing lastSeenAt — KeyError crash test")

missing_lastSeen_snapshot = {
    "offer-nots": {
        "price": 8000,
        "currency": "EUR",
        "condition": "used",
        "mileageKm": 20000,
        "title": "No Timestamp Car",
        "firstSeenAt": "2026-01-01T00:00:00+00:00",
        # NO 'lastSeenAt' key
        # NO 'priceHistory' key -> seed-on-read triggers -> hits prior['lastSeenAt']
    }
}
item_nots = {
    "offerId": "offer-nots",
    "price": 8000,
    "currency": "EUR",
    "condition": "used",
    "mileageKm": 20000,
    "title": "No Timestamp Car",
}
try:
    ct_ec2, _, _, entry_ec2 = compute_diff(item_nots, missing_lastSeen_snapshot, RUN_TS)
    ph_ec2 = entry_ec2.get("priceHistory")
    check("EC2: compute_diff does NOT crash on missing lastSeenAt", True)
    check("EC2: priceHistory is a list", isinstance(ph_ec2, list),
          f"got type {type(ph_ec2).__name__}")
except KeyError as e:
    check("EC2: compute_diff does NOT crash on missing lastSeenAt", False,
          f"KeyError: {e}")
    check("EC2: priceHistory is a list", False, "not reached (crashed)")
except Exception as e:
    check("EC2: compute_diff does NOT crash on missing lastSeenAt", False,
          f"{type(e).__name__}: {e}")
    check("EC2: priceHistory is a list", False, "not reached (crashed)")

# ---------------------------------------------------------------------------
# EC3: Snapshot manually grown to >50 entries; price UNCHANGED.
# The cap (FIFO) is only enforced when a new entry is appended.
# When unchanged, _append_price_history returns the input list unchanged.
# So a >50 entry snapshot persists through an unchanged run.
# This is LOW severity — documents expected current behavior.
# ---------------------------------------------------------------------------
section("EC3: >50 entries in snapshot, price UNCHANGED — cap not re-enforced")

# Build a 60-entry history (simulates manually edited snapshot)
big_history = [
    {"seenAt": f"2026-01-{i+1:02d}T00:00:00+00:00", "price": 5000 + i, "currency": "EUR"}
    for i in range(60)
]
big_snapshot = {
    "offer-big": {
        "price": 5059,   # == last entry price (60th entry: 5000+59=5059)
        "currency": "EUR",
        "condition": "used",
        "mileageKm": 10000,
        "title": "Big History Car",
        "firstSeenAt": "2026-01-01T00:00:00+00:00",
        "lastSeenAt": "2026-04-01T00:00:00+00:00",
        "priceHistory": big_history,
    }
}
item_big = {
    "offerId": "offer-big",
    "price": 5059,   # same as last entry → UNCHANGED → no append
    "currency": "EUR",
    "condition": "used",
    "mileageKm": 10000,
    "title": "Big History Car",
}
try:
    ct_ec3, _, _, entry_ec3 = compute_diff(item_big, big_snapshot, RUN_TS)
    ph_ec3 = entry_ec3.get("priceHistory", [])
    # UNCHANGED price → _append_price_history returns original 60-entry list unchanged
    # This documents that cap is NOT re-enforced on unchanged runs.
    cap_re_enforced = len(ph_ec3) <= MAX_PRICE_HISTORY
    check("EC3: compute_diff handles >50-entry snapshot without crash", True)
    if cap_re_enforced:
        check("EC3: cap re-enforced even on unchanged price (better behavior)", True)
    else:
        # Document as known current behavior, not a crash
        check(
            f"EC3 (known behavior): >50-entry snapshot NOT capped on UNCHANGED run "
            f"(len={len(ph_ec3)}; cap only enforces on price-change appends)",
            True,  # not a FAIL — just documenting behavior
        )
except Exception as e:
    check("EC3: compute_diff handles >50-entry snapshot without crash", False,
          f"{type(e).__name__}: {e}")
    check("EC3: cap behavior note", False, "not reached (crashed)")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*60}")
print(f"Results: {_PASS} PASS / {_FAIL} FAIL")

if _FAIL:
    print("\nFailed checks:")
    for e in _ERRORS:
        print(f" {e}")
    print("\nOverall: FAIL")
    sys.exit(1)
else:
    print("\nOverall: ALL PASS")
    sys.exit(0)
