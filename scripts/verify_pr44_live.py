"""Live post-deploy verification for PR #44 — MISSING items schema-validation fix.

Bug recap (issue #44):
  `compute_missing` builds partial item dicts from the compact KV snapshot.
  Those dicts are pushed directly via `dataset.push_data` in main.py, bypassing
  the Scrapy pipeline chain entirely. Pre-fix: None values in those dicts caused
  Apify's dataset schema validator to reject with HTTP 400, producing a silent
  FAILED run (or 0-item SUCCEEDED). Post-fix: `_drop_nones` is called on each
  missing_item before push, exactly mirroring DropNonesPipeline for in-pipeline items.

Three runs, brand-switch pattern (per CLAUDE.md live-verification guidance):

  Run A — Cold-start with brand Mini (niche, ~20-30 RO listings).
           Input: incrementalMode=true, emitMissing=true, fresh stateKey.
           Assert: SUCCEEDED, itemCount=0 (cold-start suppresses NEW).
           Snapshot is seeded with Mini offers.

  Run B — Switch to brand Smart (same stateKey, emitMissing=true).
           THE regression check: Mini offers are absent → compute_missing returns
           MISSING dicts → _drop_nones must strip Nones → push succeeds.
           Assert: SUCCEEDED, itemCount > 0.
           Without the fix this run would FAIL with schema-validation error.

  Run C — Switch back to brand Mini (same stateKey, emitMissing=true).
           Assert: SUCCEEDED, itemCount > 0, at least one REAPPEARED item,
           every REAPPEARED item has isRepost=true.

Each run polls up to 5 min for terminal status, then re-polls dataset itemCount
7 × 5s (per CLAUDE.md "eventually consistent" guidance).

Usage (after merge + Apify build completes):
  python scripts/verify_pr44_live.py

Exits 0 on full success; non-zero on any assertion failure.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

ACTOR_ID = "YEwcICSxWGYIr368r"
TOKEN_PATH = r"C:\Users\georg\.apify\auth.json"
BASE = f"https://api.apify.com/v2/acts/{ACTOR_ID}"


def _token() -> str:
    with open(TOKEN_PATH) as f:
        return json.load(f)["token"]


def _post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["data"]


def _get(url: str) -> dict:
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())["data"]


def wait_terminal(token: str, run_id: str, timeout_s: int = 300) -> dict:
    """Poll until run reaches a terminal status or timeout_s elapses."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(5)
        run = _get(f"https://api.apify.com/v2/actor-runs/{run_id}?token={token}")
        status = run["status"]
        if status in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
            return run
    raise TimeoutError(f"Run {run_id} did not reach terminal status within {timeout_s}s")


def poll_item_count(token: str, dataset_id: str, status: str) -> int:
    """Re-poll itemCount up to 7 × 5s while SUCCEEDED+0 (eventually consistent)."""
    item_count = 0
    for _ in range(7):
        ds = _get(f"https://api.apify.com/v2/datasets/{dataset_id}?token={token}")
        item_count = ds["itemCount"]
        if item_count > 0 or status != "SUCCEEDED":
            break
        time.sleep(5)
    return item_count


def fetch_all_items(token: str, dataset_id: str) -> list[dict]:
    url = (
        f"https://api.apify.com/v2/datasets/{dataset_id}/items"
        f"?token={token}&format=json"
    )
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def assert_or_die(cond: bool, msg: str) -> None:
    if cond:
        print(f"  PASS  {msg}")
    else:
        print(f"  FAIL  {msg}")
        sys.exit(1)


def run_actor(label: str, token: str, run_input: dict) -> tuple[dict, list[dict]]:
    """Start a run, wait for terminal, return (run_meta, items)."""
    print(f"\n=== {label} ===")
    started = _post(f"{BASE}/runs?token={token}", run_input)
    run_id = started["id"]
    print(f"  Run started: {run_id}")
    r = wait_terminal(token, run_id)
    status = r["status"]
    ds_id = r["defaultDatasetId"]
    status_msg = r.get("statusMessage", "")
    item_count = poll_item_count(token, ds_id, status)
    print(f"  status={status}  items={item_count}  msg={status_msg!r}")
    assert_or_die(status == "SUCCEEDED", f"{label}: run SUCCEEDED")
    items = fetch_all_items(token, ds_id) if item_count > 0 else []
    return r, items


def main() -> int:
    token = _token()
    ts = int(time.time())
    state_key = f"verify-pr44-{ts}"

    # Niche brands with small RO inventory — maxItems=200 ensures was_truncated=False
    # (MISSING emission is suppressed when spider truncates, by design)
    brand_a = "Mini"
    brand_b = "Smart"
    max_items = 200

    print(f"stateKey={state_key!r}  brand_a={brand_a!r}  brand_b={brand_b!r}")

    # ------------------------------------------------------------------
    # Run A — cold-start with brand_a
    # Expect: SUCCEEDED, 0 items (cold-start suppresses NEW)
    # ------------------------------------------------------------------
    _, items_a = run_actor(
        f"A) Cold-start {brand_a} (stateKey={state_key})",
        token,
        {
            "country": "ro",
            "brands": [brand_a],
            "maxItems": max_items,
            "incrementalMode": True,
            "stateKey": state_key,
            "emitMissing": True,
            "emitUnchanged": False,
        },
    )
    assert_or_die(len(items_a) == 0, f"A) cold-start emits 0 items (got {len(items_a)})")

    # ------------------------------------------------------------------
    # Run B — switch to brand_b (same stateKey, emitMissing=true)
    # THE regression check for issue #44:
    #   brand_a offers are absent → compute_missing returns MISSING dicts
    #   → _drop_nones must strip Nones before push → Apify accepts without HTTP 400.
    # Expect: SUCCEEDED, itemCount > 0 (MISSING items from brand_a are emitted)
    # ------------------------------------------------------------------
    _, items_b = run_actor(
        f"B) Switch to {brand_b} — MISSING check (stateKey={state_key})",
        token,
        {
            "country": "ro",
            "brands": [brand_b],
            "maxItems": max_items,
            "incrementalMode": True,
            "stateKey": state_key,
            "emitMissing": True,
            "emitUnchanged": False,
        },
    )
    assert_or_die(len(items_b) > 0, f"B) emits items (MISSING from {brand_a}) — got {len(items_b)}")

    by_type_b: dict[str, list[dict]] = {}
    for it in items_b:
        by_type_b.setdefault(it.get("changeType"), []).append(it)
    print(f"  B) breakdown: {[(k, len(v)) for k, v in by_type_b.items()]}")

    missing_b = by_type_b.get("MISSING", [])
    assert_or_die(len(missing_b) > 0, f"B) has MISSING items (brand_a={brand_a} absent) — got {len(missing_b)}")

    # Every MISSING item must have isRepost=false (not a reappearance)
    for it in missing_b:
        assert_or_die(
            it.get("isRepost") is False,
            f"B) MISSING item {it.get('offerId')}: isRepost=false (got {it.get('isRepost')!r})",
        )

    # Spot-check: no None values in any top-level field of emitted MISSING items
    # (this is the direct regression check for the #44 fix)
    for it in missing_b[:5]:  # check first 5 as representative sample
        none_keys = [k for k, v in it.items() if v is None]
        assert_or_die(
            len(none_keys) == 0,
            f"B) MISSING item {it.get('offerId')}: no None top-level values (found: {none_keys})",
        )

    # ------------------------------------------------------------------
    # Run C — switch back to brand_a (same stateKey, emitMissing=true)
    # Expect: SUCCEEDED, itemCount > 0, at least one REAPPEARED with isRepost=true
    # (Optional but validates round-trip correctness)
    # ------------------------------------------------------------------
    _, items_c = run_actor(
        f"C) Back to {brand_a} — REAPPEARED check (stateKey={state_key})",
        token,
        {
            "country": "ro",
            "brands": [brand_a],
            "maxItems": max_items,
            "incrementalMode": True,
            "stateKey": state_key,
            "emitMissing": True,
            "emitUnchanged": False,
        },
    )
    assert_or_die(len(items_c) > 0, f"C) emits items — got {len(items_c)}")

    by_type_c: dict[str, list[dict]] = {}
    for it in items_c:
        by_type_c.setdefault(it.get("changeType"), []).append(it)
    print(f"  C) breakdown: {[(k, len(v)) for k, v in by_type_c.items()]}")

    reappeared_c = by_type_c.get("REAPPEARED", [])
    assert_or_die(len(reappeared_c) > 0, f"C) at least one REAPPEARED item — got {len(reappeared_c)}")

    for it in reappeared_c:
        assert_or_die(
            it.get("isRepost") is True,
            f"C) REAPPEARED item {it.get('offerId')}: isRepost=true (got {it.get('isRepost')!r})",
        )
        print(
            f"    REAPPEARED offerId={it.get('offerId')} "
            f"make={it.get('make')} price={it.get('price')} isRepost={it.get('isRepost')}"
        )

    missing_c = by_type_c.get("MISSING", [])
    for it in missing_c:
        assert_or_die(
            it.get("isRepost") is False,
            f"C) MISSING item {it.get('offerId')}: isRepost=false (got {it.get('isRepost')!r})",
        )

    print("\n=== ALL CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
