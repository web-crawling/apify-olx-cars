"""Pipeline-level integration tests for IncrementalDiffPipeline (olx-cars #17).

Tests exercise the actual IncrementalDiffPipeline.process_item / open_spider /
close_spider chain with a MockSpider (settings dict + logger), not just the
pure state functions (those are covered by qa_incremental_unit.py).

Scenarios:
  1. Pass-through when incrementalMode: false — no change fields, no KV I/O
  2. Cold start (empty snapshot) — items flow through, UNCHANGED are dropped
  3. Second run with mixed change types (NEW / UNCHANGED / UPDATED)
  4. Within-run deduplication — second same offerId is DropItem'd
  5. maxItems truncation suppresses MISSING (was_truncated set in close_spider)
  6. Items.py field availability — changeType/firstSeenAt/lastSeenAt on CarItem

Usage:
  python scripts/qa_incremental_pipeline.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure actor root is on sys.path
ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

from scrapy.exceptions import DropItem

from src.items import CarItem
from src.pipelines import IncrementalDiffPipeline
from src.state import compute_missing

# ── Test infrastructure ─────────────────────────────────────────────────────

logging.basicConfig(level=logging.WARNING)

RUN_TS = '2026-05-16T10:00:00+00:00'
RUN_TS2 = '2026-05-17T09:00:00+00:00'

results: list[tuple[str, str]] = []

PASS = 'PASS'
FAIL = 'FAIL'


def check(name: str, condition: bool, detail: str = '') -> None:
    status = PASS if condition else FAIL
    results.append((name, status))
    marker = '  OK' if condition else '  FAIL'
    extra = f' ({detail})' if detail else ''
    print(f'{marker}  {name}{extra}')


class MockSettings:
    """Minimal Scrapy settings stand-in that supports .get()."""

    def __init__(self, input_data: dict):
        self._data = {'INPUT_DATA': input_data}

    def get(self, key, default=None):
        return self._data.get(key, default)


class MockSpider:
    """Minimal spider stand-in with settings + logger."""

    def __init__(self, input_data: dict):
        self.settings = MockSettings(input_data)
        self.logger = logging.getLogger('mock_spider')


def make_car_item(**kwargs) -> CarItem:
    """Build a minimal CarItem with required fields."""
    item = CarItem()
    item['offerId'] = kwargs.get('offerId', 99999)
    item['title'] = kwargs.get('title', 'Test Car')
    item['url'] = kwargs.get('url', 'https://www.olx.ro/d/oferta/test.html')
    item['country'] = kwargs.get('country', 'ro')
    item['scrapedAt'] = kwargs.get('scrapedAt', RUN_TS)
    item['features'] = []
    item['images'] = []
    item['paramsRaw'] = []
    for k, v in kwargs.items():
        if k not in ('offerId', 'title', 'url', 'country', 'scrapedAt'):
            try:
                item[k] = v
            except KeyError:
                pass  # field not in CarItem — skip
    return item


def run_pipeline_item(pipeline: IncrementalDiffPipeline, item, spider: MockSpider):
    """Call process_item; return (result_item, raised_DropItem_or_None)."""
    try:
        result = pipeline.process_item(item, spider)
        return result, None
    except DropItem as e:
        return None, e


# ── Scenario 1: Pass-through when incrementalMode: false ────────────────────

print('\n--- Scenario 1: Pass-through when incrementalMode=False ---')

input_data_passthrough = {
    'incrementalMode': False,
    'emitUnchanged': False,
    'emitMissing': False,
    'maxItems': 1000,
    '_snapshot': {},
    '_runTs': RUN_TS,
}
spider1 = MockSpider(input_data_passthrough)
pipeline1 = IncrementalDiffPipeline()
pipeline1.open_spider(spider1)

item_pt = make_car_item(offerId=11111, price=10000, currency='EUR', title='VW Golf')
result_pt, drop_pt = run_pipeline_item(pipeline1, item_pt, spider1)

check('passthrough.item_returned', result_pt is not None)
check('passthrough.no_drop', drop_pt is None)
check('passthrough.no_changeType', result_pt is not None and 'changeType' not in result_pt)
check('passthrough.no_firstSeenAt', result_pt is not None and 'firstSeenAt' not in result_pt)
check('passthrough.no_lastSeenAt', result_pt is not None and 'lastSeenAt' not in result_pt)

# KV state should NOT be populated (no snapshot changes when mode is off)
check('passthrough.seen_ids_empty', len(IncrementalDiffPipeline.seen_offer_ids) == 0)
check('passthrough.snapshot_unchanged', IncrementalDiffPipeline.updated_snapshot == {})

pipeline1.close_spider(spider1)
check('passthrough.not_truncated', IncrementalDiffPipeline.was_truncated == False)

# ── Scenario 2: Cold start (empty snapshot) ──────────────────────────────────

print('\n--- Scenario 2: Cold start (empty snapshot) ---')

input_data_cold = {
    'incrementalMode': True,
    'emitUnchanged': False,
    'emitMissing': False,
    'maxItems': 1000,
    '_snapshot': {},
    '_runTs': RUN_TS,
}
spider2 = MockSpider(input_data_cold)
pipeline2 = IncrementalDiffPipeline()
pipeline2.open_spider(spider2)

item_new1 = make_car_item(offerId=10001, price=15000, currency='EUR',
                           title='BMW 320d', condition='used', mileageKm=87000)
item_new2 = make_car_item(offerId=10002, price=8000, currency='RON',
                           title='VW Polo', condition='used', mileageKm=120000)

result_n1, drop_n1 = run_pipeline_item(pipeline2, item_new1, spider2)
result_n2, drop_n2 = run_pipeline_item(pipeline2, item_new2, spider2)

# Cold start: NEW items are SILENTLY DROPPED (baseline build).
# The snapshot still accumulates so the next run has state to diff against.
check('cold_start.item1_dropped', result_n1 is None, f'expected DropItem, got {result_n1!r}')
check('cold_start.item1_is_dropitem', drop_n1 is not None and isinstance(drop_n1, DropItem))
check('cold_start.item2_dropped', result_n2 is None, f'expected DropItem, got {result_n2!r}')
check('cold_start.item2_is_dropitem', drop_n2 is not None and isinstance(drop_n2, DropItem))

# Snapshot should still be accumulated (2 entries) — baseline build's job
check('cold_start.snapshot_has_2', len(IncrementalDiffPipeline.updated_snapshot) == 2,
      f"got {len(IncrementalDiffPipeline.updated_snapshot)}")
check('cold_start.seen_ids_count', len(IncrementalDiffPipeline.seen_offer_ids) == 2)

# Snapshot entries should have correct shape (firstSeenAt + tracked fields)
snap_entry_1 = IncrementalDiffPipeline.updated_snapshot.get('10001', {})
check('cold_start.snap_entry_has_firstSeenAt', snap_entry_1.get('firstSeenAt') == RUN_TS,
      f"got {snap_entry_1.get('firstSeenAt')!r}")
check('cold_start.snap_entry_has_price', snap_entry_1.get('price') == 15000)

# Now add an UNCHANGED item (simulate: feed same offerId with same fields again using
# the updated snapshot as the starting snapshot for next call within same run)
# Actually within same cold-start run, once 10001 is in updated_snapshot, feeding
# the pipeline uses self._snapshot (the ORIGINAL empty dict), not updated_snapshot.
# So a second different item just goes as NEW. The UNCHANGED drop test belongs in
# Scenario 3. But we test the UNCHANGED drop here by creating a NEW pipeline with
# pre-populated snapshot.

# Test UNCHANGED drop: feed an item that matches snapshot → should be DropItem'd
snapshot_with_item = {
    '10001': {
        'price': 15000, 'currency': 'EUR', 'condition': 'used',
        'mileageKm': 87000, 'title': 'BMW 320d',
        'firstSeenAt': RUN_TS, 'lastSeenAt': RUN_TS,
    }
}
input_data_unchanged_drop = {
    'incrementalMode': True,
    'emitUnchanged': False,  # default — UNCHANGED items are dropped
    'emitMissing': False,
    'maxItems': 1000,
    '_snapshot': snapshot_with_item,
    '_runTs': RUN_TS2,
}
spider2b = MockSpider(input_data_unchanged_drop)
pipeline2b = IncrementalDiffPipeline()
pipeline2b.open_spider(spider2b)

item_unchanged = make_car_item(offerId=10001, price=15000, currency='EUR',
                                title='BMW 320d', condition='used', mileageKm=87000)
result_unch, drop_unch = run_pipeline_item(pipeline2b, item_unchanged, spider2b)

check('cold_start.unchanged_dropped', result_unch is None,
      'UNCHANGED item should be DropItem when emitUnchanged=False')
check('cold_start.unchanged_is_dropitem', drop_unch is not None and isinstance(drop_unch, DropItem))

pipeline2.close_spider(spider2)

# ── Scenario 3: Second run with mixed change types ────────────────────────────

print('\n--- Scenario 3: Mixed change types (NEW / UNCHANGED / UPDATED) ---')

# Pre-populated snapshot: two existing entries
snapshot_s3 = {
    '20001': {
        'price': 20000, 'currency': 'EUR', 'condition': 'used',
        'mileageKm': 50000, 'title': 'Audi A4',
        'firstSeenAt': RUN_TS, 'lastSeenAt': RUN_TS,
    },
    '20002': {
        'price': 5000, 'currency': 'RON', 'condition': 'used',
        'mileageKm': 200000, 'title': 'Dacia Logan',
        'firstSeenAt': RUN_TS, 'lastSeenAt': RUN_TS,
    },
}

input_data_s3 = {
    'incrementalMode': True,
    'emitUnchanged': True,  # emit UNCHANGED for this test
    'emitMissing': False,
    'maxItems': 1000,
    '_snapshot': snapshot_s3,
    '_runTs': RUN_TS2,
}
spider3 = MockSpider(input_data_s3)
pipeline3 = IncrementalDiffPipeline()
pipeline3.open_spider(spider3)

# UNCHANGED: same fields as snapshot
item_unch3 = make_car_item(offerId=20001, price=20000, currency='EUR',
                            condition='used', mileageKm=50000, title='Audi A4')
# UPDATED: price changed
item_upd3 = make_car_item(offerId=20002, price=4800, currency='RON',
                           condition='used', mileageKm=200000, title='Dacia Logan')
# NEW: not in snapshot
item_new3 = make_car_item(offerId=20003, price=12000, currency='EUR',
                           condition='new', mileageKm=1000, title='Skoda Octavia')

result_unch3, drop_unch3 = run_pipeline_item(pipeline3, item_unch3, spider3)
result_upd3, drop_upd3 = run_pipeline_item(pipeline3, item_upd3, spider3)
result_new3, drop_new3 = run_pipeline_item(pipeline3, item_new3, spider3)

# UNCHANGED should pass through (emitUnchanged=True)
check('mixed.unchanged_passed', result_unch3 is not None, f'drop={drop_unch3}')
if result_unch3 is not None:
    check('mixed.unchanged_changeType',
          result_unch3.get('changeType') == 'UNCHANGED',
          f"got {result_unch3.get('changeType')!r}")
    check('mixed.unchanged_firstSeenAt_preserved',
          result_unch3.get('firstSeenAt') == RUN_TS,
          f"got {result_unch3.get('firstSeenAt')!r}")
    check('mixed.unchanged_lastSeenAt_updated',
          result_unch3.get('lastSeenAt') == RUN_TS2,
          f"got {result_unch3.get('lastSeenAt')!r}")

# UPDATED should pass through
check('mixed.updated_passed', result_upd3 is not None, f'drop={drop_upd3}')
if result_upd3 is not None:
    check('mixed.updated_changeType',
          result_upd3.get('changeType') == 'UPDATED',
          f"got {result_upd3.get('changeType')!r}")
    check('mixed.updated_firstSeenAt_preserved',
          result_upd3.get('firstSeenAt') == RUN_TS,
          f"got {result_upd3.get('firstSeenAt')!r}")
    check('mixed.updated_lastSeenAt_updated',
          result_upd3.get('lastSeenAt') == RUN_TS2,
          f"got {result_upd3.get('lastSeenAt')!r}")

# NEW should pass through
check('mixed.new_passed', result_new3 is not None, f'drop={drop_new3}')
if result_new3 is not None:
    check('mixed.new_changeType',
          result_new3.get('changeType') == 'NEW',
          f"got {result_new3.get('changeType')!r}")
    check('mixed.new_firstSeenAt',
          result_new3.get('firstSeenAt') == RUN_TS2,
          f"got {result_new3.get('firstSeenAt')!r}")

# snapshot should now have 3 entries
check('mixed.snapshot_3_entries',
      len(IncrementalDiffPipeline.updated_snapshot) == 3,
      f"got {len(IncrementalDiffPipeline.updated_snapshot)}")

# Verify that firstSeenAt is immutable for UNCHANGED (original RUN_TS preserved in snapshot)
check('mixed.unchanged_snapshot_firstSeenAt_preserved',
      IncrementalDiffPipeline.updated_snapshot.get('20001', {}).get('firstSeenAt') == RUN_TS)

pipeline3.close_spider(spider3)

# ── Scenario 4: Within-run deduplication ─────────────────────────────────────

print('\n--- Scenario 4: Within-run deduplication ---')

# Pre-populate snapshot so this is NOT cold-start mode — the dedup test wants
# to verify the second occurrence is dropped, which requires the first one to
# actually flow through (not be silently suppressed as cold-start baseline).
input_data_s4 = {
    'incrementalMode': True,
    'emitUnchanged': True,
    'emitMissing': False,
    'maxItems': 1000,
    '_snapshot': {
        '99999': {  # unrelated prior entry — makes snapshot non-empty
            'price': 1, 'currency': 'EUR', 'title': 'Sentinel',
            'firstSeenAt': RUN_TS, 'lastSeenAt': RUN_TS,
        },
    },
    '_runTs': RUN_TS,
}
spider4 = MockSpider(input_data_s4)
pipeline4 = IncrementalDiffPipeline()
pipeline4.open_spider(spider4)

# Feed same offerId twice
item_dup1 = make_car_item(offerId=30001, price=9000, currency='EUR', title='Ford Focus')
item_dup2 = make_car_item(offerId=30001, price=9000, currency='EUR', title='Ford Focus')

result_dup1, drop_dup1 = run_pipeline_item(pipeline4, item_dup1, spider4)
result_dup2, drop_dup2 = run_pipeline_item(pipeline4, item_dup2, spider4)

check('dedup.first_item_passed', result_dup1 is not None, f'drop={drop_dup1}')
check('dedup.second_item_dropped', result_dup2 is None, 'second occurrence should be DropItem')
check('dedup.second_is_dropitem', drop_dup2 is not None and isinstance(drop_dup2, DropItem))
# Snapshot should have only one entry for this offerId
check('dedup.snapshot_one_entry',
      len(IncrementalDiffPipeline.seen_offer_ids) == 1,
      f"got {len(IncrementalDiffPipeline.seen_offer_ids)}")

pipeline4.close_spider(spider4)

# ── Scenario 5: maxItems truncation suppresses MISSING ─────────────────────

print('\n--- Scenario 5: maxItems truncation suppresses MISSING ---')

# Simulate: maxItems=3, and we've seen exactly 3 items → truncated
# (IncrementalDiffPipeline sets was_truncated in close_spider when seen >= maxItems)
snapshot_s5 = {
    'old1': {'price': 1000, 'currency': 'EUR', 'title': 'Old Car 1',
             'firstSeenAt': RUN_TS, 'lastSeenAt': RUN_TS},
    'old2': {'price': 2000, 'currency': 'EUR', 'title': 'Old Car 2',
             'firstSeenAt': RUN_TS, 'lastSeenAt': RUN_TS},
    'old3': {'price': 3000, 'currency': 'EUR', 'title': 'Old Car 3',
             'firstSeenAt': RUN_TS, 'lastSeenAt': RUN_TS},
}

input_data_s5 = {
    'incrementalMode': True,
    'emitUnchanged': True,
    'emitMissing': True,
    'maxItems': 3,  # matches the 3 items we'll feed → truncation detected
    '_snapshot': snapshot_s5,
    '_runTs': RUN_TS2,
}
spider5 = MockSpider(input_data_s5)
pipeline5 = IncrementalDiffPipeline()
pipeline5.open_spider(spider5)

# Feed exactly maxItems=3 NEW items (all new offerIds → distinct from snapshot)
for i in range(3):
    new_item = make_car_item(offerId=40000 + i, price=1000 * (i + 1),
                              currency='EUR', title=f'New Car {i}')
    run_pipeline_item(pipeline5, new_item, spider5)

# Close spider — should set was_truncated = True (seen 3 >= maxItems 3)
pipeline5.close_spider(spider5)

check('truncation.was_truncated_set',
      IncrementalDiffPipeline.was_truncated == True,
      f"was_truncated={IncrementalDiffPipeline.was_truncated}")

# compute_missing should return [] when was_truncated=True
# (It also should NOT mutate snapshot — old entries keep no _missingCount increment)
import copy
snapshot_before = copy.deepcopy(IncrementalDiffPipeline.updated_snapshot)
missing = compute_missing(
    snapshot=IncrementalDiffPipeline.updated_snapshot,
    seen_ids=IncrementalDiffPipeline.seen_offer_ids,
    emit_missing=True,
    run_ts=RUN_TS2,
    was_truncated=IncrementalDiffPipeline.was_truncated,
)
check('truncation.missing_empty', len(missing) == 0,
      f"got {len(missing)} MISSING items (should be 0 when truncated)")

# Snapshot entries for old1/old2/old3 should NOT have _missingCount incremented
# (they're in the snapshot but not in seen_ids — however was_truncated=True suppresses)
# The compute_missing early-return means snapshot is unmutated
for old_key in ('old1', 'old2', 'old3'):
    entry = IncrementalDiffPipeline.updated_snapshot.get(old_key, {})
    check(f'truncation.{old_key}_no_missingCount',
          '_missingCount' not in entry,
          f"entry={entry}")

# ── Scenario 6: Items.py field availability ──────────────────────────────────

print('\n--- Scenario 6: CarItem field availability ---')

# Verify changeType / firstSeenAt / lastSeenAt can be assigned without KeyError
try:
    test_item = CarItem()
    test_item['changeType'] = 'NEW'
    test_item['firstSeenAt'] = RUN_TS
    test_item['lastSeenAt'] = RUN_TS2
    check('items_fields.changeType_assignable', test_item['changeType'] == 'NEW')
    check('items_fields.firstSeenAt_assignable', test_item['firstSeenAt'] == RUN_TS)
    check('items_fields.lastSeenAt_assignable', test_item['lastSeenAt'] == RUN_TS2)
except KeyError as e:
    check('items_fields.changeType_assignable', False, f'KeyError: {e}')
    check('items_fields.firstSeenAt_assignable', False)
    check('items_fields.lastSeenAt_assignable', False)

# Verify fields are absent by default (not preset to None on a fresh CarItem)
fresh_item = CarItem()
# Scrapy Items raise KeyError on access if field was never set
try:
    _ = fresh_item['changeType']
    check('items_fields.changeType_absent_by_default', False,
          'Expected KeyError — field should not be set by default')
except KeyError:
    check('items_fields.changeType_absent_by_default', True)

# ── Summary ──────────────────────────────────────────────────────────────────

total = len(results)
passed = sum(1 for _, s in results if s == PASS)
failed = total - passed

print(f'\nResults: {passed}/{total} passed')
if failed:
    print('FAILED tests:')
    for name, status in results:
        if status == FAIL:
            print(f'  - {name}')
    sys.exit(1)
else:
    print('ALL PASS')
    sys.exit(0)
