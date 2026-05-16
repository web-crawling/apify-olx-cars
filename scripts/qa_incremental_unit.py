"""Unit tests for src/state.py — incremental scraping state management.

Tests compute_diff and compute_missing with synthetic inputs.
No Scrapy, no Apify SDK, no network — pure Python.

Scenarios covered:
  1. Cold start (NEW — offerId not in snapshot)
  2. UNCHANGED (all 5 tracked fields identical)
  3. UPDATED (price changed)
  4. REAPPEARED (was in snapshot with _missingCount > 0)
  5. MISSING with purge (absent listing increments _missingCount; purged at >= 3)
  6. MISSING emit suppressed when was_truncated=True
  7. _fields_changed helper: None == None treated as unchanged

Usage:
  python scripts/qa_incremental_unit.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure actor root is on sys.path
ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

from src.state import (
    MISSING_PURGE_THRESHOLD,
    TRACKED_FIELDS,
    _fields_changed,
    compute_diff,
    compute_missing,
)

RUN_TS = '2026-05-16T10:00:00+00:00'
RUN_TS2 = '2026-05-17T09:00:00+00:00'

PASS = 'PASS'
FAIL = 'FAIL'

results: list[tuple[str, str]] = []


def check(name: str, condition: bool, detail: str = '') -> None:
    status = PASS if condition else FAIL
    results.append((name, status))
    marker = '  OK' if condition else '  FAIL'
    extra = f' ({detail})' if detail else ''
    print(f'{marker}  {name}{extra}')


# ---------------------------------------------------------------------------
# 1. Cold start — NEW
# ---------------------------------------------------------------------------
item1 = {
    'offerId': 12345,
    'price': 15000,
    'currency': 'EUR',
    'condition': 'used',
    'mileageKm': 87000,
    'title': 'BMW 320d 2018',
}
snapshot_empty: dict = {}
change_type, first_seen, last_seen, entry = compute_diff(item1, snapshot_empty, RUN_TS)
check('cold_start.changeType==NEW', change_type == 'NEW', f'got {change_type!r}')
check('cold_start.firstSeenAt==run_ts', first_seen == RUN_TS, f'got {first_seen!r}')
check('cold_start.lastSeenAt==run_ts', last_seen == RUN_TS, f'got {last_seen!r}')
check('cold_start.entry.price', entry.get('price') == 15000)
check('cold_start.no_missingCount', '_missingCount' not in entry)

# ---------------------------------------------------------------------------
# 2. UNCHANGED — all 5 tracked fields identical
# ---------------------------------------------------------------------------
snapshot_with_item = {
    '12345': {
        'price': 15000,
        'currency': 'EUR',
        'condition': 'used',
        'mileageKm': 87000,
        'title': 'BMW 320d 2018',
        'firstSeenAt': RUN_TS,
        'lastSeenAt': RUN_TS,
    }
}
change_type, first_seen, last_seen, entry = compute_diff(item1, snapshot_with_item, RUN_TS2)
check('unchanged.changeType==UNCHANGED', change_type == 'UNCHANGED', f'got {change_type!r}')
check('unchanged.firstSeenAt preserved', first_seen == RUN_TS, f'got {first_seen!r}')
check('unchanged.lastSeenAt==run_ts2', last_seen == RUN_TS2, f'got {last_seen!r}')

# ---------------------------------------------------------------------------
# 3. UPDATED — price changed
# ---------------------------------------------------------------------------
item1_updated = dict(item1)
item1_updated['price'] = 14500  # price drop
change_type, first_seen, last_seen, entry = compute_diff(item1_updated, snapshot_with_item, RUN_TS2)
check('updated.changeType==UPDATED', change_type == 'UPDATED', f'got {change_type!r}')
check('updated.firstSeenAt preserved', first_seen == RUN_TS, f'got {first_seen!r}')
check('updated.entry.price==14500', entry.get('price') == 14500)

# ---------------------------------------------------------------------------
# 4. REAPPEARED — was missing in prior run (_missingCount > 0)
# ---------------------------------------------------------------------------
snapshot_missing_once = {
    '12345': {
        'price': 15000,
        'currency': 'EUR',
        'condition': 'used',
        'mileageKm': 87000,
        'title': 'BMW 320d 2018',
        'firstSeenAt': RUN_TS,
        'lastSeenAt': RUN_TS,
        '_missingCount': 1,
    }
}
change_type, first_seen, last_seen, entry = compute_diff(item1, snapshot_missing_once, RUN_TS2)
check('reappeared.changeType==REAPPEARED', change_type == 'REAPPEARED', f'got {change_type!r}')
check('reappeared.firstSeenAt preserved', first_seen == RUN_TS, f'got {first_seen!r}')
check('reappeared.no_missingCount', '_missingCount' not in entry)

# ---------------------------------------------------------------------------
# 5. compute_missing — absent listing increments _missingCount; purge at >= 3
# ---------------------------------------------------------------------------
# Build a snapshot with 3 entries; run sees only offerId 99999
snapshot_for_missing = {
    '11111': {
        'price': 5000, 'currency': 'RON', 'title': 'VW Golf',
        'firstSeenAt': RUN_TS, 'lastSeenAt': RUN_TS,
    },
    '22222': {
        'price': 8000, 'currency': 'EUR', 'title': 'Audi A3',
        'firstSeenAt': RUN_TS, 'lastSeenAt': RUN_TS,
        '_missingCount': 2,  # will hit threshold == 3 → purge
    },
    '99999': {
        'price': 1000, 'currency': 'KZT', 'title': 'Lada',
        'firstSeenAt': RUN_TS, 'lastSeenAt': RUN_TS,
    },
}
seen_ids = {'99999'}  # only this was scraped
missing_items = compute_missing(
    snapshot=snapshot_for_missing,
    seen_ids=seen_ids,
    emit_missing=True,
    run_ts=RUN_TS2,
    was_truncated=False,
)
check('missing.count==2', len(missing_items) == 2, f'got {len(missing_items)}')
missing_change_types = {m['changeType'] for m in missing_items}
check('missing.all_MISSING', missing_change_types == {'MISSING'}, f'got {missing_change_types}')
# 11111 should be at _missingCount=1 in snapshot
check('missing.11111_count==1', snapshot_for_missing.get('11111', {}).get('_missingCount') == 1)
# 22222 should be purged (was at _missingCount=2, now 3 >= threshold)
check('missing.22222_purged', '22222' not in snapshot_for_missing)
# 99999 should still be in snapshot (it was seen)
check('missing.99999_still_in_snapshot', '99999' in snapshot_for_missing)

# ---------------------------------------------------------------------------
# 6. compute_missing — suppressed when was_truncated=True
# ---------------------------------------------------------------------------
snapshot_truncated = {
    '55555': {'price': 1000, 'currency': 'EUR', 'title': 'Test', 'firstSeenAt': RUN_TS, 'lastSeenAt': RUN_TS},
}
missing_suppressed = compute_missing(
    snapshot=snapshot_truncated,
    seen_ids=set(),
    emit_missing=True,
    run_ts=RUN_TS2,
    was_truncated=True,
)
check('truncated.no_missing_emitted', len(missing_suppressed) == 0, f'got {len(missing_suppressed)}')
# Snapshot should NOT have been mutated (was_truncated → early return)
check('truncated.snapshot_unmutated', '_missingCount' not in snapshot_truncated.get('55555', {}))

# ---------------------------------------------------------------------------
# 7. _fields_changed — None == None is unchanged
# ---------------------------------------------------------------------------
item_with_none = {'price': None, 'currency': None, 'condition': None, 'mileageKm': None, 'title': 'Test'}
prior_with_none = {'price': None, 'currency': None, 'condition': None, 'mileageKm': None, 'title': 'Test'}
check('fields_changed.none_eq_none==False', not _fields_changed(item_with_none, prior_with_none))

item_none_vs_val = {'price': None, 'currency': None, 'condition': None, 'mileageKm': None, 'title': 'Test'}
prior_val = {'price': 1000, 'currency': None, 'condition': None, 'mileageKm': None, 'title': 'Test'}
check('fields_changed.none_vs_value==True', _fields_changed(item_none_vs_val, prior_val))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = len(results)
passed = sum(1 for _, s in results if s == PASS)
failed = total - passed

print()
print(f'Results: {passed}/{total} passed')
if failed:
    print('FAILED tests:')
    for name, status in results:
        if status == FAIL:
            print(f'  - {name}')
    sys.exit(1)
else:
    print('ALL PASS')
    sys.exit(0)
