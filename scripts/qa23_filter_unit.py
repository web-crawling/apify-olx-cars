"""Unit tests for HistoryFilterPipeline.process_item — Issue #23.

Tests every boundary case from the QA plan:
  - Both filters off → pass-through
  - excludeDamaged boundary cases (ro/bg supported/unsupported)
  - firstOwnerOnly boundary cases (kz/bg/ua/ro)
  - _log_once deduplication
  - reset() classmethod
"""

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

PASS = "PASS"
FAIL = "FAIL"
results = []


def check(label: str, ok: bool, detail: str = ""):
    status = PASS if ok else FAIL
    results.append((status, label, detail))
    mark = "  OK  " if ok else " FAIL "
    extra = f" — {detail}" if detail else ""
    print(f"[{mark}] {label}{extra}")


def make_pipeline(exclude_damaged: bool, first_owner_only: bool,
                  service_book_only: bool = False) -> HistoryFilterPipeline:
    """Build a pipeline instance mimicking open_spider behaviour.

    The ``service_book_only`` keyword defaults to False so existing call sites
    (which test only the first two filters) continue to work, while still
    initialising the third instance attribute that PR #51 added to the
    process_item short-circuit guard. Without setting this attribute,
    process_item raises AttributeError on the first ``or self._service_book_only``
    evaluation.
    """
    HistoryFilterPipeline.reset()
    pipeline = HistoryFilterPipeline()
    pipeline._exclude_damaged = exclude_damaged
    pipeline._first_owner_only = first_owner_only
    pipeline._service_book_only = service_book_only
    return pipeline


class FakeSpider:
    """Minimal spider stub for logging."""
    logger = logging.getLogger("fake_spider")


SPIDER = FakeSpider()


def item(country: str, condition: str = None, condition_raw=None, owners_count=None) -> dict:
    """Build a minimal item dict."""
    d = {"offerId": 999, "country": country}
    if condition is not None:
        d["condition"] = condition
    if condition_raw is not None:
        d["conditionRaw"] = condition_raw
    if owners_count is not None:
        d["ownersCount"] = owners_count
    return d


def expect_pass(pipeline, it, label):
    try:
        result = pipeline.process_item(it)
        check(label, result is not None, "item returned")
    except DropItem:
        check(label, False, "unexpected DropItem raised")


def expect_drop(pipeline, it, label):
    try:
        pipeline.process_item(it)
        check(label, False, "DropItem not raised — expected drop")
    except DropItem:
        check(label, True, "DropItem raised as expected")


# ---------------------------------------------------------------------------
# 1. Both filters off → pass-through unchanged
# ---------------------------------------------------------------------------
print("\n--- 1. Both filters off ---")
p = make_pipeline(False, False)
it = item("ro", condition="damaged")
result = p.process_item(it)
check("both-off: damaged ro item passes through", result is it)

# ---------------------------------------------------------------------------
# 2. excludeDamaged = True, country=ro, condition='damaged' → DropItem
# ---------------------------------------------------------------------------
print("\n--- 2. excludeDamaged=True, ro, damaged → drop ---")
p = make_pipeline(True, False)
expect_drop(p, item("ro", condition="damaged"), "ro damaged → DropItem")

# ---------------------------------------------------------------------------
# 3. excludeDamaged = True, country=ro, condition='used' → passes
# ---------------------------------------------------------------------------
print("\n--- 3. excludeDamaged=True, ro, used → pass ---")
p = make_pipeline(True, False)
expect_pass(p, item("ro", condition="used"), "ro used → pass")

# ---------------------------------------------------------------------------
# 4. excludeDamaged = True, country=bg (unsupported) → passes + INFO log once
# ---------------------------------------------------------------------------
print("\n--- 4. excludeDamaged=True, bg (unsupported) → pass + log ---")
HistoryFilterPipeline.reset()
p = make_pipeline(True, False)

# Capture log — _log_once now uses the module-level logger ('src.pipelines'),
# not spider.logger, so attach the handler to that logger.
log_records = []
class CapturingHandler(logging.Handler):
    def emit(self, record):
        log_records.append(record.getMessage())

handler = CapturingHandler()
pipelines_logger = logging.getLogger('src.pipelines')
pipelines_logger.addHandler(handler)
pipelines_logger.setLevel(logging.DEBUG)

expect_pass(p, item("bg", condition="used"), "bg used → pass (unsupported country)")
bg_logs = [r for r in log_records if "excludeDamaged" in r and "bg" in r]
check("bg: INFO log emitted once for excludeDamaged", len(bg_logs) >= 1,
      f"found {len(bg_logs)} matching log records")

# ---------------------------------------------------------------------------
# 5. excludeDamaged = True, country=bg, SECOND item → passes + NO duplicate log
# ---------------------------------------------------------------------------
print("\n--- 5. excludeDamaged=True, bg, second item → no duplicate log ---")
log_records.clear()
expect_pass(p, item("bg", condition="used"), "bg second item → pass")
bg_logs2 = [r for r in log_records if "excludeDamaged" in r and "bg" in r]
check("bg: no duplicate INFO log on second item", len(bg_logs2) == 0,
      f"found {len(bg_logs2)} log records (expected 0)")

pipelines_logger.removeHandler(handler)

# ---------------------------------------------------------------------------
# 6. firstOwnerOnly = True, country=kz, ownersCount=1 → passes
# ---------------------------------------------------------------------------
print("\n--- 6. firstOwnerOnly=True, kz, ownersCount=1 → pass ---")
p = make_pipeline(False, True)
expect_pass(p, item("kz", owners_count=1), "kz ownersCount=1 → pass")

# ---------------------------------------------------------------------------
# 7. firstOwnerOnly = True, country=kz, ownersCount=2 → DropItem
# ---------------------------------------------------------------------------
print("\n--- 7. firstOwnerOnly=True, kz, ownersCount=2 → drop ---")
p = make_pipeline(False, True)
expect_drop(p, item("kz", owners_count=2), "kz ownersCount=2 → DropItem")

# ---------------------------------------------------------------------------
# 8. firstOwnerOnly = True, country=kz, ownersCount missing/None
#    Architecture R2 applies to conditionRaw (BG/UA path).
#    For KZ, architecture pseudo-code: str(None) != '1' → DropItem.
#    Implementation: int(None or 0)==1 → False → DropItem.
#    QA brief asked to confirm; this tests what the code actually does.
# ---------------------------------------------------------------------------
print("\n--- 8. firstOwnerOnly=True, kz, ownersCount missing → DropItem (current impl) ---")
p = make_pipeline(False, True)
# Item without ownersCount key (mimics DropNonesPipeline having stripped it)
it_no_owners = {"offerId": 1, "country": "kz", "condition": "used"}
expect_drop(p, it_no_owners, "kz ownersCount absent → DropItem (R2 does NOT apply to KZ ownersCount path)")

# ---------------------------------------------------------------------------
# 9. firstOwnerOnly = True, country=bg, conditionRaw='first-owner' → passes
# ---------------------------------------------------------------------------
print("\n--- 9. firstOwnerOnly=True, bg, conditionRaw='first-owner' → pass ---")
p = make_pipeline(False, True)
expect_pass(p, item("bg", condition_raw="first-owner"), "bg conditionRaw='first-owner' → pass")

# ---------------------------------------------------------------------------
# 10. firstOwnerOnly = True, country=ua, conditionRaw ';'-joined with first-owner → passes
# ---------------------------------------------------------------------------
print("\n--- 10. firstOwnerOnly=True, ua, conditionRaw ';'-joined with first-owner → pass ---")
p = make_pipeline(False, True)
# UA multi-element arrays are ';'-joined by the spider before pipeline
expect_pass(p, item("ua", condition_raw="first-owner;after-an-accident"),
            "ua conditionRaw='first-owner;after-an-accident' → pass")

# ---------------------------------------------------------------------------
# 11. firstOwnerOnly = True, country=ua, conditionRaw='used' → DropItem
# ---------------------------------------------------------------------------
print("\n--- 11. firstOwnerOnly=True, ua, conditionRaw='used' → drop ---")
p = make_pipeline(False, True)
expect_drop(p, item("ua", condition_raw="used"),
            "ua conditionRaw='used' → DropItem")

# ---------------------------------------------------------------------------
# 12. firstOwnerOnly = True, country=ro (unsupported) → passes + INFO log once
# ---------------------------------------------------------------------------
print("\n--- 12. firstOwnerOnly=True, ro (unsupported) → pass + log ---")
HistoryFilterPipeline.reset()
p = make_pipeline(False, True)

# _log_once now uses the module-level logger; capture from 'src.pipelines'.
log_records_ro = []
class CapturingHandler2(logging.Handler):
    def emit(self, record):
        log_records_ro.append(record.getMessage())

handler2 = CapturingHandler2()
pipelines_logger2 = logging.getLogger('src.pipelines')
pipelines_logger2.addHandler(handler2)
pipelines_logger2.setLevel(logging.DEBUG)

it_ro = item("ro", condition="used")
try:
    result_ro = p.process_item(it_ro)
    check("ro (unsupported) → pass", result_ro is not None, "item returned")
except DropItem:
    check("ro (unsupported) → pass", False, "unexpected DropItem")
ro_logs = [r for r in log_records_ro if "firstOwnerOnly" in r and "ro" in r]
check("ro: INFO log for firstOwnerOnly inapplicable", len(ro_logs) >= 1,
      f"found {len(ro_logs)} log records")
pipelines_logger2.removeHandler(handler2)

# ---------------------------------------------------------------------------
# 13. R2: BG/UA missing conditionRaw → pass through (not drop)
# ---------------------------------------------------------------------------
print("\n--- 13. R2: BG conditionRaw=None → pass (missing = unknown) ---")
p = make_pipeline(False, True)
it_bg_no_raw = {"offerId": 2, "country": "bg"}  # no conditionRaw (stripped by DropNones)
expect_pass(p, it_bg_no_raw, "bg conditionRaw absent → pass through (R2 safety)")

print("\n--- 14. R2: UA conditionRaw=None → pass (missing = unknown) ---")
p = make_pipeline(False, True)
it_ua_no_raw = {"offerId": 3, "country": "ua"}
expect_pass(p, it_ua_no_raw, "ua conditionRaw absent → pass through (R2 safety)")

# ---------------------------------------------------------------------------
# 14. reset(): _logged_inapplicable is cleared
# ---------------------------------------------------------------------------
print("\n--- 15. reset() clears _logged_inapplicable ---")
# First, populate the set
p = make_pipeline(True, True)
p.process_item(item("bg", condition="used"))  # logs bg/excludeDamaged
before = len(HistoryFilterPipeline._logged_inapplicable)
HistoryFilterPipeline.reset()
after = len(HistoryFilterPipeline._logged_inapplicable)
check("reset() empties _logged_inapplicable",
      after == 0, f"before={before}, after={after}")

# ---------------------------------------------------------------------------
# 15. _logged_inapplicable is a class attribute (not instance)
# ---------------------------------------------------------------------------
print("\n--- 16. _logged_inapplicable is class attribute, shared across instances ---")
HistoryFilterPipeline.reset()
p1 = make_pipeline(True, False)
p2 = make_pipeline(True, False)
p1.process_item(item("bg", condition="used"))  # p1 logs bg
check("p1 log recorded in class attr", len(HistoryFilterPipeline._logged_inapplicable) > 0)
size_before = len(HistoryFilterPipeline._logged_inapplicable)
p2.process_item(item("bg", condition="used"))  # p2 should NOT add duplicate
check("p2 does not double-log same cell",
      len(HistoryFilterPipeline._logged_inapplicable) == size_before,
      f"set size unchanged at {size_before}")

# ---------------------------------------------------------------------------
# Results summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
total = len(results)
passed = sum(1 for s, *_ in results if s == PASS)
failed = total - passed
print(f"Results: {passed}/{total} passed, {failed} failed")
if failed:
    print("\nFailed tests:")
    for status, label, detail in results:
        if status == FAIL:
            print(f"  FAIL: {label} — {detail}")
    sys.exit(1)
else:
    print("ALL PASS")
    sys.exit(0)
