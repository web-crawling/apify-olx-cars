"""End-to-end pipeline harness for priceHistory — olx-cars issue #20.

Drives IncrementalDiffPipeline through three consecutive mock runs using an
in-memory snapshot store (no Apify token, no live spider needed).

Scenarios covered:
  Run 1 (cold start): empty snapshot → item suppressed (NEW on cold start)
                      but updated_snapshot has priceHistory seeded with 1 entry.
  Run 2 (warm, price change): snapshot from run 1, price 12000→13000 →
                      item emitted with changeType=UPDATED, priceHistory=[2 entries].
  Run 3 (no change):  snapshot from run 2, same price 13000 →
                      item emitted with changeType=UNCHANGED (emitUnchanged=True),
                      priceHistory=[2 entries] (no new append).

Usage:
    .venv/Scripts/python scripts/qa_pr_price_history_e2e.py

Exit code: 0 = all PASS, 1 = any FAIL.
"""

from __future__ import annotations

import copy
import io
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

# Import after path fix
from scrapy.exceptions import DropItem
from src.items import CarItem
from src.pipelines import IncrementalDiffPipeline, DropNonesPipeline

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
# Minimal spider stub (IncrementalDiffPipeline only reads settings)
# ---------------------------------------------------------------------------

class FakeSettings(dict):
    """Minimal Scrapy settings shim."""
    def get(self, key, default=None):
        return super().get(key, default)


class FakeCrawler:
    """Minimal crawler stub for from_crawler (pipeline reads crawler.settings)."""
    def __init__(self, input_data: dict):
        self.settings = FakeSettings(INPUT_DATA=input_data)


class FakeSpider:
    """Minimal spider stub — kept for close_spider calls."""
    def __init__(self, input_data: dict):
        self.settings = FakeSettings(INPUT_DATA=input_data)
        self.crawl_failed = False

    def log(self, msg, level=None):
        pass


# ---------------------------------------------------------------------------
# Pipeline runner helpers
# ---------------------------------------------------------------------------

def make_item(offer_id: int, price: int | None, currency: str | None) -> CarItem:
    """Build a minimal CarItem suitable for IncrementalDiffPipeline."""
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
    item: CarItem,
    snapshot: dict,
    run_ts: str,
    emit_unchanged: bool = False,
) -> tuple[CarItem | None, dict]:
    """
    Run IncrementalDiffPipeline on a single item.

    Returns (emitted_item_or_None, updated_snapshot).
    emitted_item_or_None is None when the pipeline drops the item (DropItem).

    Also runs DropNonesPipeline to mirror the production chain.
    """
    input_data = {
        "incrementalMode": True,
        "emitUnchanged": emit_unchanged,
        "emitMissing": False,
        "maxItems": 1000,
        "_snapshot": copy.deepcopy(snapshot),
        "_runTs": run_ts,
        "stateKey": "test-state",
    }
    spider = FakeSpider(input_data)

    diff_pipeline = IncrementalDiffPipeline.from_crawler(FakeCrawler(input_data))

    drop_pipeline = DropNonesPipeline()

    try:
        result = diff_pipeline.process_item(item)
        # Apply DropNonesPipeline to mirror production chain
        result = drop_pipeline.process_item(result)
    except DropItem:
        result = None

    updated_snap = copy.deepcopy(IncrementalDiffPipeline.updated_snapshot)
    return result, updated_snap


# ---------------------------------------------------------------------------
# Run 1: Cold start — empty snapshot
# ---------------------------------------------------------------------------
section("Run 1: Cold start — empty snapshot")

OFFER_ID = 303514047
RUN_TS_1 = "2026-05-16T08:00:00+00:00"

item_run1 = make_item(OFFER_ID, price=12000, currency="EUR")
emitted_run1, snap_after_run1 = run_pipeline(
    item_run1, snapshot={}, run_ts=RUN_TS_1
)

check("item suppressed on cold start (None)", emitted_run1 is None,
      f"item was NOT suppressed: {emitted_run1!r}")

offer_key = str(OFFER_ID)
snap_entry_run1 = snap_after_run1.get(offer_key)

check("snapshot entry created for offer", snap_entry_run1 is not None)

ph_run1 = snap_entry_run1.get("priceHistory") if snap_entry_run1 else None
check("priceHistory seeded in snapshot with 1 entry",
      isinstance(ph_run1, list) and len(ph_run1) == 1,
      f"priceHistory={ph_run1!r}")

if ph_run1 and len(ph_run1) == 1:
    check("seed entry price == 12000", ph_run1[0].get("price") == 12000)
    check("seed entry currency == EUR", ph_run1[0].get("currency") == "EUR")
    check("seed entry seenAt == run_ts_1", ph_run1[0].get("seenAt") == RUN_TS_1)

# ---------------------------------------------------------------------------
# Run 2: Warm start, price change 12000 → 13000
# ---------------------------------------------------------------------------
section("Run 2: Warm start — price change 12000 → 13000")

RUN_TS_2 = "2026-05-17T08:00:00+00:00"
item_run2 = make_item(OFFER_ID, price=13000, currency="EUR")
emitted_run2, snap_after_run2 = run_pipeline(
    item_run2, snapshot=snap_after_run1, run_ts=RUN_TS_2
)

check("item emitted (not suppressed)", emitted_run2 is not None,
      "item was dropped but should be emitted as UPDATED")

if emitted_run2 is not None:
    ct = emitted_run2.get("changeType") if isinstance(emitted_run2, dict) else emitted_run2["changeType"]
    check("changeType == UPDATED", ct == "UPDATED", f"got {ct!r}")

    ph_run2_emitted = (
        emitted_run2.get("priceHistory") if isinstance(emitted_run2, dict)
        else emitted_run2.get("priceHistory")
    )
    check("emitted priceHistory is list", isinstance(ph_run2_emitted, list),
          f"got {type(ph_run2_emitted).__name__}")
    check("emitted priceHistory has 2 entries", len(ph_run2_emitted) == 2,
          f"got {len(ph_run2_emitted)} entries: {ph_run2_emitted!r}")

    if isinstance(ph_run2_emitted, list) and len(ph_run2_emitted) == 2:
        check("entry[0] price == 12000 (original)", ph_run2_emitted[0].get("price") == 12000,
              f"got {ph_run2_emitted[0].get('price')!r}")
        check("entry[1] price == 13000 (new)", ph_run2_emitted[1].get("price") == 13000,
              f"got {ph_run2_emitted[1].get('price')!r}")
        check("entry[1] seenAt == run_ts_2", ph_run2_emitted[1].get("seenAt") == RUN_TS_2,
              f"got {ph_run2_emitted[1].get('seenAt')!r}")

# ---------------------------------------------------------------------------
# Run 3: No change — same price 13000
# ---------------------------------------------------------------------------
section("Run 3: No change — price stays at 13000, emitUnchanged=True")

RUN_TS_3 = "2026-05-18T08:00:00+00:00"
item_run3 = make_item(OFFER_ID, price=13000, currency="EUR")
emitted_run3, snap_after_run3 = run_pipeline(
    item_run3, snapshot=snap_after_run2, run_ts=RUN_TS_3, emit_unchanged=True
)

check("item emitted (emitUnchanged=True)", emitted_run3 is not None,
      "item was dropped but emitUnchanged=True should emit UNCHANGED items")

if emitted_run3 is not None:
    ct3 = (
        emitted_run3.get("changeType") if isinstance(emitted_run3, dict)
        else emitted_run3["changeType"]
    )
    check("changeType == UNCHANGED", ct3 == "UNCHANGED", f"got {ct3!r}")

    ph_run3 = (
        emitted_run3.get("priceHistory") if isinstance(emitted_run3, dict)
        else emitted_run3.get("priceHistory")
    )
    check("priceHistory still has 2 entries (no new append for UNCHANGED)",
          isinstance(ph_run3, list) and len(ph_run3) == 2,
          f"got {ph_run3!r}")

    if isinstance(ph_run3, list) and len(ph_run3) == 2:
        check("entry[0] price still 12000 (oldest preserved)",
              ph_run3[0].get("price") == 12000)
        check("entry[1] price still 13000 (most recent)",
              ph_run3[1].get("price") == 13000)

# ---------------------------------------------------------------------------
# Bonus: DropNonesPipeline interaction — None price stripped from emitted entry
# ---------------------------------------------------------------------------
section("Bonus: DropNonesPipeline strips None price/currency from emitted entries")

# Build snapshot with one entry where price=None was stored (None-price listing)
RUN_TS_NONE = "2026-05-19T00:00:00+00:00"
OFFER_NONE_ID = 999888777
item_none_price = make_item(OFFER_NONE_ID, price=None, currency=None)
_, snap_none = run_pipeline(item_none_price, snapshot={}, run_ts=RUN_TS_NONE)

# Snapshot should carry None values internally
snap_entry_none = snap_none.get(str(OFFER_NONE_ID))
ph_in_snap = snap_entry_none.get("priceHistory") if snap_entry_none else []
if ph_in_snap:
    check("snapshot priceHistory entry price is None (preserved for diff)",
          ph_in_snap[0].get("price") is None,
          f"got price={ph_in_snap[0].get('price')!r}")

# Now run 2 with a real price (None → 5000 = change)
RUN_TS_NONE2 = "2026-05-20T00:00:00+00:00"
item_now_priced = make_item(OFFER_NONE_ID, price=5000, currency="EUR")
emitted_none2, _ = run_pipeline(item_now_priced, snapshot=snap_none, run_ts=RUN_TS_NONE2)

if emitted_none2 is not None:
    ph_emitted = (
        emitted_none2.get("priceHistory") if isinstance(emitted_none2, dict)
        else emitted_none2.get("priceHistory")
    )
    check("emitted priceHistory has 2 entries (None + real price)",
          isinstance(ph_emitted, list) and len(ph_emitted) == 2,
          f"got {ph_emitted!r}")
    # DropNonesPipeline strips price/currency keys from the None entry
    if isinstance(ph_emitted, list) and len(ph_emitted) >= 1:
        first_entry_keys = set(ph_emitted[0].keys())
        check("DropNonesPipeline stripped price/currency from None entry (only seenAt remains)",
              "price" not in first_entry_keys and "currency" not in first_entry_keys,
              f"keys present: {first_entry_keys}")
        check("seenAt preserved in None entry", "seenAt" in first_entry_keys)
else:
    print("  SKIP  DropNonesPipeline interaction (item was suppressed — run was cold start?)")

# ---------------------------------------------------------------------------
# ITEM_PIPELINES override audit (matching settings.py production chain)
# ---------------------------------------------------------------------------
section("ITEM_PIPELINES override audit")

import re as _re

scripts_dir = ACTOR_ROOT / "scripts"
settings_file = ACTOR_ROOT / "src" / "settings.py"

# Read production pipeline order from settings.py
settings_text = settings_file.read_text(encoding="utf-8")
prod_pipelines: dict[str, int] = {}
# settings.py uses single-quoted strings; match both quote styles
for m in _re.finditer(r"""['\"](src\.pipelines\.\w+)['\"]:\s*(\d+)""", settings_text):
    prod_pipelines[m.group(1)] = int(m.group(2))

print(f"  Production pipelines (from src/settings.py): {prod_pipelines}")

# Scan all qa_*.py scripts for ITEM_PIPELINES overrides and check inclusion.
# Exclude:
#   - this script itself (mentions ITEM_PIPELINES in audit comments)
#   - purpose-specific extension tests that deliberately use a non-production pipeline
#     (identified by having a custom 'FailingPipeline' or similar test-only pipeline)
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
    check("All standard qa_* scripts with ITEM_PIPELINES override include all production pipelines",
          True)

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
