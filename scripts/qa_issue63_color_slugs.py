"""QA micro-test for issue #63 — verify the 4 new text-slug entries
in UA_COLOR_MAP and KZ_COLOR_MAP map to the correct canonical values,
and that pre-existing numeric-id entries are untouched.

Run with:
    .venv/Scripts/python scripts/qa_issue63_color_slugs.py

Exit codes:
    0 — all assertions passed
    1 — one or more assertions failed (AssertionError raised)
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.data.param_maps import UA_COLOR_MAP, KZ_COLOR_MAP  # noqa: E402


def _check(label: str, actual: object, expected: object) -> bool:
    ok = actual == expected
    status = "OK  " if ok else "FAIL"
    print(f"  [{status}] {label}: got {actual!r}, expected {expected!r}")
    return ok


def main() -> int:
    print("=" * 60)
    print("Issue #63 — color text-slug micro-test")
    print("=" * 60)

    failures: list[str] = []

    print("\nMap sizes:")
    print(f"  UA_COLOR_MAP size: {len(UA_COLOR_MAP)}")
    print(f"  KZ_COLOR_MAP size: {len(KZ_COLOR_MAP)}")

    # ---------------------------------------------------------------
    # New text-slug entries (issue #63) — UA
    # ---------------------------------------------------------------
    print("\nUA_COLOR_MAP — new text-slug entries:")
    cases_ua_new = [
        ("UA_COLOR_MAP['grey']",       UA_COLOR_MAP.get("grey"),       "gray"),
        ("UA_COLOR_MAP['light_blue']", UA_COLOR_MAP.get("light_blue"), "blue"),
        ("UA_COLOR_MAP['multicolor']", UA_COLOR_MAP.get("multicolor"), "other"),
        ("UA_COLOR_MAP['pixel']",      UA_COLOR_MAP.get("pixel"),      "other"),
    ]
    for label, actual, expected in cases_ua_new:
        if not _check(label, actual, expected):
            failures.append(label)

    # ---------------------------------------------------------------
    # New text-slug entries (issue #63) — KZ mirror
    # ---------------------------------------------------------------
    print("\nKZ_COLOR_MAP — new text-slug entries (mirror):")
    cases_kz_new = [
        ("KZ_COLOR_MAP['grey']",       KZ_COLOR_MAP.get("grey"),       "gray"),
        ("KZ_COLOR_MAP['light_blue']", KZ_COLOR_MAP.get("light_blue"), "blue"),
        ("KZ_COLOR_MAP['multicolor']", KZ_COLOR_MAP.get("multicolor"), "other"),
        ("KZ_COLOR_MAP['pixel']",      KZ_COLOR_MAP.get("pixel"),      "other"),
    ]
    for label, actual, expected in cases_kz_new:
        if not _check(label, actual, expected):
            failures.append(label)

    # ---------------------------------------------------------------
    # Pre-existing numeric-id entries — UA (sampled from param_maps.py
    # numeric block lines 395–416). Confirms data fix did not regress
    # any prior entry.
    # ---------------------------------------------------------------
    print("\nUA_COLOR_MAP — pre-existing numeric-id entries (regression):")
    cases_ua_pre = [
        ("UA_COLOR_MAP['1']",  UA_COLOR_MAP.get("1"),  "white"),
        ("UA_COLOR_MAP['2']",  UA_COLOR_MAP.get("2"),  "black"),
        ("UA_COLOR_MAP['4']",  UA_COLOR_MAP.get("4"),  "gray"),
        ("UA_COLOR_MAP['9']",  UA_COLOR_MAP.get("9"),  "gray"),
        ("UA_COLOR_MAP['14']", UA_COLOR_MAP.get("14"), "blue"),
        ("UA_COLOR_MAP['20']", UA_COLOR_MAP.get("20"), "other"),
        ("UA_COLOR_MAP['25']", UA_COLOR_MAP.get("25"), "other"),
    ]
    for label, actual, expected in cases_ua_pre:
        if not _check(label, actual, expected):
            failures.append(label)

    # ---------------------------------------------------------------
    # Pre-existing numeric-id entries — KZ
    # ---------------------------------------------------------------
    print("\nKZ_COLOR_MAP — pre-existing numeric-id entries (regression):")
    cases_kz_pre = [
        ("KZ_COLOR_MAP['1']",  KZ_COLOR_MAP.get("1"),  "white"),
        ("KZ_COLOR_MAP['2']",  KZ_COLOR_MAP.get("2"),  "black"),
        ("KZ_COLOR_MAP['4']",  KZ_COLOR_MAP.get("4"),  "gray"),
        ("KZ_COLOR_MAP['9']",  KZ_COLOR_MAP.get("9"),  "gray"),
        ("KZ_COLOR_MAP['14']", KZ_COLOR_MAP.get("14"), "blue"),
        ("KZ_COLOR_MAP['23']", KZ_COLOR_MAP.get("23"), "other"),
        ("KZ_COLOR_MAP['25']", KZ_COLOR_MAP.get("25"), "other"),
    ]
    for label, actual, expected in cases_kz_pre:
        if not _check(label, actual, expected):
            failures.append(label)

    # ---------------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    if failures:
        print(f"RESULT: FAILED — {len(failures)} assertion(s) failed:")
        for f in failures:
            print(f"  - {f}")
        print("=" * 60)
        return 1

    print("RESULT: PASSED — all 22 assertions passed.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
