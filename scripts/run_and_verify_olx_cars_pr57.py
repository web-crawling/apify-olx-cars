"""Live verification for olx-cars PR #57 (notifications, issue #29).

Runs four scenarios against the deployed actor on Apify:

  1. Schema-prefill smoke test (regression):
     submits the schema's prefill payload and asserts SUCCEEDED + itemCount > 0.
     Catches the silent-0-items failure mode unrelated to this PR.

  2. Cold-start notifications:
     fresh stateKey, incrementalMode=true, notifyOn=both, niche brand.
     Asserts SUCCEEDED + dataset 0 items (cold-start suppression) AND
     `olx-cars-notifications/digest-latest` KV record present with
     counts.new == 0 AND summaryText contains 'baseline'.

  3. Warm-run notifications:
     same stateKey as #2. Asserts SUCCEEDED + dataset items > 0 AND
     digest KV record updated (matching runId), counts.total > 0.

  4. Negative hard-fail:
     notifyOn='new_listings' + incrementalMode=false. Asserts FAILED status
     and statusMessage contains the clear error string.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ACTOR_ID = "YEwcICSxWGYIr368r"
ACTOR_SLUG = "extractify-labs/olx-cars"
AUTH_PATH = Path.home() / ".apify" / "auth.json"


def _load_token() -> str:
    return json.loads(AUTH_PATH.read_text())["token"]


def _post(url: str, body: dict, token: str) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{url}?token={token}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["data"]


def _get(url: str, token: str) -> dict:
    with urllib.request.urlopen(f"{url}?token={token}") as r:
        return json.loads(r.read())["data"]


def _get_raw(url: str, token: str) -> bytes | None:
    """Fetch raw bytes; return None on 404 (record absent)."""
    try:
        with urllib.request.urlopen(f"{url}?token={token}") as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _start_run(token: str, run_input: dict) -> str:
    run = _post(
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs",
        run_input,
        token,
    )
    return run["id"]


def _wait_terminal(token: str, run_id: str, timeout_s: int = 480) -> dict:
    """Poll until run reaches terminal state. Returns the final run object."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        run = _get(
            f"https://api.apify.com/v2/actor-runs/{run_id}",
            token,
        )
        if run["status"] in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
            return run
        time.sleep(5)
    raise TimeoutError(f"Run {run_id} did not reach terminal state within {timeout_s}s")


def _dataset_count_with_retry(token: str, dataset_id: str, status: str) -> int:
    """Apify itemCount is eventually consistent — re-poll for ~30s."""
    count = 0
    for _ in range(7):
        data = _get(
            f"https://api.apify.com/v2/datasets/{dataset_id}",
            token,
        )
        count = data["itemCount"]
        if count > 0 or status != "SUCCEEDED":
            return count
        time.sleep(5)
    return count


def _fetch_kv_record(token: str, store_name: str, key: str) -> dict | None:
    """Resolve a named KV store by name across the user's account, then
    fetch the record by key. Returns None if store or key not found."""
    # Apify named KV stores are listed under /v2/key-value-stores; we filter
    # by exact name. There is no direct GET-by-name; we must list and match.
    list_url = f"https://api.apify.com/v2/key-value-stores?limit=1000"
    with urllib.request.urlopen(f"{list_url}&token={token}") as r:
        stores = json.loads(r.read())["data"]["items"]
    match = next((s for s in stores if s.get("name") == store_name), None)
    if match is None:
        return None
    store_id = match["id"]
    record_url = f"https://api.apify.com/v2/key-value-stores/{store_id}/records/{key}"
    raw = _get_raw(record_url, token)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw.decode("utf-8", errors="replace")}


def test_1_schema_prefill_smoke(token: str) -> tuple[bool, str]:
    """Standard regression smoke test using the schema's prefill payload."""
    print("\n=== Test 1: schema-prefill smoke test (regression) ===")
    run_input = {
        "startUrls": [
            {"url": "https://www.olx.ro/auto-masini-moto-ambarcatiuni/autoturisme/"}
        ],
        "brands": ["BMW", "Volkswagen"],
        "maxItems": 50,
    }
    run_id = _start_run(token, run_input)
    print(f"  Run started: {run_id}")
    run = _wait_terminal(token, run_id)
    status = run["status"]
    item_count = _dataset_count_with_retry(token, run["defaultDatasetId"], status)
    print(f"  Run {run_id}: status={status}, items={item_count}")
    if status != "SUCCEEDED":
        return False, f"Status was {status}, statusMessage={run.get('statusMessage')}"
    if item_count <= 0:
        return False, "SUCCEEDED but produced 0 items — silent failure"
    return True, f"OK ({item_count} items)"


def test_2_cold_start_notifications(token: str, state_key: str) -> tuple[bool, str]:
    """Cold-start with notifyOn=both. Expect 0 dataset items + digest with
    counts.new=0 and 'baseline' summaryText."""
    print("\n=== Test 2: cold-start notifications ===")
    print(f"  stateKey={state_key}")
    run_input = {
        "country": "ro",
        "brands": ["Mini"],
        "maxItems": 100,
        "incrementalMode": True,
        "stateKey": state_key,
        "notifyOn": "both",
        "notifyTopN": 10,
        "notifyMinPriceDropPct": 5,
    }
    run_id = _start_run(token, run_input)
    print(f"  Run started: {run_id}")
    run = _wait_terminal(token, run_id)
    status = run["status"]
    item_count = _dataset_count_with_retry(token, run["defaultDatasetId"], status)
    print(f"  Run {run_id}: status={status}, items={item_count}")

    if status != "SUCCEEDED":
        return False, f"Cold-start run failed: status={status}, msg={run.get('statusMessage')}"
    # Cold-start MUST suppress all NEW items (incremental contract)
    if item_count != 0:
        return False, (
            f"Cold-start expected 0 dataset items (suppression), got {item_count}"
        )

    # Verify digest KV record
    digest = _fetch_kv_record(token, "olx-cars-notifications", "digest-latest")
    if digest is None:
        return False, "digest-latest KV record NOT found in olx-cars-notifications store"

    print(f"  digest-latest fetched: runId={digest.get('runId')!r} "
          f"counts={digest.get('counts')} summaryText={digest.get('summaryText')!r}")

    counts = digest.get("counts") or {}
    if counts.get("new") != 0:
        return False, f"Expected counts.new=0 on cold-start, got {counts.get('new')}"
    summary = digest.get("summaryText", "")
    if "baseline" not in summary.lower():
        return False, f"Expected 'baseline' in summaryText, got: {summary!r}"
    if digest.get("notifyOn") != "both":
        return False, f"Expected notifyOn=both echo, got {digest.get('notifyOn')!r}"
    if digest.get("runId") != run_id:
        return False, f"runId mismatch: digest={digest.get('runId')} run={run_id}"

    # Also verify the per-run archive key
    archive = _fetch_kv_record(token, "olx-cars-notifications", f"digest-{run_id}")
    if archive is None:
        return False, f"digest-{run_id} KV archive record NOT found"
    if archive.get("runId") != run_id:
        return False, "Archive record runId does not match"

    return True, f"OK (digest emitted, counts.new=0, baseline summaryText, both keys present)"


def test_3_warm_run_notifications(token: str, state_key: str) -> tuple[bool, str]:
    """Warm-run with a DIFFERENT brand than cold-start (brand-switch pattern).

    Cold-start (Test 2) seeded the snapshot with Mini listings. We now run
    with brand=Smart against the same stateKey. Smart listings are NEW
    (absent from prior snapshot), so they should pass through
    IncrementalDiffPipeline without DropItem and reach NotificationBuffer
    at priority 250 with changeType=NEW. The digest should show counts.new
    > 0 and a populated newItems array.

    Note: emitUnchanged defaults to false, so UNCHANGED items are
    DropItem'd by IncrementalDiff at 200 before reaching the notification
    pipeline at 250. counts.unchanged in the digest will therefore reflect
    EMITTED unchanged items, not the full universe. This is intentional but
    worth noting in the README's digest payload section.
    """
    print("\n=== Test 3: warm-run notifications (brand-switch pattern) ===")
    print(f"  stateKey={state_key} (snapshot has Mini from Test 2; switching to Smart)")
    run_input = {
        "country": "ro",
        "brands": ["Smart"],
        "maxItems": 100,
        "incrementalMode": True,
        "stateKey": state_key,
        "notifyOn": "both",
        "notifyTopN": 10,
        "notifyMinPriceDropPct": 5,
    }
    run_id = _start_run(token, run_input)
    print(f"  Run started: {run_id}")
    run = _wait_terminal(token, run_id)
    status = run["status"]
    item_count = _dataset_count_with_retry(token, run["defaultDatasetId"], status)
    print(f"  Run {run_id}: status={status}, items={item_count}")

    if status != "SUCCEEDED":
        return False, f"Warm run failed: status={status}, msg={run.get('statusMessage')}"
    if item_count == 0:
        return False, (
            "Warm run produced 0 dataset items — brand-switch should produce "
            "NEW Smart listings. Possible silent failure."
        )

    digest = _fetch_kv_record(token, "olx-cars-notifications", "digest-latest")
    if digest is None:
        return False, "digest-latest KV record NOT found after warm run"
    counts = digest.get("counts") or {}
    new_items_sample = digest.get("newItems", [])[:1]
    print(f"  digest-latest: runId={digest.get('runId')!r} "
          f"counts={counts} "
          f"newItems[0:1]={new_items_sample}")

    if digest.get("runId") != run_id:
        return False, (
            f"digest-latest not updated: digest.runId={digest.get('runId')} "
            f"expected {run_id}"
        )
    if counts.get("new", 0) <= 0:
        return False, (
            f"Expected counts.new > 0 after brand-switch (Mini→Smart), "
            f"got counts={counts}. Brand-switch should make Smart listings "
            f"new vs the Mini-only snapshot."
        )
    if not digest.get("newItems"):
        return False, "Expected non-empty newItems[] after brand-switch"

    # Spot-check the shape of the first newItems entry
    first = digest["newItems"][0]
    required_keys = {"offerId", "url", "title", "make", "firstSeenAt"}
    missing = required_keys - set(first.keys())
    if missing:
        return False, f"newItems[0] missing required keys: {missing}"

    return True, (
        f"OK (counts.new={counts.get('new')}, items={item_count}, "
        f"newItems[0]={first.get('make')!r} {first.get('title')!r:.60})"
    )


def test_4_negative_hard_fail(token: str) -> tuple[bool, str]:
    """notifyOn != 'none' without incrementalMode=true → Actor.fail()."""
    print("\n=== Test 4: negative hard-fail (notifyOn without incrementalMode) ===")
    run_input = {
        "country": "ro",
        "brands": ["BMW"],
        "maxItems": 10,
        # incrementalMode intentionally omitted (defaults to false)
        "notifyOn": "new_listings",
    }
    run_id = _start_run(token, run_input)
    print(f"  Run started: {run_id}")
    run = _wait_terminal(token, run_id, timeout_s=120)
    status = run["status"]
    msg = run.get("statusMessage", "") or ""
    print(f"  Run {run_id}: status={status}, statusMessage={msg!r}")

    if status != "FAILED":
        return False, f"Expected status=FAILED, got {status}"
    if "notifyOn requires incrementalMode" not in msg:
        return False, f"Expected guard message, got statusMessage={msg!r}"

    return True, f"OK (FAILED with clear guard message)"


def main() -> int:
    token = _load_token()
    # Unique stateKey for this verification round so we always start clean
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    state_key = f"qa-pr57-{ts}"

    results: list[tuple[str, bool, str]] = []

    for name, fn, args in [
        ("schema-prefill smoke", test_1_schema_prefill_smoke, (token,)),
        ("cold-start notifications", test_2_cold_start_notifications, (token, state_key)),
        ("warm-run notifications", test_3_warm_run_notifications, (token, state_key)),
        ("negative hard-fail", test_4_negative_hard_fail, (token,)),
    ]:
        try:
            ok, note = fn(*args)
        except Exception as exc:
            ok, note = False, f"EXCEPTION: {exc}"
        results.append((name, ok, note))
        marker = "PASS" if ok else "FAIL"
        print(f"  ==> {marker}: {note}")

    print("\n" + "=" * 70)
    print("Summary:")
    all_pass = True
    for name, ok, note in results:
        marker = "PASS" if ok else "FAIL"
        print(f"  [{marker}] {name}: {note}")
        if not ok:
            all_pass = False
    print("=" * 70)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
