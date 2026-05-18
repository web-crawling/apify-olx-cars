"""End-to-end lifecycle harness for isRepost flag — olx-cars issue #21.

Drives IncrementalDiffPipeline + compute_missing through 9 consecutive mock
runs using an in-memory snapshot store (no Apify token, no live spider needed).

Lifecycle under test (single offerId across 9 runs):
  Run 1: cold start  → NEW suppressed; snapshot seeded
  Run 2: offer gone  → MISSING emitted, _missingCount=1, isRepost=False
  Run 3: still gone  → MISSING emitted, _missingCount=2, isRepost=False
  Run 4: offer back  → REAPPEARED emitted, isRepost=True, _missingCount reset
  Run 5: no change   → UNCHANGED emitted (emitUnchanged=True), isRepost=False
  Run 6: gone again  → MISSING emitted, _missingCount=1, isRepost=False
  Run 7: still gone  → MISSING emitted, _missingCount=2, isRepost=False
  Run 8: still gone  → MISSING emitted, _missingCount=3 == threshold → PURGED
  Run 9: same id back post-purge → changeType=NEW, isRepost=False (v1 limitation)

Additional sections:
  Edge case audit   — null-safe ==, main.py ordering, DropNones, cold-start, emitUnchanged/emitMissing
  ITEM_PIPELINES audit — same logic as qa_pr_price_history_e2e.py

Usage:
    .venv/Scripts/python scripts/qa_pr_is_repost_e2e.py

Exit code: 0 = all PASS, 1 = any FAIL.
"""

from __future__ import annotations

import copy
import io
import re as _re
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

from scrapy.exceptions import DropItem
from src.items import CarItem
from src.pipelines import IncrementalDiffPipeline, DropNonesPipeline
from src.state import compute_missing, MISSING_PURGE_THRESHOLD

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
# Minimal spider stub
# ---------------------------------------------------------------------------

class FakeSettings(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class FakeCrawler:
    """Minimal crawler stub for from_crawler."""
    def __init__(self, input_data: dict):
        self.settings = FakeSettings(INPUT_DATA=input_data)


class FakeSpider:
    def __init__(self, input_data: dict):
        self.settings = FakeSettings(INPUT_DATA=input_data)
        self.crawl_failed = False

    def log(self, msg, level=None):
        pass


# ---------------------------------------------------------------------------
# Pipeline runner helpers
# ---------------------------------------------------------------------------

def make_item(offer_id: int, price: int = 10000, currency: str = "EUR") -> CarItem:
    item = CarItem()
    item["offerId"] = offer_id
    item["url"] = f"https://www.olx.ro/d/oferta/test-car-ID{offer_id}.html"
    item["country"] = "ro"
    item["title"] = "Test Car"
    item["description"] = "Test description"
    item["price"] = price
    item["currency"] = currency
    item["condition"] = "used"
    item["mileageKm"] = 50000
    item["scrapedAt"] = "2026-05-16T08:00:00+00:00"
    item["features"] = []
    item["images"] = []
    item["paramsRaw"] = []
    item["seller"] = {"id": 1, "type": "private", "hasPhone": True, "hasChat": False}
    item["location"] = {"city": "Bucharest", "gpsObfuscated": False}
    return item


def run_pipeline(
    items: list[CarItem],
    snapshot: dict,
    run_ts: str,
    emit_unchanged: bool = False,
    emit_missing: bool = True,
) -> tuple[list[dict], list[dict], dict]:
    """
    Run IncrementalDiffPipeline on a list of items, then compute_missing.

    Returns:
        (emitted_live_items, emitted_missing_items, updated_snapshot)

    Each emitted item has DropNonesPipeline applied (mirrors production chain).
    """
    input_data = {
        "incrementalMode": True,
        "emitUnchanged": emit_unchanged,
        "emitMissing": emit_missing,
        "maxItems": 1000,
        "_snapshot": copy.deepcopy(snapshot),
        "_runTs": run_ts,
        "stateKey": "test-state",
    }
    spider = FakeSpider(input_data)

    diff_pipeline = IncrementalDiffPipeline.from_crawler(FakeCrawler(input_data))

    drop_pipeline = DropNonesPipeline()

    # Track seen IDs for compute_missing
    seen_ids: set[str] = set()
    emitted_live: list[dict] = []

    for item in items:
        try:
            result = diff_pipeline.process_item(item)
            result = drop_pipeline.process_item(result)
            if isinstance(result, dict):
                emitted_live.append(result)
            else:
                # CarItem or similar — convert via asdict-like access
                emitted_live.append(dict(result))
            offer_id_str = str(item["offerId"])
            seen_ids.add(offer_id_str)
        except DropItem:
            offer_id_str = str(item["offerId"])
            seen_ids.add(offer_id_str)

    # After pipeline, read the updated_snapshot class attribute
    updated_snap = copy.deepcopy(IncrementalDiffPipeline.updated_snapshot)

    # Compute MISSING items (mirrors main.py post-crawl logic)
    missing_items_raw = compute_missing(
        snapshot=updated_snap,
        seen_ids=seen_ids,
        emit_missing=emit_missing,
        run_ts=run_ts,
        was_truncated=False,
    )

    # Attach isRepost=False to MISSING items (mirrors main.py injection)
    emitted_missing: list[dict] = []
    for m in missing_items_raw:
        m["isRepost"] = False
        emitted_missing.append(m)

    # updated_snap was mutated in-place by compute_missing (purges + increments)
    final_snap = copy.deepcopy(updated_snap)

    return emitted_live, emitted_missing, final_snap


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OFFER_ID = 404010101
OFFER_KEY = str(OFFER_ID)

# ---------------------------------------------------------------------------
# Run 1: Cold start — empty snapshot
# ---------------------------------------------------------------------------
section("Run 1: Cold start (empty snapshot) — offer first seen")

RUN_TS_1 = "2026-05-01T08:00:00+00:00"
snapshot_run1 = {}

live1, missing1, snap1 = run_pipeline(
    [make_item(OFFER_ID)],
    snapshot=snapshot_run1,
    run_ts=RUN_TS_1,
    emit_unchanged=True,
    emit_missing=True,
)

check("Run 1: no live items emitted (cold-start suppression)", len(live1) == 0,
      f"got {len(live1)} live items: {live1!r}")
check("Run 1: no MISSING items (offer was present)", len(missing1) == 0,
      f"got {len(missing1)} missing items")
check("Run 1: snapshot seeded with offer entry", OFFER_KEY in snap1,
      f"snapshot keys: {list(snap1.keys())}")

if OFFER_KEY in snap1:
    check("Run 1: snapshot _missingCount absent (not missing)", snap1[OFFER_KEY].get("_missingCount") is None,
          f"got {snap1[OFFER_KEY].get('_missingCount')!r}")

# ---------------------------------------------------------------------------
# Run 2: Offer disappears — first absence, _missingCount=1
# ---------------------------------------------------------------------------
section("Run 2: Offer absent for first time — MISSING _missingCount=1")

RUN_TS_2 = "2026-05-02T08:00:00+00:00"

# No items in results this run (offer disappeared)
live2, missing2, snap2 = run_pipeline(
    [],
    snapshot=snap1,
    run_ts=RUN_TS_2,
    emit_missing=True,
)

check("Run 2: no live items", len(live2) == 0)
check("Run 2: one MISSING item emitted", len(missing2) == 1,
      f"got {len(missing2)} missing items: {missing2!r}")

if missing2:
    m2 = missing2[0]
    check("Run 2: MISSING changeType", m2.get("changeType") == "MISSING",
          f"got {m2.get('changeType')!r}")
    check("Run 2: MISSING isRepost=False", m2.get("isRepost") == False,
          f"got {m2.get('isRepost')!r}")
    check("Run 2: MISSING offerId matches", str(m2.get("offerId")) == OFFER_KEY,
          f"got {m2.get('offerId')!r}")

check("Run 2: snapshot still has offer (below purge threshold)",
      OFFER_KEY in snap2, f"keys: {list(snap2.keys())}")

if OFFER_KEY in snap2:
    check("Run 2: snapshot _missingCount=1",
          snap2[OFFER_KEY].get("_missingCount") == 1,
          f"got {snap2[OFFER_KEY].get('_missingCount')!r}")

# ---------------------------------------------------------------------------
# Run 3: Offer still missing — _missingCount=2
# ---------------------------------------------------------------------------
section("Run 3: Offer still absent — MISSING _missingCount=2")

RUN_TS_3 = "2026-05-03T08:00:00+00:00"

live3, missing3, snap3 = run_pipeline(
    [],
    snapshot=snap2,
    run_ts=RUN_TS_3,
    emit_missing=True,
)

check("Run 3: one MISSING item emitted", len(missing3) == 1,
      f"got {len(missing3)}")

if missing3:
    m3 = missing3[0]
    check("Run 3: changeType=MISSING", m3.get("changeType") == "MISSING")
    check("Run 3: isRepost=False", m3.get("isRepost") == False,
          f"got {m3.get('isRepost')!r}")

check("Run 3: offer still in snapshot (count 2 < threshold 3)",
      OFFER_KEY in snap3)

if OFFER_KEY in snap3:
    check("Run 3: snapshot _missingCount=2",
          snap3[OFFER_KEY].get("_missingCount") == 2,
          f"got {snap3[OFFER_KEY].get('_missingCount')!r}")

# ---------------------------------------------------------------------------
# Run 4: Offer REAPPEARS — isRepost=True
# ---------------------------------------------------------------------------
section("Run 4: Offer reappears after 2 misses — REAPPEARED, isRepost=True")

RUN_TS_4 = "2026-05-04T08:00:00+00:00"

live4, missing4, snap4 = run_pipeline(
    [make_item(OFFER_ID)],
    snapshot=snap3,
    run_ts=RUN_TS_4,
    emit_unchanged=True,
    emit_missing=True,
)

check("Run 4: one live item emitted", len(live4) == 1,
      f"got {len(live4)} live items")
check("Run 4: no MISSING items", len(missing4) == 0,
      f"got {len(missing4)}")

if live4:
    r4 = live4[0]
    check("Run 4: changeType=REAPPEARED",
          r4.get("changeType") == "REAPPEARED",
          f"got {r4.get('changeType')!r}")
    check("Run 4: isRepost=True",
          r4.get("isRepost") == True,
          f"got {r4.get('isRepost')!r}")

check("Run 4: snapshot _missingCount reset (entry present, no _missingCount key)",
      snap4.get(OFFER_KEY, {}).get("_missingCount") is None,
      f"got {snap4.get(OFFER_KEY, {}).get('_missingCount')!r}")

# ---------------------------------------------------------------------------
# Run 5: No change — UNCHANGED, isRepost=False
# ---------------------------------------------------------------------------
section("Run 5: No change — UNCHANGED, isRepost=False")

RUN_TS_5 = "2026-05-05T08:00:00+00:00"

live5, missing5, snap5 = run_pipeline(
    [make_item(OFFER_ID)],
    snapshot=snap4,
    run_ts=RUN_TS_5,
    emit_unchanged=True,
    emit_missing=True,
)

check("Run 5: one live item (emitUnchanged=True)", len(live5) == 1,
      f"got {len(live5)}")

if live5:
    r5 = live5[0]
    check("Run 5: changeType=UNCHANGED",
          r5.get("changeType") == "UNCHANGED",
          f"got {r5.get('changeType')!r}")
    check("Run 5: isRepost=False",
          r5.get("isRepost") == False,
          f"got {r5.get('isRepost')!r}")

# ---------------------------------------------------------------------------
# Run 6: Gone again — _missingCount=1
# ---------------------------------------------------------------------------
section("Run 6: Offer gone again — MISSING _missingCount=1")

RUN_TS_6 = "2026-05-06T08:00:00+00:00"

live6, missing6, snap6 = run_pipeline(
    [],
    snapshot=snap5,
    run_ts=RUN_TS_6,
    emit_missing=True,
)

check("Run 6: one MISSING item emitted", len(missing6) == 1,
      f"got {len(missing6)}")

if missing6:
    m6 = missing6[0]
    check("Run 6: changeType=MISSING", m6.get("changeType") == "MISSING")
    check("Run 6: isRepost=False", m6.get("isRepost") == False,
          f"got {m6.get('isRepost')!r}")

check("Run 6: offer still in snapshot (_missingCount=1)",
      snap6.get(OFFER_KEY, {}).get("_missingCount") == 1,
      f"got {snap6.get(OFFER_KEY, {}).get('_missingCount')!r}")

# ---------------------------------------------------------------------------
# Run 7: Still missing — _missingCount=2
# ---------------------------------------------------------------------------
section("Run 7: Offer still absent — MISSING _missingCount=2")

RUN_TS_7 = "2026-05-07T08:00:00+00:00"

live7, missing7, snap7 = run_pipeline(
    [],
    snapshot=snap6,
    run_ts=RUN_TS_7,
    emit_missing=True,
)

check("Run 7: one MISSING item emitted", len(missing7) == 1)
if missing7:
    check("Run 7: isRepost=False", missing7[0].get("isRepost") == False,
          f"got {missing7[0].get('isRepost')!r}")

check("Run 7: _missingCount=2",
      snap7.get(OFFER_KEY, {}).get("_missingCount") == 2,
      f"got {snap7.get(OFFER_KEY, {}).get('_missingCount')!r}")

# ---------------------------------------------------------------------------
# Run 8: Third consecutive miss — PURGE_THRESHOLD reached → entry purged
# ---------------------------------------------------------------------------
section(f"Run 8: Third miss — _missingCount reaches threshold={MISSING_PURGE_THRESHOLD}, entry PURGED")

RUN_TS_8 = "2026-05-08T08:00:00+00:00"

live8, missing8, snap8 = run_pipeline(
    [],
    snapshot=snap7,
    run_ts=RUN_TS_8,
    emit_missing=True,
)

# On the purge run, compute_missing emits one final MISSING item and then deletes the entry
check("Run 8: final MISSING item emitted before purge", len(missing8) == 1,
      f"got {len(missing8)}")
if missing8:
    check("Run 8: changeType=MISSING", missing8[0].get("changeType") == "MISSING")
    check("Run 8: isRepost=False on final MISSING", missing8[0].get("isRepost") == False,
          f"got {missing8[0].get('isRepost')!r}")

check("Run 8: offer entry PURGED from snapshot",
      OFFER_KEY not in snap8,
      f"snapshot still has key; entry: {snap8.get(OFFER_KEY)!r}")

# ---------------------------------------------------------------------------
# Run 9: Same offerId reappears post-purge → NEW, isRepost=False (v1 limitation)
# ---------------------------------------------------------------------------
section("Run 9: Same offerId returns after purge — NEW, isRepost=False (v1 known limitation)")

RUN_TS_9 = "2026-05-09T08:00:00+00:00"

# snap8 has no entry for OFFER_KEY — cold-start guard does NOT fire (snapshot is non-empty;
# other state could exist from previous runs if this were a realistic scenario).
# To test the post-purge NEW path cleanly: start with snap8 but add a dummy unrelated key
# so the snapshot is non-empty, preventing the cold-start baseline guard from triggering.
snap8_with_dummy = copy.deepcopy(snap8)
snap8_with_dummy["dummy_offer_99999"] = {
    "firstSeenAt": RUN_TS_1,
    "lastSeenAt": RUN_TS_5,
    "priceHistory": [],
}

live9, missing9, snap9 = run_pipeline(
    [make_item(OFFER_ID)],
    snapshot=snap8_with_dummy,
    run_ts=RUN_TS_9,
    emit_unchanged=True,
    emit_missing=True,
)

check("Run 9: one live item emitted (post-purge NEW)", len(live9) == 1,
      f"got {len(live9)}")

if live9:
    r9 = live9[0]
    check("Run 9: changeType=NEW (no snapshot record to detect repost)",
          r9.get("changeType") == "NEW",
          f"got {r9.get('changeType')!r}")
    check("Run 9: isRepost=False (v1 known limitation — no record)",
          r9.get("isRepost") == False,
          f"got {r9.get('isRepost')!r}")

# ---------------------------------------------------------------------------
# Edge case audit — Section C
# ---------------------------------------------------------------------------
section("Edge Case Audit")

# C1: None == 'REAPPEARED' is False (Python null-safe equality)
none_eq_result = (None == 'REAPPEARED')
check("C1: None == 'REAPPEARED' evaluates to False (null-safe ==)",
      none_eq_result == False,
      f"got {none_eq_result!r}")

# C2: main.py assigns isRepost BEFORE push_data — verify ordering in source text
main_py = (ACTOR_ROOT / "src" / "main.py").read_text(encoding="utf-8")
# Find the loop that attaches isRepost and calls push_data; verify isRepost= comes first
import re
# Look for the block that does missing_item['isRepost'] = False and push_data in order
isrepost_pos = main_py.find("missing_item['isRepost'] = False")
push_pos = main_py.find("await dataset.push_data(missing_item)")
check("C2: isRepost=False assigned BEFORE push_data in main.py",
      isrepost_pos != -1 and push_pos != -1 and isrepost_pos < push_pos,
      f"isRepost pos={isrepost_pos}, push_data pos={push_pos}")

# C3: DropNonesPipeline does not strip False (False is not None)
from src.pipelines import DropNonesPipeline as _DP, _drop_nones
result_c3 = _drop_nones({"isRepost": False, "price": None, "currency": "EUR"})
check("C3: DropNonesPipeline/_drop_nones keeps isRepost=False (False is not None)",
      result_c3.get("isRepost") == False and "price" not in result_c3,
      f"got {result_c3!r}")

# C4: Cold-start NEW items are suppressed before reaching output — isRepost doesn't matter
# (already asserted in Run 1, but re-assert the key invariant here)
check("C4: cold-start NEW item suppressed (live1 is empty, verified in Run 1)",
      len(live1) == 0,
      f"live1={live1!r}")

# C5: emitUnchanged=True — UNCHANGED items carry isRepost=False (verified in Run 5)
unchanged_isrepost_ok = len(live5) == 1 and live5[0].get("isRepost") == False
check("C5: emitUnchanged=True — UNCHANGED item carries isRepost=False",
      unchanged_isrepost_ok,
      f"live5={live5!r}")

# C6: emitMissing=True — MISSING items carry isRepost=False (verified in Runs 2/3/6/7/8)
missing_isrepost_ok = all(m.get("isRepost") == False for m in (missing2 + missing3 + missing6 + missing7 + missing8))
check("C6: emitMissing=True — all MISSING items carry isRepost=False",
      missing_isrepost_ok,
      f"MISSING items: {missing2 + missing3 + missing6 + missing7 + missing8!r}")

# C7: isRepost field absent entirely when incrementalMode=False
from src.pipelines import IncrementalDiffPipeline as _IDP, DropNonesPipeline as _DNP
_noinc_input = {
    "incrementalMode": False,
    "emitUnchanged": True,
    "emitMissing": True,
    "maxItems": 1000,
    "_snapshot": {},
    "_runTs": "2026-05-16T00:00:00+00:00",
}
_noinc_pipeline = _IDP.from_crawler(FakeCrawler(_noinc_input))
_noinc_item = {"offerId": 777, "price": 5000, "currency": "EUR"}
_noinc_result = _noinc_pipeline.process_item(_noinc_item)
check("C7: isRepost absent when incrementalMode=False",
      "isRepost" not in _noinc_result,
      f"got isRepost={_noinc_result.get('isRepost')!r}")

# ---------------------------------------------------------------------------
# ITEM_PIPELINES override audit (Section D)
# ---------------------------------------------------------------------------
section("ITEM_PIPELINES override audit")

scripts_dir = ACTOR_ROOT / "scripts"
settings_file = ACTOR_ROOT / "src" / "settings.py"

settings_text = settings_file.read_text(encoding="utf-8")
prod_pipelines: dict[str, int] = {}
for m in _re.finditer(r"""['\"](src\.pipelines\.\w+)['\"]:\s*(\d+)""", settings_text):
    prod_pipelines[m.group(1)] = int(m.group(2))

print(f"  Production pipelines (from src/settings.py): {prod_pipelines}")

THIS_SCRIPT = Path(__file__).name
override_issues: list[str] = []
for qa_script in sorted(scripts_dir.glob("qa_*.py")):
    if qa_script.name == THIS_SCRIPT:
        continue
    text = qa_script.read_text(encoding="utf-8", errors="replace")
    # Skip scripts that deliberately replace the entire pipeline chain with a test stub
    if "FailingPipeline" in text or "ITEM_PIPELINES" not in text:
        continue
    for pipe_name in prod_pipelines:
        if pipe_name not in text:
            override_issues.append(
                f"{qa_script.name}: ITEM_PIPELINES override missing {pipe_name!r}"
            )

if override_issues:
    for issue in override_issues:
        check(f"Pipeline audit: {issue}", False)
else:
    check(
        "All standard qa_* scripts with ITEM_PIPELINES override include all production pipelines",
        True,
    )

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*60}")
print(f"Results: {_PASS} PASS / {_FAIL} FAIL")

if _FAIL:
    print("\nFailed checks:")
    for e in _ERRORS:
        print(f"  {e}")
    print("\nOverall: FAIL")
    sys.exit(1)
else:
    print("\nOverall: ALL PASS")
    sys.exit(0)
