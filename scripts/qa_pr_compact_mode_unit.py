"""Unit tests for shape_output() and COMPACT_FIELDS — Issue #24 (Compact / LLM-friendly output mode).

Tests are deterministic and require no network access.
Run:
    .venv/Scripts/python scripts/qa_pr_compact_mode_unit.py

Exit codes:
    0 — all tests pass
    1 — one or more tests failed
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Force UTF-8 on stdout for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

from src.pipelines import COMPACT_FIELDS, shape_output  # noqa: E402

# ---------------------------------------------------------------------------
# Approved 18-field compact set from Gate 1 (06-params-approval.md)
# ---------------------------------------------------------------------------
EXPECTED_COMPACT_FIELDS = frozenset({
    'offerId', 'url', 'country', 'title', 'price', 'currency',
    'make', 'model', 'year', 'mileageKm', 'fuelType', 'transmission',
    'bodyType', 'condition', 'description',
    'engineCapacityCm3', 'powerHp', 'color',
})

# ---------------------------------------------------------------------------
# Synthetic 49-field item — covers all 18 compact fields + excluded fields
# ---------------------------------------------------------------------------
SYNTHETIC_ITEM = {
    # --- Compact fields (18) ---
    'offerId': 123456789,
    'url': 'https://www.olx.ro/d/oferta/bmw-320d-ID123456789.html',
    'country': 'ro',
    'title': 'BMW 320d xDrive',
    'price': 15000,
    'currency': 'EUR',
    'make': 'BMW',
    'model': '3-series',
    'year': 2018,
    'mileageKm': 95000,
    'fuelType': 'diesel',
    'transmission': 'automatic',
    'bodyType': 'sedan',
    'condition': 'used',
    'description': 'Autoturism in stare excelenta, fara accidente, service complet BMW.',
    'engineCapacityCm3': 1995,
    'powerHp': 190,
    'color': 'Negru',
    # --- Excluded fields: FairPrice ---
    'priceVsMedianPct': -8.5,
    'priceRating': 'good',
    # --- Excluded fields: incremental tracking ---
    'changeType': 'NEW',
    'firstSeenAt': '2026-05-18T10:00:00Z',
    'lastSeenAt': '2026-05-18T10:00:00Z',
    'priceHistory': [{'seenAt': '2026-05-18T10:00:00Z', 'price': 15000, 'currency': 'EUR'}],
    'isRepost': False,
    # --- Excluded fields: nested objects ---
    'seller': {'id': '987', 'type': 'private', 'hasPhone': True, 'hasChat': False},
    'location': {'city': 'Bucuresti', 'region': 'Ilfov', 'gpsObfuscated': True},
    # --- Excluded fields: media / raw / passthrough ---
    'images': ['https://img1.olx.ro/img1.jpg', 'https://img2.olx.ro/img2.jpg'],
    'paramsRaw': [{'key': 'gearbox', 'value': {'key': 'automatic', 'label': 'Automata'}}],
    'extraAttributes': {'gearbox': 'Automata', 'fuel_type': 'Diesel'},
    'promotionFlags': [],
    'conditionRaw': 'used',
    # --- Excluded fields: country-specific ---
    'vin': 'WBA3B31090F123456',
    'licensePlate': 'B-123-ABC',
    'drivetrain': 'awd',
    'steeringWheelSide': 'left-hand-drive',
    'doorCount': 4,
    'seatCount': 5,
    'registrationStatus': 'registered',
    'countryOfOrigin': 'DE',
    'customsCleared': 'yes',
    'ownersCount': 2,
    'co2Emissions': 132,
    'features': ['navigation', 'heated-seats', 'sunroof'],
    # --- Excluded fields: timestamps ---
    'postedAt': '2026-04-01T09:00:00Z',
    'refreshedAt': '2026-05-18T08:00:00Z',
    'validTo': '2026-06-01T00:00:00Z',
    'scrapedAt': '2026-05-18T10:05:00Z',
    # --- Excluded fields: pricing extras ---
    'priceNegotiable': False,
    'pricePrevious': 16500,
    'priceConverted': 74850,
    'priceCurrencyConverted': 'RON',
}


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
_pass_count = 0
_fail_count = 0
_failures: list[str] = []


def _pass(name: str) -> None:
    global _pass_count
    _pass_count += 1
    print(f"  PASS  {name}")


def _fail(name: str, msg: str) -> None:
    global _fail_count
    _fail_count += 1
    _failures.append(f"{name}: {msg}")
    print(f"  FAIL  {name}: {msg}")


def run_test(name: str, fn) -> None:
    try:
        fn()
        _pass(name)
    except AssertionError as exc:
        _fail(name, str(exc))
    except Exception as exc:
        _fail(name, f"Unexpected exception: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# T1 — full mode is a no-op
# ---------------------------------------------------------------------------
def test_T1():
    item = dict(SYNTHETIC_ITEM)
    result = shape_output(item, 'full', None)
    assert result is item, "shape_output should mutate in-place and return the same dict"
    assert result == SYNTHETIC_ITEM, (
        f"full mode + no truncation must return item equal to input\n"
        f"  extra keys: {set(result) - set(SYNTHETIC_ITEM)}\n"
        f"  missing keys: {set(SYNTHETIC_ITEM) - set(result)}"
    )


# ---------------------------------------------------------------------------
# T2 — compact mode retains only COMPACT_FIELDS
# ---------------------------------------------------------------------------
def test_T2():
    item = dict(SYNTHETIC_ITEM)
    result = shape_output(item, 'compact', None)
    # All keys must be a subset of COMPACT_FIELDS
    extra = set(result.keys()) - COMPACT_FIELDS
    assert not extra, f"compact mode emitted unexpected fields: {sorted(extra)}"
    # All COMPACT_FIELDS that were in the original input must still be present
    for field in COMPACT_FIELDS:
        if field in SYNTHETIC_ITEM:
            assert field in result, f"compact mode dropped expected compact field {field!r}"


# ---------------------------------------------------------------------------
# T3 — full mode + truncation truncates description, leaves all else untouched
# ---------------------------------------------------------------------------
def test_T3():
    item = dict(SYNTHETIC_ITEM)
    original_desc = SYNTHETIC_ITEM['description']
    result = shape_output(item, 'full', 100)
    # description truncated
    assert 'description' in result, "description should still be present (len > 0)"
    assert len(result['description']) <= 100, (
        f"description not truncated: len={len(result['description'])}"
    )
    # If original was longer than 100 chars, verify the slice is exact
    if len(original_desc) > 100:
        assert result['description'] == original_desc[:100], "description not sliced correctly"
    # All other fields unchanged
    for k, v in SYNTHETIC_ITEM.items():
        if k == 'description':
            continue
        assert k in result, f"field {k!r} disappeared after truncation"
        assert result[k] == v, f"field {k!r} changed after truncation"


# ---------------------------------------------------------------------------
# T4 — compact + truncation applies both filters
# ---------------------------------------------------------------------------
def test_T4():
    item = dict(SYNTHETIC_ITEM)
    result = shape_output(item, 'compact', 200)
    # Only compact fields
    extra = set(result.keys()) - COMPACT_FIELDS
    assert not extra, f"compact+truncation emitted non-compact fields: {sorted(extra)}"
    # description truncated
    if 'description' in result:
        assert len(result['description']) <= 200, (
            f"description not truncated: len={len(result['description'])}"
        )


# ---------------------------------------------------------------------------
# T5 — descriptionMaxLength=0 drops the description key entirely
# ---------------------------------------------------------------------------
def test_T5():
    item = dict(SYNTHETIC_ITEM)
    result = shape_output(item, 'compact', 0)
    assert 'description' not in result, (
        f"descriptionMaxLength=0 should drop description key, but key is present"
    )
    # Other compact fields still present
    for field in COMPACT_FIELDS - {'description'}:
        if field in SYNTHETIC_ITEM:
            assert field in result, f"field {field!r} disappeared with descriptionMaxLength=0"


# ---------------------------------------------------------------------------
# T6 — Unicode truncation is character-safe (not byte-based)
# ---------------------------------------------------------------------------
def test_T6():
    cyrillic_base = 'абв' * 200  # 600 Cyrillic characters
    item = {
        'offerId': 1,
        'description': cyrillic_base,
    }
    result = shape_output(item, 'full', 50)
    assert 'description' in result, "description should be present"
    actual_len = len(result['description'])
    assert actual_len == 50, (
        f"Unicode truncation: expected 50 characters, got {actual_len}. "
        f"Possible byte-based truncation."
    )
    assert result['description'] == cyrillic_base[:50], (
        f"Truncated text doesn't match expected slice"
    )

    # Also test with emoji + Romanian diacritics
    mixed = '🚗ă' * 100  # 200 chars of emoji+diacritic pairs
    item2 = {'offerId': 2, 'description': mixed}
    result2 = shape_output(item2, 'full', 30)
    assert len(result2['description']) == 30, (
        f"Mixed-Unicode truncation: expected 30 chars, got {len(result2['description'])}"
    )
    assert result2['description'] == mixed[:30]


# ---------------------------------------------------------------------------
# T7 — Item with no description field: shape_output leaves it unchanged
# ---------------------------------------------------------------------------
def test_T7():
    item = {
        'offerId': 999,
        'title': 'Dacia Logan',
        'price': 5000,
        'currency': 'EUR',
    }
    original = dict(item)
    result = shape_output(item, 'full', 100)
    assert result == original, (
        f"Item without description should be unchanged; diff: "
        f"extra={set(result)-set(original)}, missing={set(original)-set(result)}"
    )
    assert 'description' not in result, "description key must not be created"


# ---------------------------------------------------------------------------
# T8 — outputMode='garbage' treated as no-op; compact removes all excluded fields
# ---------------------------------------------------------------------------
def test_T8_garbage_is_noop():
    item = dict(SYNTHETIC_ITEM)
    result = shape_output(item, 'garbage', None)
    # 'garbage' is not 'compact' → no field filtering; no truncation
    assert result == SYNTHETIC_ITEM, (
        f"outputMode='garbage' should be a no-op; "
        f"diff keys: {set(result).symmetric_difference(set(SYNTHETIC_ITEM))}"
    )


def test_T8_compact_excluded_fields():
    # All these fields must be ABSENT in compact output
    excluded_fields = [
        'priceVsMedianPct', 'priceRating',
        'changeType', 'firstSeenAt', 'lastSeenAt', 'priceHistory', 'isRepost',
        'seller', 'location',
        'images', 'paramsRaw', 'extraAttributes', 'promotionFlags', 'conditionRaw',
        'vin', 'licensePlate', 'drivetrain', 'steeringWheelSide', 'doorCount',
        'seatCount', 'registrationStatus', 'countryOfOrigin', 'customsCleared',
        'ownersCount', 'co2Emissions', 'features',
        'postedAt', 'refreshedAt', 'validTo', 'scrapedAt',
        'priceNegotiable', 'pricePrevious', 'priceConverted', 'priceCurrencyConverted',
    ]
    item = dict(SYNTHETIC_ITEM)
    result = shape_output(item, 'compact', None)
    for field in excluded_fields:
        assert field not in result, (
            f"compact mode should exclude {field!r} but it is present"
        )


# ---------------------------------------------------------------------------
# T9 — COMPACT_FIELDS exactly equals the 18 approved fields
# ---------------------------------------------------------------------------
def test_T9():
    missing = EXPECTED_COMPACT_FIELDS - COMPACT_FIELDS
    extra = COMPACT_FIELDS - EXPECTED_COMPACT_FIELDS
    assert not missing and not extra, (
        f"COMPACT_FIELDS mismatch.\n"
        f"  Missing from COMPACT_FIELDS: {sorted(missing)}\n"
        f"  Unexpected in COMPACT_FIELDS: {sorted(extra)}"
    )
    assert len(COMPACT_FIELDS) == 18, (
        f"COMPACT_FIELDS should have exactly 18 fields, got {len(COMPACT_FIELDS)}: "
        f"{sorted(COMPACT_FIELDS)}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 60)
    print("Unit tests — shape_output() / COMPACT_FIELDS (Issue #24)")
    print("=" * 60)

    run_test("T1: full mode no-op", test_T1)
    run_test("T2: compact mode retains only COMPACT_FIELDS", test_T2)
    run_test("T3: full + descriptionMaxLength truncates description only", test_T3)
    run_test("T4: compact + descriptionMaxLength applies both filters", test_T4)
    run_test("T5: descriptionMaxLength=0 drops description key", test_T5)
    run_test("T6: Unicode truncation is character-safe", test_T6)
    run_test("T7: no description field — item unchanged", test_T7)
    run_test("T8a: outputMode='garbage' is no-op", test_T8_garbage_is_noop)
    run_test("T8b: compact excludes all expected fields", test_T8_compact_excluded_fields)
    run_test("T9: COMPACT_FIELDS is exactly the 18 approved fields", test_T9)

    print("=" * 60)
    total = _pass_count + _fail_count
    print(f"Results: {_pass_count}/{total} PASS, {_fail_count}/{total} FAIL")

    if _fail_count:
        print("\nFailed tests:")
        for msg in _failures:
            print(f"  - {msg}")
        print("\nFINAL: FAIL")
        return 1

    print("\nFINAL: ALL PASS")
    return 0


if __name__ == '__main__':
    sys.exit(main())
