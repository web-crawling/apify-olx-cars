"""QA micro-test for issue #65 — verify the bordeaux text-slug and numeric-id
fixes in UA_COLOR_MAP and KZ_COLOR_MAP.

Surfaced during PR #64 live verification: 5/500 UA items had non-canonical
color value "bordeaux". Root cause: (1) text-slug path — `UA_COLOR_MAP.get
("bordeaux", "bordeaux")` passed through unchanged; (2) latent numeric-id
path — both UA_COLOR_MAP["13"] and KZ_COLOR_MAP["13"] mapped to "bordeaux"
(Вишневий/Вишнёвый = cherry/burgundy → red family). This test asserts both
fix axes and confirms no remaining "bordeaux" in any map value.

Run with:
    .venv/Scripts/python scripts/qa_issue65_bordeaux.py

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
    print("Issue #65 — bordeaux fix micro-test")
    print("=" * 60)

    failures: list[str] = []

    print("\nMap sizes:")
    print(f"  UA_COLOR_MAP size: {len(UA_COLOR_MAP)}")
    print(f"  KZ_COLOR_MAP size: {len(KZ_COLOR_MAP)}")

    # ---------------------------------------------------------------
    # Text-slug fix (issue #65) — UA
    # ---------------------------------------------------------------
    print("\nUA_COLOR_MAP — bordeaux text-slug fix:")
    label = "UA_COLOR_MAP['bordeaux']"
    if not _check(label, UA_COLOR_MAP.get("bordeaux"), "red"):
        failures.append(label)

    # ---------------------------------------------------------------
    # Text-slug fix (issue #65) — KZ mirror
    # ---------------------------------------------------------------
    print("\nKZ_COLOR_MAP — bordeaux text-slug fix (mirror):")
    label = "KZ_COLOR_MAP['bordeaux']"
    if not _check(label, KZ_COLOR_MAP.get("bordeaux"), "red"):
        failures.append(label)

    # ---------------------------------------------------------------
    # Numeric-id fix (issue #65) — id 13 in both maps
    # ---------------------------------------------------------------
    print("\nUA_COLOR_MAP — id 13 numeric fix (cherry/burgundy -> red family):")
    label = "UA_COLOR_MAP['13']"
    if not _check(label, UA_COLOR_MAP.get("13"), "red"):
        failures.append(label)

    print("\nKZ_COLOR_MAP — id 13 numeric fix (cherry/burgundy -> red family):")
    label = "KZ_COLOR_MAP['13']"
    if not _check(label, KZ_COLOR_MAP.get("13"), "red"):
        failures.append(label)

    # ---------------------------------------------------------------
    # No remaining bordeaux output in either map
    # ---------------------------------------------------------------
    print("\nNo-bordeaux-in-values check:")
    ua_values = set(UA_COLOR_MAP.values())
    kz_values = set(KZ_COLOR_MAP.values())

    label = "'bordeaux' not in UA_COLOR_MAP values"
    ok = "bordeaux" not in ua_values
    status = "OK  " if ok else "FAIL"
    print(f"  [{status}] {label}")
    if not ok:
        failures.append(label)

    label = "'bordeaux' not in KZ_COLOR_MAP values"
    ok = "bordeaux" not in kz_values
    status = "OK  " if ok else "FAIL"
    print(f"  [{status}] {label}")
    if not ok:
        failures.append(label)

    # ---------------------------------------------------------------
    # Regression: pre-existing entries untouched
    # Sampled from numeric block lines ~395–454 in param_maps.py.
    # Includes the pre-#65 id=6 "red" mapping (confirms id 6 still
    # maps to red and id 13's change is isolated).
    # ---------------------------------------------------------------
    print("\nUA_COLOR_MAP — pre-existing entries (regression):")
    cases_ua_pre = [
        ("UA_COLOR_MAP['1']",    UA_COLOR_MAP.get("1"),    "white"),
        ("UA_COLOR_MAP['6']",    UA_COLOR_MAP.get("6"),    "red"),
        ("UA_COLOR_MAP['grey']", UA_COLOR_MAP.get("grey"), "gray"),
    ]
    for label, actual, expected in cases_ua_pre:
        if not _check(label, actual, expected):
            failures.append(label)

    print("\nKZ_COLOR_MAP — pre-existing entries (regression):")
    cases_kz_pre = [
        ("KZ_COLOR_MAP['1']",    KZ_COLOR_MAP.get("1"),    "white"),
        ("KZ_COLOR_MAP['6']",    KZ_COLOR_MAP.get("6"),    "red"),
        ("KZ_COLOR_MAP['grey']", KZ_COLOR_MAP.get("grey"), "gray"),
    ]
    for label, actual, expected in cases_kz_pre:
        if not _check(label, actual, expected):
            failures.append(label)

    # ---------------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    total_assertions = 4 + 2 + 6  # text+id fixes + no-bordeaux + regression
    if failures:
        print(f"RESULT: FAILED — {len(failures)} assertion(s) failed:")
        for f in failures:
            print(f"  - {f}")
        print("=" * 60)
        return 1

    print(f"RESULT: PASSED — all {total_assertions} assertions passed.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
