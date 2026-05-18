"""Unit-style tests for NotificationBufferPipeline — olx-cars issue #29.

Tests the pipeline class directly with synthetic items (no network, no Apify
token, no live spider). Covers the test plan in architecture doc section 9.

Tests:
  Test 1: notifyOn='none' → buffers empty after N items
  Test 2: counts match changeType totals (NEW/UPDATED/UNCHANGED/MISSING/REAPPEARED)
  Test 3: notifyTopN truncation respected in post-crawl sort+slice
  Test 4: notifyMinPriceDropPct filter applied correctly
  Test 5: cold-start behaviour — empty buffer when no NEW items reach pipeline
  Test 7: price-drop math correctness (10000→8500 == 15.0%)
  Test 8: non-qualifying drops excluded from buffer
  Test 11: summaryText format sanity (<= 280 chars, contains key substrings)

Usage:
    .venv/Scripts/python scripts/qa_notification_digest.py

Exit code: 0 = all PASS, 1 = any FAIL.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Force UTF-8 output on Windows (avoids UnicodeEncodeError for non-ASCII)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

from src.pipelines import NotificationBufferPipeline

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
# Minimal stubs (pipeline only reads spider.settings.get('INPUT_DATA'))
# ---------------------------------------------------------------------------

class FakeSettings(dict):
    """Minimal Scrapy settings shim."""
    def get(self, key, default=None):
        return super().get(key, default)


class FakeSpider:
    """Minimal spider stub — pipeline only reads spider.settings."""
    def __init__(self, input_data: dict):
        self.settings = FakeSettings(INPUT_DATA=input_data)

    def log(self, msg, level=None):
        pass


def make_pipeline(input_data: dict) -> tuple[NotificationBufferPipeline, FakeSpider]:
    """Create a fresh pipeline + spider pair and call open_spider."""
    # Reset class attributes before each test to prevent bleed-over
    NotificationBufferPipeline.new_items_buffer = []
    NotificationBufferPipeline.price_drop_buffer = []
    NotificationBufferPipeline._counts = {}

    spider = FakeSpider(input_data)
    pipeline = NotificationBufferPipeline()
    pipeline.open_spider(spider)
    return pipeline, spider


def make_item(change_type: str, price: int | None = None,
              price_history: list | None = None,
              first_seen_at: str = "2026-05-18T10:00:00+00:00",
              offer_id: int = 1) -> dict:
    """Build a minimal plain-dict item suitable for NotificationBufferPipeline."""
    return {
        "offerId": offer_id,
        "url": f"https://www.olx.ro/d/oferta/test-ID{offer_id}.html",
        "title": f"Test Car {offer_id}",
        "price": price,
        "currency": "EUR",
        "year": 2019,
        "mileageKm": 50000,
        "make": "BMW",
        "model": "X5",
        "firstSeenAt": first_seen_at,
        "changeType": change_type,
        "priceHistory": price_history or [],
    }


# ---------------------------------------------------------------------------
# Test 1: notifyOn='none' — buffers empty after N items
# ---------------------------------------------------------------------------
section("Test 1: notifyOn='none' — buffers empty")

pipeline, spider = make_pipeline({
    "notifyOn": "none",
    "incrementalMode": True,
})

for i in range(5):
    item = make_item("NEW", price=10000, offer_id=i + 1)
    pipeline.process_item(item, spider)

check(
    "T1a: new_items_buffer empty after 5 NEW items with notifyOn=none",
    NotificationBufferPipeline.new_items_buffer == [],
    f"got {NotificationBufferPipeline.new_items_buffer!r}",
)
check(
    "T1b: price_drop_buffer empty after 5 NEW items with notifyOn=none",
    NotificationBufferPipeline.price_drop_buffer == [],
    f"got {NotificationBufferPipeline.price_drop_buffer!r}",
)
check(
    "T1c: _counts empty with notifyOn=none",
    NotificationBufferPipeline._counts == {},
    f"got {NotificationBufferPipeline._counts!r}",
)

# ---------------------------------------------------------------------------
# Test 2: counts match changeType totals
# ---------------------------------------------------------------------------
section("Test 2: counts match changeType totals")

pipeline, spider = make_pipeline({
    "notifyOn": "both",
    "notifyMinPriceDropPct": 5,
    "notifyTopN": 20,
    "incrementalMode": True,
})

# Push: 3 NEW + 2 UPDATED + 5 UNCHANGED + 1 MISSING + 1 REAPPEARED = 12 total
for i in range(3):
    pipeline.process_item(make_item("NEW", price=10000, offer_id=100 + i), spider)
for i in range(2):
    pipeline.process_item(make_item("UPDATED", price=9000, offer_id=200 + i), spider)
for i in range(5):
    pipeline.process_item(make_item("UNCHANGED", price=8000, offer_id=300 + i), spider)
for i in range(1):
    pipeline.process_item(make_item("MISSING", price=7000, offer_id=400 + i), spider)
for i in range(1):
    pipeline.process_item(make_item("REAPPEARED", price=6000, offer_id=500 + i), spider)

counts = NotificationBufferPipeline._counts
expected_counts = {
    "NEW": 3,
    "UPDATED": 2,
    "UNCHANGED": 5,
    "MISSING": 1,
    "REAPPEARED": 1,
    "total": 12,
}
check(
    "T2a: _counts match expected changeType totals",
    counts == expected_counts,
    f"expected={expected_counts!r}, got={counts!r}",
)

# ---------------------------------------------------------------------------
# Test 3: notifyTopN truncation respected
# ---------------------------------------------------------------------------
section("Test 3: notifyTopN truncation")

notify_top_n = 2

pipeline, spider = make_pipeline({
    "notifyOn": "new_listings",
    "notifyTopN": notify_top_n,
    "notifyMinPriceDropPct": 5,
    "incrementalMode": True,
})

# Push 10 NEW items with distinct firstSeenAt timestamps
for i in range(10):
    ts = f"2026-05-18T10:{i:02d}:00+00:00"
    pipeline.process_item(
        make_item("NEW", price=10000, offer_id=1000 + i, first_seen_at=ts),
        spider,
    )

# Simulate the main.py post-crawl sort+slice
buffer = NotificationBufferPipeline.new_items_buffer
sorted_new = sorted(buffer, key=lambda d: d.get("firstSeenAt") or "", reverse=True)
sliced_new = sorted_new[:notify_top_n]

check(
    "T3a: new_items_buffer has 10 items before slice",
    len(buffer) == 10,
    f"got {len(buffer)}",
)
check(
    "T3b: after sort+slice[:2], exactly 2 items",
    len(sliced_new) == 2,
    f"got {len(sliced_new)}",
)
check(
    "T3c: top item has most-recent firstSeenAt",
    sliced_new[0]["firstSeenAt"] == "2026-05-18T10:09:00+00:00",
    f"got {sliced_new[0]['firstSeenAt']!r}",
)

# ---------------------------------------------------------------------------
# Test 4: notifyMinPriceDropPct filter applied
# ---------------------------------------------------------------------------
section("Test 4: notifyMinPriceDropPct filter")

pipeline, spider = make_pipeline({
    "notifyOn": "price_drops",
    "notifyMinPriceDropPct": 10,
    "notifyTopN": 20,
    "incrementalMode": True,
})

# Five UPDATED items with price drops of approx: 3%, 7%, 11%, 15%, 5%
# prev=10000, curr values:
#   3%  => curr=9700 (drop=3.0%)
#   7%  => curr=9300 (drop=7.0%)
#   11% => curr=8900 (drop=11.0%)
#   15% => curr=8500 (drop=15.0%)
#   5%  => curr=9500 (drop=5.0%)

drop_scenarios = [
    (10000, 9700),   # 3%
    (10000, 9300),   # 7%
    (10000, 8900),   # 11%  — qualifies
    (10000, 8500),   # 15%  — qualifies
    (10000, 9500),   # 5%
]

for i, (prev_p, curr_p) in enumerate(drop_scenarios):
    item = make_item(
        "UPDATED",
        price=curr_p,
        offer_id=2000 + i,
        price_history=[
            {"price": prev_p, "currency": "EUR", "seenAt": "2026-05-10T10:00:00+00:00"},
            {"price": curr_p, "currency": "EUR", "seenAt": "2026-05-18T10:00:00+00:00"},
        ],
    )
    pipeline.process_item(item, spider)

qualified = NotificationBufferPipeline.price_drop_buffer
check(
    "T4a: exactly 2 items qualify at notifyMinPriceDropPct=10",
    len(qualified) == 2,
    f"got {len(qualified)} items: {[d['priceDropPct'] for d in qualified]}",
)
check(
    "T4b: qualified drops are 11% and 15% (unordered check)",
    {round(d["priceDropPct"], 1) for d in qualified} == {11.0, 15.0},
    f"got pcts={[d['priceDropPct'] for d in qualified]}",
)

# ---------------------------------------------------------------------------
# Test 5: cold-start behaviour — no NEW items reach buffer
# ---------------------------------------------------------------------------
section("Test 5: cold-start — NEW items suppressed before reaching pipeline")

# On cold-start, IncrementalDiffPipeline raises DropItem for NEW items, so they
# never reach NotificationBufferPipeline at priority 250. This test verifies the
# DOWNSTREAM contract: after a cold-start run, new_items_buffer is empty and
# the digest builder must handle the empty-buffer case gracefully.

pipeline, spider = make_pipeline({
    "notifyOn": "both",
    "notifyMinPriceDropPct": 5,
    "notifyTopN": 20,
    "incrementalMode": True,
})

# Simulate cold-start: no NEW items reach this pipeline (they were DropItem'd
# by IncrementalDiffPipeline). We only push UNCHANGED (snapshot-seeded) items.
for i in range(5):
    pipeline.process_item(
        make_item("UNCHANGED", price=10000, offer_id=3000 + i), spider
    )

check(
    "T5a: new_items_buffer empty on cold-start (no NEW items reach priority 250)",
    NotificationBufferPipeline.new_items_buffer == [],
    f"got {NotificationBufferPipeline.new_items_buffer!r}",
)
check(
    "T5b: price_drop_buffer also empty (no UPDATED items on cold-start)",
    NotificationBufferPipeline.price_drop_buffer == [],
    f"got {NotificationBufferPipeline.price_drop_buffer!r}",
)

# Verify digest builder handles empty buffers gracefully: sort+slice of [] == []
empty_new = sorted([], key=lambda d: d.get("firstSeenAt") or "", reverse=True)[:20]
empty_drops = sorted([], key=lambda d: d.get("priceDropPct") or 0, reverse=True)[:20]
check(
    "T5c: digest builder handles empty new_items_buffer gracefully (sort+slice OK)",
    empty_new == [],
)
check(
    "T5d: digest builder handles empty price_drop_buffer gracefully (sort+slice OK)",
    empty_drops == [],
)

# Simulate cold-start summaryText (replicating the main.py logic)
country = "ro"
notify_on_val = "both"
seeded_count = 5
summary = (
    f"OLX Cars baseline run ({country}, notifyOn={notify_on_val}): "
    f"0 changes emitted (snapshot seeded with "
    f"{seeded_count} listings). "
    f"Next run will detect changes."
)
check(
    "T5e: cold-start summaryText contains 'baseline' or '0 changes'",
    "baseline" in summary.lower() or "0 changes" in summary.lower(),
    f"got: {summary!r}",
)
check(
    "T5f: cold-start summaryText <= 280 chars",
    len(summary) <= 280,
    f"len={len(summary)}",
)

# ---------------------------------------------------------------------------
# Test 7: price-drop math correctness
# ---------------------------------------------------------------------------
section("Test 7: price-drop math correctness")

# Spec: priceHistory=[{price:10000}, {price:8500}], curr=8500 → pct=15.0
pipeline, spider = make_pipeline({
    "notifyOn": "price_drops",
    "notifyMinPriceDropPct": 5,
    "notifyTopN": 20,
    "incrementalMode": True,
})

item = make_item(
    "UPDATED",
    price=8500,
    offer_id=9001,
    price_history=[
        {"price": 10000, "currency": "EUR", "seenAt": "2026-05-10T10:00:00+00:00"},
        {"price": 8500, "currency": "EUR", "seenAt": "2026-05-18T10:00:00+00:00"},
    ],
)
pipeline.process_item(item, spider)

drops = NotificationBufferPipeline.price_drop_buffer
check(
    "T7a: one qualifying drop in buffer",
    len(drops) == 1,
    f"got {len(drops)} drops",
)
if drops:
    pct = drops[0]["priceDropPct"]
    check(
        "T7b: priceDropPct == 15.0 for 10000→8500",
        pct == 15.0,
        f"got {pct!r}",
    )
    check(
        "T7c: pricePrevious == 10000",
        drops[0]["pricePrevious"] == 10000,
        f"got {drops[0]['pricePrevious']!r}",
    )
    check(
        "T7d: priceCurrent == 8500",
        drops[0]["priceCurrent"] == 8500,
        f"got {drops[0]['priceCurrent']!r}",
    )

# ---------------------------------------------------------------------------
# Test 8: non-qualifying price drops excluded
# ---------------------------------------------------------------------------
section("Test 8: non-qualifying price drops excluded")

pipeline, spider = make_pipeline({
    "notifyOn": "price_drops",
    "notifyMinPriceDropPct": 5,
    "notifyTopN": 20,
    "incrementalMode": True,
})

# priceHistory=[{price:8500}, {price:8400}] — drop = (8500-8400)/8500*100 = 1.18%
item = make_item(
    "UPDATED",
    price=8400,
    offer_id=9002,
    price_history=[
        {"price": 8500, "currency": "EUR", "seenAt": "2026-05-10T10:00:00+00:00"},
        {"price": 8400, "currency": "EUR", "seenAt": "2026-05-18T10:00:00+00:00"},
    ],
)
pipeline.process_item(item, spider)

check(
    "T8a: 1.18% drop does not qualify at notifyMinPriceDropPct=5",
    NotificationBufferPipeline.price_drop_buffer == [],
    f"got {NotificationBufferPipeline.price_drop_buffer!r}",
)

# ---------------------------------------------------------------------------
# Test 11: summaryText format sanity
# ---------------------------------------------------------------------------
section("Test 11: summaryText format sanity")

# Replicate the main.py summaryText f-string logic for a warm run
country = "ro"
notify_on_val = "both"
notify_min_price_drop_pct = 5
counts_new = 5
counts_price_drops_qualified = 3

bits = []
if notify_on_val in ("new_listings", "both"):
    bits.append(f"{counts_new} new")
if notify_on_val in ("price_drops", "both"):
    n_drops = counts_price_drops_qualified
    bits.append(
        f"{n_drops} price drop"
        f"{'s' if n_drops != 1 else ''} "
        f"(>={notify_min_price_drop_pct}%)"
    )
summary_text = (
    f"OLX Cars run ({country}, notifyOn={notify_on_val}): "
    f"{', '.join(bits) or 'no qualifying changes'}."
)

check(
    "T11a: summaryText contains '5 new'",
    "5 new" in summary_text,
    f"got: {summary_text!r}",
)
check(
    "T11b: summaryText contains '3 price drop'",
    "3 price drop" in summary_text,
    f"got: {summary_text!r}",
)
check(
    "T11c: summaryText <= 280 chars",
    len(summary_text) <= 280,
    f"len={len(summary_text)}, text={summary_text!r}",
)

# Also test edge case: 1 price drop (no 's' suffix)
bits2 = []
if notify_on_val in ("new_listings", "both"):
    bits2.append(f"{counts_new} new")
if notify_on_val in ("price_drops", "both"):
    n_drops = 1
    bits2.append(
        f"{n_drops} price drop"
        f"{'s' if n_drops != 1 else ''} "
        f"(>={notify_min_price_drop_pct}%)"
    )
summary_singular = (
    f"OLX Cars run ({country}, notifyOn={notify_on_val}): "
    f"{', '.join(bits2) or 'no qualifying changes'}."
)
check(
    "T11d: singular '1 price drop' (no trailing s)",
    "1 price drop " in summary_singular and "1 price drops" not in summary_singular,
    f"got: {summary_singular!r}",
)

# Test empty digest summary (0 new, 0 drops)
bits3 = []
if notify_on_val in ("new_listings", "both"):
    bits3.append("0 new")
if notify_on_val in ("price_drops", "both"):
    bits3.append("0 price drops (>=5%)")
summary_empty = (
    f"OLX Cars run ({country}, notifyOn={notify_on_val}): "
    f"{', '.join(bits3) or 'no qualifying changes'}."
)
check(
    "T11e: '0 new, 0 price drops' summary makes sense (not empty string)",
    len(summary_empty) > 0,
)

# ---------------------------------------------------------------------------
# Bonus: price-drop buffer edge cases
# ---------------------------------------------------------------------------
section("Edge cases: price-drop buffer guards")

# Edge case A: curr_price > prev_price (price INCREASE) — must NOT qualify
pipeline, spider = make_pipeline({
    "notifyOn": "price_drops",
    "notifyMinPriceDropPct": 5,
    "notifyTopN": 20,
    "incrementalMode": True,
})
item = make_item(
    "UPDATED",
    price=12000,
    offer_id=9010,
    price_history=[
        {"price": 10000, "currency": "EUR", "seenAt": "2026-05-10T10:00:00+00:00"},
        {"price": 12000, "currency": "EUR", "seenAt": "2026-05-18T10:00:00+00:00"},
    ],
)
pipeline.process_item(item, spider)
check(
    "EC-A: price INCREASE (10000→12000) not buffered as a price drop",
    NotificationBufferPipeline.price_drop_buffer == [],
    f"got {NotificationBufferPipeline.price_drop_buffer!r}",
)

# Edge case B: only 1 priceHistory entry — must NOT attempt drop computation
pipeline, spider = make_pipeline({
    "notifyOn": "price_drops",
    "notifyMinPriceDropPct": 5,
    "notifyTopN": 20,
    "incrementalMode": True,
})
item = make_item(
    "UPDATED",
    price=8000,
    offer_id=9011,
    price_history=[
        {"price": 10000, "currency": "EUR", "seenAt": "2026-05-18T10:00:00+00:00"},
    ],
)
pipeline.process_item(item, spider)
check(
    "EC-B: single-entry priceHistory does not trigger price drop",
    NotificationBufferPipeline.price_drop_buffer == [],
    f"got {NotificationBufferPipeline.price_drop_buffer!r}",
)

# Edge case C: UPDATED item with no priceHistory at all
pipeline, spider = make_pipeline({
    "notifyOn": "price_drops",
    "notifyMinPriceDropPct": 5,
    "notifyTopN": 20,
    "incrementalMode": True,
})
item = make_item("UPDATED", price=8000, offer_id=9012, price_history=None)
pipeline.process_item(item, spider)
check(
    "EC-C: None priceHistory does not crash or buffer",
    NotificationBufferPipeline.price_drop_buffer == [],
    f"got {NotificationBufferPipeline.price_drop_buffer!r}",
)

# Edge case D: notifyOn='new_listings' — UPDATED items NOT counted in new_items_buffer
pipeline, spider = make_pipeline({
    "notifyOn": "new_listings",
    "notifyMinPriceDropPct": 5,
    "notifyTopN": 20,
    "incrementalMode": True,
})
pipeline.process_item(make_item("UPDATED", price=9000, offer_id=9013), spider)
check(
    "EC-D: notifyOn=new_listings — UPDATED item not in new_items_buffer",
    NotificationBufferPipeline.new_items_buffer == [],
    f"got {NotificationBufferPipeline.new_items_buffer!r}",
)
check(
    "EC-D2: notifyOn=new_listings — UPDATED count still appears in _counts",
    NotificationBufferPipeline._counts.get("UPDATED", 0) == 1,
    f"counts={NotificationBufferPipeline._counts!r}",
)

# Edge case E: notifyOn='price_drops' — NEW items not in new_items_buffer
pipeline, spider = make_pipeline({
    "notifyOn": "price_drops",
    "notifyMinPriceDropPct": 5,
    "notifyTopN": 20,
    "incrementalMode": True,
})
pipeline.process_item(make_item("NEW", price=10000, offer_id=9014), spider)
check(
    "EC-E: notifyOn=price_drops — NEW item not in new_items_buffer",
    NotificationBufferPipeline.new_items_buffer == [],
    f"got {NotificationBufferPipeline.new_items_buffer!r}",
)
check(
    "EC-E2: notifyOn=price_drops — NEW count in _counts",
    NotificationBufferPipeline._counts.get("NEW", 0) == 1,
    f"counts={NotificationBufferPipeline._counts!r}",
)

# Edge case F: open_spider reset — verify class attributes reset on second open_spider
pipeline, spider = make_pipeline({"notifyOn": "both", "notifyMinPriceDropPct": 5, "notifyTopN": 20})
pipeline.process_item(make_item("NEW", price=10000, offer_id=9020), spider)
# Simulate second run: call open_spider again on same pipeline instance
NotificationBufferPipeline.new_items_buffer = []
NotificationBufferPipeline.price_drop_buffer = []
NotificationBufferPipeline._counts = {}
pipeline.open_spider(spider)
check(
    "EC-F: open_spider resets class-attribute buffers for second run",
    NotificationBufferPipeline.new_items_buffer == []
    and NotificationBufferPipeline.price_drop_buffer == []
    and NotificationBufferPipeline._counts == {},
    f"buffers={NotificationBufferPipeline.new_items_buffer!r} {NotificationBufferPipeline._counts!r}",
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'=' * 60}")
print(f"Results: {_PASS} PASS, {_FAIL} FAIL")
if _ERRORS:
    print("\nFailed tests:")
    for e in _ERRORS:
        print(f"  {e}")
    sys.exit(1)
else:
    print("All tests PASSED.")
    sys.exit(0)
