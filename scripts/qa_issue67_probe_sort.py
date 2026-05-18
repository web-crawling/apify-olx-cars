"""QA micro-test for issue #67 — verify check_slug_vocabulary handles
text-slug keys cleanly when they appear in the non-canonical violation set.

Pre-PR #67, the sort key inside check_slug_vocabulary was `int(x[0])`, which
crashes with ValueError on any text-slug key. Today the path is unreachable
in production data (all text-slug entries are canonical post-PR #66), so
this test exercises it synthetically: it mutates COPIES of UA_COLOR_MAP and
KZ_COLOR_MAP with a deliberately non-canonical text-slug value and asserts
that check_slug_vocabulary handles them without raising.

Run with:
    apify-olx-cars/.venv/Scripts/python.exe scripts/qa_issue67_probe_sort.py

Exit codes:
    0 — sort key handles both numeric and text-slug violations cleanly
    1 — sort key crashes OR fails to report the violation
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.qa_color_map_coverage import check_slug_vocabulary  # noqa: E402
from src.data.param_maps import UA_COLOR_MAP, KZ_COLOR_MAP  # noqa: E402


def _check(label: str, ok: bool) -> bool:
    status = "OK  " if ok else "FAIL"
    print(f"  [{status}] {label}")
    return ok


def main() -> int:
    print("=" * 60)
    print("Issue #67 — probe sort-key text-slug crash test")
    print("=" * 60)

    failures: list[str] = []

    # ----------------------------------------------------------
    # 1. Baseline: real maps pass (no violations, no crash).
    # ----------------------------------------------------------
    print("\nBaseline — real maps (no violations expected):")
    try:
        ok = check_slug_vocabulary(UA_COLOR_MAP, KZ_COLOR_MAP)
        if not _check("real maps pass cleanly", ok is True):
            failures.append("baseline")
    except Exception as exc:
        _check(f"real maps raised {type(exc).__name__}: {exc}", False)
        failures.append("baseline-crash")

    # ----------------------------------------------------------
    # 2. Inject a non-canonical TEXT-slug entry into a copy.
    #    Pre-fix this used to crash with ValueError because the
    #    sort key was `int(x[0])`. After the fix it must:
    #      - NOT raise
    #      - Return False (violations detected)
    # ----------------------------------------------------------
    print("\nInjection — non-canonical text-slug entry in UA copy:")
    mutated_ua = dict(UA_COLOR_MAP)
    mutated_ua["fakeslug"] = "magenta"  # magenta is NOT canonical
    try:
        ok = check_slug_vocabulary(mutated_ua, KZ_COLOR_MAP)
        if not _check("text-slug violation does not raise", True):
            failures.append("text-slug-raise")
        if not _check("text-slug violation returns False", ok is False):
            failures.append("text-slug-return")
    except Exception as exc:
        _check(f"text-slug violation raised {type(exc).__name__}: {exc}", False)
        failures.append("text-slug-crash")

    # ----------------------------------------------------------
    # 3. Mixed violations — numeric id AND text-slug both bad.
    #    Confirms sort key handles both branches in one call.
    # ----------------------------------------------------------
    print("\nInjection — mixed numeric + text-slug violations in KZ copy:")
    mutated_kz = dict(KZ_COLOR_MAP)
    mutated_kz["99"] = "magenta"          # numeric id, non-canonical value
    mutated_kz["another_slug"] = "neon"   # text-slug, non-canonical value
    try:
        ok = check_slug_vocabulary(UA_COLOR_MAP, mutated_kz)
        if not _check("mixed violations do not raise", True):
            failures.append("mixed-raise")
        if not _check("mixed violations return False", ok is False):
            failures.append("mixed-return")
    except Exception as exc:
        _check(f"mixed violations raised {type(exc).__name__}: {exc}", False)
        failures.append("mixed-crash")

    # ----------------------------------------------------------
    # 4. Regression — pre-existing numeric-only violation
    #    (id="99", canonical key shape) still sorts cleanly.
    # ----------------------------------------------------------
    print("\nInjection — numeric-only violation in UA copy (regression):")
    mutated_ua_num = dict(UA_COLOR_MAP)
    mutated_ua_num["99"] = "magenta"
    try:
        ok = check_slug_vocabulary(mutated_ua_num, KZ_COLOR_MAP)
        if not _check("numeric-only violation does not raise", True):
            failures.append("numeric-raise")
        if not _check("numeric-only violation returns False", ok is False):
            failures.append("numeric-return")
    except Exception as exc:
        _check(f"numeric-only violation raised {type(exc).__name__}: {exc}", False)
        failures.append("numeric-crash")

    print("\n" + "=" * 60)
    if failures:
        print(f"RESULT: FAILED — {len(failures)} assertion(s) failed:")
        for f in failures:
            print(f"  - {f}")
        print("=" * 60)
        return 1

    print("RESULT: PASSED — sort key handles numeric + text-slug + mixed cases.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
