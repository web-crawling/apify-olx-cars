"""Unit tests for HistoryFilterPipeline.process_item — Issue #51 (`serviceBookOnly`).

Covers all 15 test cases from architecture § 4 → qa role:
  1.  BG fixture, conditionRaw='service-book', serviceBookOnly=True            -> kept
  2.  BG fixture, conditionRaw='technically-upright', serviceBookOnly=True     -> dropped
  3.  BG fixture, conditionRaw='first-owner', serviceBookOnly=True             -> dropped
  4.  BG fixture, conditionRaw=None, serviceBookOnly=True                      -> kept (false-negative-keep)
  5.  BG fixture, conditionRaw='with-improvements', serviceBookOnly=True       -> dropped (substring trap)
  6.  BG fixture, conditionRaw='something;service-book;else'                   -> kept (set membership)
  7.  RO fixture, conditionRaw='used', serviceBookOnly=True                    -> kept + INFO log
  8.  PL fixture, conditionRaw='notdamaged', serviceBookOnly=True              -> kept + INFO log
  9.  PT fixture, conditionRaw='usado', serviceBookOnly=True                   -> kept + INFO log
  10. UA fixture, conditionRaw='first-owner;service-book'                      -> kept + INFO log (country gate trumps slug)
  11. KZ fixture, conditionRaw='perfect', serviceBookOnly=True                 -> kept + INFO log
  12. INFO log fires exactly once per (filter, country) cell across 5 items
  13. reset() clears _logged_inapplicable between simulated runs
  14. All-three-filters-on, BG, conditionRaw='service-book' (intersection trap)-> dropped by firstOwnerOnly
  15. All-three-filters-on, BG, conditionRaw='service-book;first-owner'        -> kept by all three filters

Mirrors the shape of `scripts/qa23_filter_unit.py`. Runs offline (no network).
"""

from __future__ import annotations

import io
import sys
import logging
from pathlib import Path

# Force UTF-8 stdout on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

from scrapy.exceptions import DropItem
from src.pipelines import HistoryFilterPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = 'PASS'
FAIL = 'FAIL'
results: list[tuple[str, str, str]] = []


def check(label: str, ok: bool, detail: str = '') -> None:
    status = PASS if ok else FAIL
    results.append((status, label, detail))
    mark = '  OK  ' if ok else ' FAIL '
    extra = f' -- {detail}' if detail else ''
    print(f'[{mark}] {label}{extra}')


def make_pipeline(
    exclude_damaged: bool = False,
    first_owner_only: bool = False,
    service_book_only: bool = False,
) -> HistoryFilterPipeline:
    """Build a pipeline instance mimicking open_spider behaviour.

    Does NOT call reset() so the caller controls when the class-level
    _logged_inapplicable set is cleared.
    """
    pipeline = HistoryFilterPipeline()
    pipeline._exclude_damaged = exclude_damaged
    pipeline._first_owner_only = first_owner_only
    pipeline._service_book_only = service_book_only
    return pipeline


class CapturingLogger:
    """Spider-style logger that captures INFO/WARN calls into a list."""

    def __init__(self) -> None:
        self.records: list[str] = []

    def info(self, msg, *args):
        text = msg % args if args else msg
        self.records.append(text)

    def warning(self, msg, *args):
        text = msg % args if args else msg
        self.records.append(text)

    def debug(self, *args, **kwargs):
        pass


class FakeSpider:
    """Minimal spider stub with a capturing logger."""

    def __init__(self) -> None:
        self.logger = CapturingLogger()


def item(
    country: str,
    condition: str | None = None,
    condition_raw=None,
    owners_count=None,
    offer_id: int = 999,
) -> dict:
    """Build a minimal item dict."""
    d: dict = {'offerId': offer_id, 'country': country}
    if condition is not None:
        d['condition'] = condition
    if condition_raw is not None:
        d['conditionRaw'] = condition_raw
    if owners_count is not None:
        d['ownersCount'] = owners_count
    return d


def expect_pass(pipeline, it, spider, label):
    try:
        result = pipeline.process_item(it, spider)
        check(label, result is not None, 'item returned (not dropped)')
    except DropItem as e:
        check(label, False, f'unexpected DropItem raised: {e}')


def expect_drop(pipeline, it, spider, label):
    try:
        pipeline.process_item(it, spider)
        check(label, False, 'DropItem NOT raised -- expected drop')
    except DropItem:
        check(label, True, 'DropItem raised as expected')


# ===========================================================================
# Tests
# ===========================================================================

print('=' * 72)
print('qa51_servicebook_unit -- 15 cases')
print('=' * 72)

# ---------------------------------------------------------------------------
# 1. BG fixture, conditionRaw='service-book', serviceBookOnly=True -> kept
# ---------------------------------------------------------------------------
print('\n--- 1. BG conditionRaw=service-book, serviceBookOnly=True -> kept ---')
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
expect_pass(p, item('bg', condition_raw='service-book', offer_id=1), spider,
            'BG conditionRaw=service-book -> kept')

# ---------------------------------------------------------------------------
# 2. BG fixture, conditionRaw='technically-upright', serviceBookOnly=True -> dropped
# ---------------------------------------------------------------------------
print('\n--- 2. BG conditionRaw=technically-upright, serviceBookOnly=True -> drop ---')
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
expect_drop(p, item('bg', condition_raw='technically-upright', offer_id=2), spider,
            'BG conditionRaw=technically-upright -> DropItem (exact-slug semantics)')

# ---------------------------------------------------------------------------
# 3. BG fixture, conditionRaw='first-owner', serviceBookOnly=True -> dropped
# ---------------------------------------------------------------------------
print('\n--- 3. BG conditionRaw=first-owner, serviceBookOnly=True -> drop ---')
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
expect_drop(p, item('bg', condition_raw='first-owner', offer_id=3), spider,
            'BG conditionRaw=first-owner -> DropItem (different BG condition slug)')

# ---------------------------------------------------------------------------
# 4. BG fixture, conditionRaw=None, serviceBookOnly=True -> kept (false-negative-keep)
# ---------------------------------------------------------------------------
print('\n--- 4. BG conditionRaw=None, serviceBookOnly=True -> pass (false-negative-keep) ---')
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
# Item with no conditionRaw key at all (mimics DropNonesPipeline having stripped it)
it_bg_no_raw = {'offerId': 4, 'country': 'bg'}
expect_pass(p, it_bg_no_raw, spider,
            'BG conditionRaw absent -> kept (R6 policy)')

# ---------------------------------------------------------------------------
# 5. BG fixture, conditionRaw='with-improvements', serviceBookOnly=True -> dropped
# ---------------------------------------------------------------------------
print('\n--- 5. BG conditionRaw=with-improvements, serviceBookOnly=True -> drop (substring trap check) ---')
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
# `with-improvements` does NOT contain the exact slug `service-book` -> drop
expect_drop(p, item('bg', condition_raw='with-improvements', offer_id=5), spider,
            'BG conditionRaw=with-improvements -> DropItem (substring trap correctly avoided)')

# ---------------------------------------------------------------------------
# 6. BG fixture, conditionRaw='something;service-book;else', serviceBookOnly=True -> kept
# ---------------------------------------------------------------------------
print("\n--- 6. BG conditionRaw='something;service-book;else' -> kept (set membership) ---")
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
expect_pass(p, item('bg', condition_raw='something;service-book;else', offer_id=6), spider,
            "BG conditionRaw=';'-joined with service-book -> kept (set membership)")

# ---------------------------------------------------------------------------
# 7. RO fixture, conditionRaw='used', serviceBookOnly=True -> kept + INFO log
# ---------------------------------------------------------------------------
print('\n--- 7. RO unsupported -> pass + INFO log ---')
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
expect_pass(p, item('ro', condition_raw='used', offer_id=7), spider,
            'RO (unsupported) -> kept')
check(
    'RO: _logged_inapplicable contains (serviceBookOnly, ro)',
    ('serviceBookOnly', 'ro') in HistoryFilterPipeline._logged_inapplicable,
    f'set={sorted(HistoryFilterPipeline._logged_inapplicable)}',
)
ro_logs = [r for r in spider.logger.records
           if 'serviceBookOnly' in r and "'ro'" in r]
check('RO: INFO log fires for serviceBookOnly inapplicable', len(ro_logs) == 1,
      f'found {len(ro_logs)} matching log records (expected exactly 1)')

# ---------------------------------------------------------------------------
# 8. PL fixture, conditionRaw='notdamaged', serviceBookOnly=True -> kept + INFO log
# ---------------------------------------------------------------------------
print('\n--- 8. PL unsupported -> pass + INFO log ---')
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
expect_pass(p, item('pl', condition_raw='notdamaged', offer_id=8), spider,
            'PL (unsupported) -> kept')
check(
    'PL: _logged_inapplicable contains (serviceBookOnly, pl)',
    ('serviceBookOnly', 'pl') in HistoryFilterPipeline._logged_inapplicable,
    f'set={sorted(HistoryFilterPipeline._logged_inapplicable)}',
)
pl_logs = [r for r in spider.logger.records
           if 'serviceBookOnly' in r and "'pl'" in r]
check('PL: INFO log fires for serviceBookOnly inapplicable', len(pl_logs) == 1,
      f'found {len(pl_logs)} matching log records (expected exactly 1)')

# ---------------------------------------------------------------------------
# 9. PT fixture, conditionRaw='usado', serviceBookOnly=True -> kept + INFO log
# ---------------------------------------------------------------------------
print('\n--- 9. PT unsupported -> pass + INFO log ---')
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
expect_pass(p, item('pt', condition_raw='usado', offer_id=9), spider,
            'PT (unsupported) -> kept')
check(
    'PT: _logged_inapplicable contains (serviceBookOnly, pt)',
    ('serviceBookOnly', 'pt') in HistoryFilterPipeline._logged_inapplicable,
    f'set={sorted(HistoryFilterPipeline._logged_inapplicable)}',
)
pt_logs = [r for r in spider.logger.records
           if 'serviceBookOnly' in r and "'pt'" in r]
check('PT: INFO log fires for serviceBookOnly inapplicable', len(pt_logs) == 1,
      f'found {len(pt_logs)} matching log records (expected exactly 1)')

# ---------------------------------------------------------------------------
# 10. UA fixture, conditionRaw='first-owner;service-book' -> kept + INFO log
#     (country gate trumps slug; UA is NOT in _SERVICE_BOOK_COUNTRIES)
# ---------------------------------------------------------------------------
print("\n--- 10. UA conditionRaw='first-owner;service-book' -> pass + log (country gate trumps slug) ---")
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
# Critical: even though the slug `service-book` is present in the joined string,
# UA is NOT in _SERVICE_BOOK_COUNTRIES, so the country gate runs first and the
# slug check is never reached -> item passes through and one INFO log fires.
expect_pass(p, item('ua', condition_raw='first-owner;service-book', offer_id=10), spider,
            'UA with service-book slug present -> kept (country gate trumps slug)')
check(
    'UA: _logged_inapplicable contains (serviceBookOnly, ua)',
    ('serviceBookOnly', 'ua') in HistoryFilterPipeline._logged_inapplicable,
    f'set={sorted(HistoryFilterPipeline._logged_inapplicable)}',
)
ua_logs = [r for r in spider.logger.records
           if 'serviceBookOnly' in r and "'ua'" in r]
check('UA: INFO log fires once for serviceBookOnly inapplicable', len(ua_logs) == 1,
      f'found {len(ua_logs)} matching log records (expected exactly 1)')

# ---------------------------------------------------------------------------
# 11. KZ fixture -> kept + INFO log
# ---------------------------------------------------------------------------
print('\n--- 11. KZ unsupported -> pass + INFO log ---')
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
expect_pass(p, item('kz', condition_raw='perfect', offer_id=11), spider,
            'KZ (unsupported) -> kept')
check(
    'KZ: _logged_inapplicable contains (serviceBookOnly, kz)',
    ('serviceBookOnly', 'kz') in HistoryFilterPipeline._logged_inapplicable,
    f'set={sorted(HistoryFilterPipeline._logged_inapplicable)}',
)
kz_logs = [r for r in spider.logger.records
           if 'serviceBookOnly' in r and "'kz'" in r]
check('KZ: INFO log fires for serviceBookOnly inapplicable', len(kz_logs) == 1,
      f'found {len(kz_logs)} matching log records (expected exactly 1)')

# ---------------------------------------------------------------------------
# 12. INFO log fires exactly once per (filter, country) cell across 5 items.
# ---------------------------------------------------------------------------
print('\n--- 12. Push 5 RO items -> INFO log fires exactly once ---')
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
for i in range(5):
    expect_pass(p, item('ro', condition_raw='used', offer_id=1000 + i), spider,
                f'RO item #{i + 1}/5 -> kept')
ro_log_count = sum(
    1 for r in spider.logger.records
    if 'serviceBookOnly' in r and "'ro'" in r
)
check('5 RO items -> exactly one INFO log for (serviceBookOnly, ro)',
      ro_log_count == 1,
      f'log fired {ro_log_count} times (expected 1)')
check('_logged_inapplicable size == 1 after 5 RO items',
      len(HistoryFilterPipeline._logged_inapplicable) == 1,
      f'size={len(HistoryFilterPipeline._logged_inapplicable)}')

# ---------------------------------------------------------------------------
# 13. reset() clears _logged_inapplicable between simulated runs.
# ---------------------------------------------------------------------------
print('\n--- 13. reset() clears _logged_inapplicable between runs ---')
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(service_book_only=True)
# Populate the set with one cell
p.process_item(item('ro', offer_id=2000), spider)
before = len(HistoryFilterPipeline._logged_inapplicable)
check('Cell populated before reset()', before == 1, f'size before reset={before}')
HistoryFilterPipeline.reset()
after = len(HistoryFilterPipeline._logged_inapplicable)
check('reset() empties _logged_inapplicable', after == 0, f'size after reset={after}')
# Simulate a second run: log should fire again because state was cleared
spider2 = FakeSpider()
p2 = make_pipeline(service_book_only=True)
p2.process_item(item('ro', offer_id=2001), spider2)
post_reset_logs = [
    r for r in spider2.logger.records
    if 'serviceBookOnly' in r and "'ro'" in r
]
check('After reset(), INFO log fires again on next run',
      len(post_reset_logs) == 1,
      f'log records after reset={len(post_reset_logs)} (expected 1)')

# ---------------------------------------------------------------------------
# 14. All-three-filters-on, BG, conditionRaw='service-book' -> intersection trap
#     BG IS in _FIRST_OWNER_COUNTRIES; conditionRaw lacks 'first-owner' ->
#     firstOwnerOnly drops the item BEFORE serviceBookOnly even runs.
#     (Documented "intersection trap" expected behaviour, architecture R4.)
# ---------------------------------------------------------------------------
print('\n--- 14. ALL filters on, BG conditionRaw=service-book -> DROPPED by firstOwnerOnly (intersection trap) ---')
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(
    exclude_damaged=True,
    first_owner_only=True,
    service_book_only=True,
)
# Process order in pipeline:
#   excludeDamaged: BG is NOT in _DAMAGED_COUNTRIES -> _log_once(excludeDamaged, bg) + pass
#   firstOwnerOnly: BG IS in _FIRST_OWNER_COUNTRIES, conditionRaw='service-book' lacks
#                   'first-owner' -> raise DropItem
#   serviceBookOnly: never reached
expect_drop(p, item('bg', condition_raw='service-book', offer_id=14), spider,
            'BG with service-book but no first-owner -> DropItem by firstOwnerOnly (intersection trap)')

# ---------------------------------------------------------------------------
# 15. All-three-filters-on, BG, conditionRaw='service-book;first-owner' -> kept by all three filters
# ---------------------------------------------------------------------------
print("\n--- 15. ALL filters on, BG conditionRaw='service-book;first-owner' -> kept by all three filters ---")
HistoryFilterPipeline.reset()
spider = FakeSpider()
p = make_pipeline(
    exclude_damaged=True,
    first_owner_only=True,
    service_book_only=True,
)
# Process order:
#   excludeDamaged: BG not in _DAMAGED_COUNTRIES -> log + pass
#   firstOwnerOnly: BG in _FIRST_OWNER_COUNTRIES, parts contains 'first-owner' -> pass
#   serviceBookOnly: BG in _SERVICE_BOOK_COUNTRIES, parts contains 'service-book' -> pass
expect_pass(p, item('bg', condition_raw='service-book;first-owner', offer_id=15), spider,
            "BG with both slugs joined -> kept by all three filters")

# ---------------------------------------------------------------------------
# Results summary
# ---------------------------------------------------------------------------
print('\n' + '=' * 72)
total = len(results)
passed = sum(1 for s, *_ in results if s == PASS)
failed = total - passed
print(f'Results: {passed}/{total} passed, {failed} failed')
if failed:
    print('\nFailed tests:')
    for status, label, detail in results:
        if status == FAIL:
            print(f'  FAIL: {label} -- {detail}')
    print('\nqa51_servicebook_unit: FAIL')
    sys.exit(1)
else:
    print('qa51_servicebook_unit: PASS')
    sys.exit(0)
