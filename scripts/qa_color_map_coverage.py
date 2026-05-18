"""QA probe: verify UA and KZ color id coverage against live OLX listings.

Run with: PYTHONIOENCODING=utf-8 python scripts/qa_color_map_coverage.py
(or the script sets it automatically at startup)

Fetches a meaningful sample of listings per country (parent cars category,
several sort orders, ~3 pages each), collects every observed color param
numeric id, and reports coverage against UA_COLOR_MAP / KZ_COLOR_MAP.

Usage:
    python scripts/qa_color_map_coverage.py

Exit codes:
    0 — all observed live ids are covered by the canonical maps
    1 — one or more observed live ids are MISSING from the canonical maps

Reusable for future quarterly audits.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import urllib.request
import urllib.error

# Force UTF-8 stdout so Cyrillic labels print correctly on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Path setup — resolve src package so we can import param_maps directly
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.data.param_maps import UA_COLOR_MAP, KZ_COLOR_MAP  # noqa: E402


def _load_json(path: Path) -> dict[str, str]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)

UA_COLOR_IDS_FILE = REPO_ROOT / "src" / "data" / "_color_ids_ua.json"
KZ_COLOR_IDS_FILE = REPO_ROOT / "src" / "data" / "_color_ids_kz.json"

# ---------------------------------------------------------------------------
# OLX API constants
# ---------------------------------------------------------------------------
COUNTRY_CONFIG: dict[str, dict[str, Any]] = {
    "ua": {
        "domain": "www.olx.ua",
        "category": 108,
        "map": UA_COLOR_MAP,
        "ids_file": UA_COLOR_IDS_FILE,
        "label": "Ukraine (UA)",
    },
    "kz": {
        "domain": "www.olx.kz",
        "category": 108,
        "map": KZ_COLOR_MAP,
        "ids_file": KZ_COLOR_IDS_FILE,
        "label": "Kazakhstan (KZ)",
    },
}

SORT_ORDERS = [
    "created_at:desc",
    "filter_float_price:asc",
    "filter_float_price:desc",
]
PAGES_PER_SORT = 3
LIMIT = 50  # listings per page

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def fetch_json(url: str) -> dict | None:
    """Fetch a URL and return parsed JSON, or None on error."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read()
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        print(f"    HTTP {exc.code} for {url}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"    Error fetching {url}: {exc}", file=sys.stderr)
        return None


def collect_color_ids_for_country(
    domain: str,
    category: int,
) -> tuple[int, set[str]]:
    """Return (total_listings_sampled, set_of_observed_color_ids)."""
    observed: set[str] = set()
    total_sampled = 0

    for sort in SORT_ORDERS:
        print(f"  sort={sort!r}: ", end="", flush=True)
        for page in range(PAGES_PER_SORT):
            offset = page * LIMIT
            url = (
                f"https://{domain}/api/v1/offers/"
                f"?category={category}&limit={LIMIT}&offset={offset}&sort={sort}"
            )
            data = fetch_json(url)
            if data is None:
                print(f"[page {page+1} ERR] ", end="", flush=True)
                continue

            listings = data.get("data", [])
            total_sampled += len(listings)

            for listing in listings:
                params = listing.get("params", [])
                for param in params:
                    if param.get("key") == "color":
                        val = param.get("value", {})
                        raw_key = val.get("key")
                        if raw_key is not None:
                            observed.add(str(raw_key))
            print(f"[page {page+1}: {len(listings)} listings] ", end="", flush=True)
            time.sleep(0.25)  # gentle rate limit
        print()  # newline after each sort order

    return total_sampled, observed


def _sort_key_mixed(x: str) -> tuple:
    """Sort numeric ids before text slugs."""
    try:
        return (0, int(x), "")
    except ValueError:
        return (1, 0, x)


def report_country(
    country_code: str,
    config: dict,
    total: int,
    observed: set[str],
) -> bool:
    """Print per-country report. Returns True if all observed ids are covered."""
    canonical_map: dict[str, str] = config["map"]
    ids_file: Path = config["ids_file"]
    label: str = config["label"]

    canonical_ids = set(canonical_map.keys())

    # Load the reference JSON file for comparison (once)
    ref_data_full: dict[str, str] = _load_json(ids_file) if ids_file.exists() else {}
    ref_ids = set(ref_data_full.keys())

    # Partition observed values: numeric-looking ids vs text slugs.
    # Text slugs pass through the loader unchanged (UA_COLOR_MAP.get(x, x)).
    # Only numeric ids that are NOT in the canonical map are true gaps.
    numeric_observed = {v for v in observed if v.isdigit()}
    text_observed = observed - numeric_observed

    numeric_unmapped = numeric_observed - canonical_ids   # TRUE FAILURES
    text_unmapped = text_observed - canonical_ids         # pass-through (pre-existing)
    covered = observed & canonical_ids
    in_map_not_observed = canonical_ids - observed

    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  Listings sampled               : {total}")
    print(f"  Unique color values seen       : {len(observed)}")
    print(f"    - numeric ids                : {len(numeric_observed)}")
    print(f"    - text slugs (loader pass-thru): {len(text_observed)}")
    if text_observed:
        print(f"      text slugs observed: {sorted(text_observed)}")
    print(f"  Covered by canonical map       : {len(covered)}")
    print(f"  Numeric ids UNMAPPED (GAPS)    : {len(numeric_unmapped)}  <-- only these are failures")
    print(f"  Text slugs not in map          : {len(text_unmapped)}  (pass-through, not failures)")

    if numeric_unmapped:
        print(f"\n  !! NUMERIC ID GAPS (MAP FAILURES): {sorted(numeric_unmapped, key=int)}")
    else:
        print("  -> All observed numeric ids are covered. No numeric gaps.")

    if text_unmapped:
        print(f"\n  NOTE — text slugs passing through (pre-existing behavior):")
        for slug in sorted(text_unmapped):
            print(f"    {slug!r}")

    print(f"\n  Ids in canonical map not observed in this sample ({len(in_map_not_observed)}):")
    if in_map_not_observed:
        for uid in sorted(in_map_not_observed, key=_sort_key_mixed):
            mapped_slug = canonical_map[uid]
            in_ref = uid in ref_ids
            ref_label = ref_data_full.get(uid, "N/A")
            print(f"    id={uid:>3}  -> slug={mapped_slug!r:<12}  ref_label={ref_label!r}  in_ref_json={in_ref}")
    else:
        print("    (all map ids were observed)")

    print(f"\n  Diff: canonical_map keys vs ref JSON ({ids_file.name}) keys:")
    only_in_map = canonical_ids - ref_ids
    only_in_ref = ref_ids - canonical_ids
    if only_in_map:
        print(f"    In map but NOT in ref JSON: {sorted(only_in_map, key=_sort_key_mixed)}")
    if only_in_ref:
        print(f"    In ref JSON but NOT in map: {sorted(only_in_ref, key=_sort_key_mixed)}")
    if not only_in_map and not only_in_ref:
        print("    -> map and ref JSON have identical key sets. Good.")

    print(f"\n  Full observed value -> slug table:")
    print(f"  {'value':>10}  {'map_slug':<15}  {'status':<20}  ref_label")
    print(f"  {'-'*10}  {'-'*15}  {'-'*20}  ---------")
    for uid in sorted(observed, key=_sort_key_mixed):
        slug = canonical_map.get(uid, "—")
        is_numeric = uid.isdigit()
        if uid in canonical_ids:
            status = "COVERED"
        elif is_numeric:
            status = "NUMERIC GAP <-- FAIL"
        else:
            status = "text pass-through"
        ref_label = ref_data_full.get(uid, "(text slug)")
        print(f"  {uid:>10}  {slug:<15}  {status:<20}  {ref_label}")

    # Only numeric-id gaps are true failures for this map
    return len(numeric_unmapped) == 0


def check_slug_vocabulary(
    ua_map: dict[str, str],
    kz_map: dict[str, str],
) -> bool:
    """Verify every value in both maps is in the canonical slug vocabulary."""
    canonical_slugs = {
        "black", "white", "silver", "gray", "red", "blue", "green",
        "yellow", "orange", "brown", "beige", "gold", "purple",
        "other",
    }
    all_ok = True
    for country_code, color_map in (("ua", ua_map), ("kz", kz_map)):
        non_canonical = {
            (uid, slug)
            for uid, slug in color_map.items()
            if slug not in canonical_slugs
        }
        if non_canonical:
            print(f"\n  !! SLUG VOCABULARY VIOLATION in {country_code.upper()}_COLOR_MAP:")
            for uid, slug in sorted(non_canonical, key=lambda pair: _sort_key_mixed(pair[0])):
                print(f"    id={uid}  slug={slug!r}  -- NOT in canonical vocabulary")
            all_ok = False
    if all_ok:
        print("\n  Slug vocabulary check: PASSED — all slugs are canonical.")
    return all_ok


def main() -> int:
    print("=" * 60)
    print("OLX UA/KZ Color Map Coverage QA Probe")
    print("=" * 60)

    all_passed = True
    results: dict[str, tuple[int, set[str]]] = {}

    for country_code, config in COUNTRY_CONFIG.items():
        print(f"\n[{config['label']}] Fetching listings...")
        total, observed = collect_color_ids_for_country(
            config["domain"],
            config["category"],
        )
        results[country_code] = (total, observed)

    print("\n\n" + "=" * 60)
    print("COVERAGE REPORTS")
    print("=" * 60)

    for country_code, (total, observed) in results.items():
        ok = report_country(country_code, COUNTRY_CONFIG[country_code], total, observed)
        if not ok:
            all_passed = False

    print("\n\n" + "=" * 60)
    print("SLUG VOCABULARY CHECK")
    print("=" * 60)
    vocab_ok = check_slug_vocabulary(UA_COLOR_MAP, KZ_COLOR_MAP)
    if not vocab_ok:
        all_passed = False

    print("\n\n" + "=" * 60)
    if all_passed:
        print("OVERALL RESULT: PASSED — no gaps, no vocabulary violations.")
    else:
        print("OVERALL RESULT: FAILED — see GAPS / vocabulary violations above.")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
