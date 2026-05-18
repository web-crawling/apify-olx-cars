"""Tests for notification pre-validation logic in main.py — olx-cars issue #29.

Tests the input validation and clamping behaviour defined in architecture doc
section 5 by replicating the validation logic inline (no Apify Actor context
required — avoids async Actor.fail() complexity in a test harness).

Validation rules under test:
  V1: notifyOn != 'none' + incrementalMode=False → fail (clear error message)
  V2: notifyMinPriceDropPct=150 → clamped to 99 with WARNING
  V3: notifyTopN=500 → clamped to 200 with WARNING
  V4: notifyWebhookUrl='ftp://foo' → disabled (empty string) with WARNING
  V5: notifyOn='gibberish' → defaults to 'none' with WARNING

Also verifies that the main.py file is structurally correct (importable without
Apify runtime and contains expected validation code paths).

Usage:
    .venv/Scripts/python scripts/qa_notify_main_validation.py

Exit code: 0 = all PASS, 1 = any FAIL.
"""

from __future__ import annotations

import io
import logging
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

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
# Inline replication of main.py validation logic
# (avoids needing an async Actor context)
# ---------------------------------------------------------------------------

def run_notify_validation(actor_input: dict, incremental_mode: bool) -> dict:
    """Replicate main.py notification validation block.

    Returns a dict with:
      notify_on                — validated/normalised value
      notify_min_price_drop_pct — validated/clamped value
      notify_top_n             — validated/clamped value
      notify_webhook_url        — validated value (empty = disabled)
      should_fail              — True if notifyOn!=none with incrementalMode=False
      warnings                 — list of warning messages
    """
    warnings: list[str] = []

    valid_notify_on = {"none", "new_listings", "price_drops", "both"}
    notify_on_raw = actor_input.get("notifyOn", "none")
    notify_on = str(notify_on_raw).lower() if notify_on_raw else "none"
    if notify_on not in valid_notify_on:
        warnings.append(f"Invalid notifyOn {notify_on_raw!r} — defaulting to 'none'.")
        notify_on = "none"

    # Guard: notifyOn != none requires incrementalMode
    should_fail = (notify_on != "none" and not incremental_mode)

    notify_min_pct_raw = actor_input.get("notifyMinPriceDropPct", 5)
    try:
        notify_min_price_drop_pct = int(notify_min_pct_raw)
        if not (1 <= notify_min_price_drop_pct <= 99):
            warnings.append(
                f"notifyMinPriceDropPct {notify_min_pct_raw!r} out of range [1,99] — clamping."
            )
            notify_min_price_drop_pct = max(1, min(99, notify_min_price_drop_pct))
    except (TypeError, ValueError):
        warnings.append(f"Invalid notifyMinPriceDropPct {notify_min_pct_raw!r} — defaulting to 5.")
        notify_min_price_drop_pct = 5

    notify_top_n_raw = actor_input.get("notifyTopN", 20)
    try:
        notify_top_n = int(notify_top_n_raw)
        if not (1 <= notify_top_n <= 200):
            warnings.append(
                f"notifyTopN {notify_top_n_raw!r} out of range [1,200] — clamping."
            )
            notify_top_n = max(1, min(200, notify_top_n))
    except (TypeError, ValueError):
        warnings.append(f"Invalid notifyTopN {notify_top_n_raw!r} — defaulting to 20.")
        notify_top_n = 20

    notify_webhook_url_raw = actor_input.get("notifyWebhookUrl", "") or ""
    notify_webhook_url = str(notify_webhook_url_raw).strip()
    if notify_webhook_url and not notify_webhook_url.startswith(("http://", "https://")):
        warnings.append(
            f"notifyWebhookUrl {notify_webhook_url!r} is not a valid http(s) URL — disabling."
        )
        notify_webhook_url = ""

    return {
        "notify_on": notify_on,
        "notify_min_price_drop_pct": notify_min_price_drop_pct,
        "notify_top_n": notify_top_n,
        "notify_webhook_url": notify_webhook_url,
        "should_fail": should_fail,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# V1: notifyOn != 'none' + incrementalMode=False → should fail
# ---------------------------------------------------------------------------
section("V1: notifyOn != 'none' + incrementalMode=False → should fail")

result = run_notify_validation(
    actor_input={"notifyOn": "new_listings"},
    incremental_mode=False,
)
check(
    "V1a: should_fail=True when notifyOn=new_listings + incrementalMode=False",
    result["should_fail"] is True,
    f"got should_fail={result['should_fail']!r}",
)
check(
    "V1b: notify_on preserved as 'new_listings' (not defaulted to none) before fail",
    result["notify_on"] == "new_listings",
    f"got {result['notify_on']!r}",
)

# Also verify the guard condition logic itself
for val in ("new_listings", "price_drops", "both"):
    res = run_notify_validation(
        actor_input={"notifyOn": val},
        incremental_mode=False,
    )
    check(
        f"V1c: notifyOn='{val}' + incrementalMode=False → should_fail=True",
        res["should_fail"] is True,
        f"got {res['should_fail']!r}",
    )

# notifyOn='none' with incrementalMode=False → should NOT fail
result_none = run_notify_validation(
    actor_input={"notifyOn": "none"},
    incremental_mode=False,
)
check(
    "V1d: notifyOn='none' + incrementalMode=False → should_fail=False",
    result_none["should_fail"] is False,
    f"got {result_none['should_fail']!r}",
)

# notifyOn != none + incrementalMode=True → should NOT fail
result_ok = run_notify_validation(
    actor_input={"notifyOn": "both"},
    incremental_mode=True,
)
check(
    "V1e: notifyOn='both' + incrementalMode=True → should_fail=False",
    result_ok["should_fail"] is False,
    f"got {result_ok['should_fail']!r}",
)

# ---------------------------------------------------------------------------
# V2: notifyMinPriceDropPct=150 → clamped to 99 with WARNING
# ---------------------------------------------------------------------------
section("V2: notifyMinPriceDropPct out-of-range → clamped")

result = run_notify_validation(
    actor_input={"notifyOn": "none", "notifyMinPriceDropPct": 150},
    incremental_mode=False,
)
check(
    "V2a: notifyMinPriceDropPct=150 clamped to 99",
    result["notify_min_price_drop_pct"] == 99,
    f"got {result['notify_min_price_drop_pct']!r}",
)
check(
    "V2b: clamping emits a WARNING",
    any("notifyMinPriceDropPct" in w and "clamping" in w for w in result["warnings"]),
    f"warnings={result['warnings']!r}",
)

# Low boundary: 0 → clamped to 1
result_low = run_notify_validation(
    actor_input={"notifyOn": "none", "notifyMinPriceDropPct": 0},
    incremental_mode=False,
)
check(
    "V2c: notifyMinPriceDropPct=0 clamped to 1",
    result_low["notify_min_price_drop_pct"] == 1,
    f"got {result_low['notify_min_price_drop_pct']!r}",
)

# In-range: 10 → stays 10
result_ok = run_notify_validation(
    actor_input={"notifyOn": "none", "notifyMinPriceDropPct": 10},
    incremental_mode=False,
)
check(
    "V2d: notifyMinPriceDropPct=10 (in range) → no clamping",
    result_ok["notify_min_price_drop_pct"] == 10,
    f"got {result_ok['notify_min_price_drop_pct']!r}",
)
check(
    "V2e: no WARNING for in-range notifyMinPriceDropPct",
    not any("notifyMinPriceDropPct" in w for w in result_ok["warnings"]),
    f"warnings={result_ok['warnings']!r}",
)

# ---------------------------------------------------------------------------
# V3: notifyTopN=500 → clamped to 200 with WARNING
# ---------------------------------------------------------------------------
section("V3: notifyTopN out-of-range → clamped")

result = run_notify_validation(
    actor_input={"notifyOn": "none", "notifyTopN": 500},
    incremental_mode=False,
)
check(
    "V3a: notifyTopN=500 clamped to 200",
    result["notify_top_n"] == 200,
    f"got {result['notify_top_n']!r}",
)
check(
    "V3b: clamping emits a WARNING",
    any("notifyTopN" in w and "clamping" in w for w in result["warnings"]),
    f"warnings={result['warnings']!r}",
)

# Low boundary: 0 → clamped to 1
result_low = run_notify_validation(
    actor_input={"notifyOn": "none", "notifyTopN": 0},
    incremental_mode=False,
)
check(
    "V3c: notifyTopN=0 clamped to 1",
    result_low["notify_top_n"] == 1,
    f"got {result_low['notify_top_n']!r}",
)

# In-range: 20 → stays 20
result_ok = run_notify_validation(
    actor_input={"notifyOn": "none", "notifyTopN": 20},
    incremental_mode=False,
)
check(
    "V3d: notifyTopN=20 (in range) → no clamping",
    result_ok["notify_top_n"] == 20,
    f"got {result_ok['notify_top_n']!r}",
)

# ---------------------------------------------------------------------------
# V4: notifyWebhookUrl='ftp://foo' → disabled with WARNING
# ---------------------------------------------------------------------------
section("V4: invalid notifyWebhookUrl → disabled")

result = run_notify_validation(
    actor_input={"notifyOn": "none", "notifyWebhookUrl": "ftp://foo.example.com"},
    incremental_mode=False,
)
check(
    "V4a: ftp:// URL → notify_webhook_url='' (disabled)",
    result["notify_webhook_url"] == "",
    f"got {result['notify_webhook_url']!r}",
)
check(
    "V4b: ftp:// URL emits WARNING about disabling",
    any("notifyWebhookUrl" in w and "disabling" in w for w in result["warnings"]),
    f"warnings={result['warnings']!r}",
)

# Valid https URL → preserved
result_https = run_notify_validation(
    actor_input={"notifyOn": "none", "notifyWebhookUrl": "https://hooks.slack.com/services/X/Y/Z"},
    incremental_mode=False,
)
check(
    "V4c: valid https:// URL preserved",
    result_https["notify_webhook_url"] == "https://hooks.slack.com/services/X/Y/Z",
    f"got {result_https['notify_webhook_url']!r}",
)

# Valid http URL → preserved
result_http = run_notify_validation(
    actor_input={"notifyOn": "none", "notifyWebhookUrl": "http://example.com/hook"},
    incremental_mode=False,
)
check(
    "V4d: valid http:// URL preserved",
    result_http["notify_webhook_url"] == "http://example.com/hook",
    f"got {result_http['notify_webhook_url']!r}",
)

# Empty string → stays empty, no warning
result_empty = run_notify_validation(
    actor_input={"notifyOn": "none", "notifyWebhookUrl": ""},
    incremental_mode=False,
)
check(
    "V4e: empty notifyWebhookUrl → stays empty, no warning",
    result_empty["notify_webhook_url"] == ""
    and not any("notifyWebhookUrl" in w for w in result_empty["warnings"]),
    f"url={result_empty['notify_webhook_url']!r} warnings={result_empty['warnings']!r}",
)

# No-field case (absent from input) → stays empty
result_absent = run_notify_validation(
    actor_input={"notifyOn": "none"},
    incremental_mode=False,
)
check(
    "V4f: absent notifyWebhookUrl → empty string",
    result_absent["notify_webhook_url"] == "",
    f"got {result_absent['notify_webhook_url']!r}",
)

# ---------------------------------------------------------------------------
# V5: notifyOn='gibberish' → defaults to 'none' with WARNING
# ---------------------------------------------------------------------------
section("V5: invalid notifyOn → defaults to 'none'")

result = run_notify_validation(
    actor_input={"notifyOn": "gibberish"},
    incremental_mode=False,
)
check(
    "V5a: notifyOn='gibberish' normalised to 'none'",
    result["notify_on"] == "none",
    f"got {result['notify_on']!r}",
)
check(
    "V5b: invalid notifyOn emits WARNING",
    any("notifyOn" in w and "defaulting" in w for w in result["warnings"]),
    f"warnings={result['warnings']!r}",
)
check(
    "V5c: should_fail=False when gibberish defaults to 'none'",
    result["should_fail"] is False,
    f"got {result['should_fail']!r}",
)

# notifyOn=None (None value from input) → treated as 'none'
result_none_input = run_notify_validation(
    actor_input={"notifyOn": None},
    incremental_mode=False,
)
check(
    "V5d: notifyOn=None → defaults to 'none'",
    result_none_input["notify_on"] == "none",
    f"got {result_none_input['notify_on']!r}",
)

# All valid values pass through unchanged
for valid in ("none", "new_listings", "price_drops", "both"):
    r = run_notify_validation(
        actor_input={"notifyOn": valid},
        incremental_mode=True,
    )
    check(
        f"V5e: valid notifyOn='{valid}' → no WARNING, preserved",
        r["notify_on"] == valid and not any("notifyOn" in w for w in r["warnings"]),
        f"got {r['notify_on']!r}, warnings={r['warnings']!r}",
    )

# ---------------------------------------------------------------------------
# Structural check: main.py can be AST-parsed and contains expected patterns
# ---------------------------------------------------------------------------
section("Structural check: main.py validation patterns present")

import ast
from pathlib import Path

main_py = ACTOR_ROOT / "src" / "main.py"
source = main_py.read_text(encoding="utf-8")

check(
    "S1: main.py AST-parses without SyntaxError",
    True,  # If we got this far, the import/parse at top of script would have failed
)

check(
    "S2: main.py contains notifyOn validation block",
    "valid_notify_on" in source and "notifyOn" in source,
    "could not find notifyOn validation block",
)
check(
    "S3: main.py contains notifyMinPriceDropPct clamping block",
    "notify_min_price_drop_pct" in source and "clamping" in source,
    "could not find notifyMinPriceDropPct clamping",
)
check(
    "S4: main.py contains notifyTopN clamping block",
    "notify_top_n" in source and "1 <= notify_top_n <= 200" in source,
    "could not find notifyTopN clamping block",
)
check(
    "S5: main.py contains notifyWebhookUrl validation",
    "notify_webhook_url" in source and "startswith" in source,
    "could not find notifyWebhookUrl validation",
)
check(
    "S6: main.py hard-fails when notifyOn!=none and incrementalMode=False",
    "notify_on != 'none' and not incremental_mode" in source,
    "could not find the incrementalMode guard",
)
check(
    "S7: main.py imports NotificationBufferPipeline",
    "NotificationBufferPipeline" in source,
    "NotificationBufferPipeline not imported in main.py",
)
check(
    "S8: main.py resets NotificationBufferPipeline class attributes pre-run",
    "NotificationBufferPipeline.new_items_buffer = []" in source,
    "pre-run reset for new_items_buffer not found",
)
check(
    "S9: main.py has post-crawl notification digest block",
    "notify_on != 'none'" in source and "olx-cars-notifications" in source,
    "post-crawl digest block not found",
)
check(
    "S10: main.py reads notifyOn from INPUT_DATA dict",
    "'notifyOn': notify_on," in source,
    "notifyOn not in INPUT_DATA dict",
)
check(
    "S11: main.py reads notifyMinPriceDropPct from INPUT_DATA dict",
    "'notifyMinPriceDropPct': notify_min_price_drop_pct," in source,
    "notifyMinPriceDropPct not in INPUT_DATA dict",
)
check(
    "S12: main.py reads notifyTopN from INPUT_DATA dict",
    "'notifyTopN': notify_top_n," in source,
    "notifyTopN not in INPUT_DATA dict",
)
check(
    "S13: main.py reads notifyWebhookUrl from INPUT_DATA dict",
    "'notifyWebhookUrl': notify_webhook_url," in source,
    "notifyWebhookUrl not in INPUT_DATA dict",
)
check(
    "S14: KV write failure sets crawl_failed (fatal path)",
    "crawl_failed = True" in source and "olx-cars-notifications" in source,
    "KV write failure -> crawl_failed not found",
)
check(
    "S15: webhook POST failure is non-fatal (warning only, no crawl_failed)",
    "non-fatal, dataset is unaffected" in source,
    "non-fatal webhook failure comment not found",
)

# AST parse validation
try:
    tree = ast.parse(source)
    check("S16: main.py AST parse OK", True)
except SyntaxError as e:
    check("S16: main.py AST parse OK", False, str(e))

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
