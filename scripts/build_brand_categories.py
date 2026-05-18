"""Build / refresh src/data/brand_categories.json.

Usage:
    # Refresh all 6 countries
    python scripts/build_brand_categories.py

    # Refresh a subset
    python scripts/build_brand_categories.py --countries pt,ua,kz

    # Polite mode (slower, useful if a domain throttles)
    python scripts/build_brand_categories.py --delay 0.5

    # Dump color ID maps for UA and KZ (separate subcommand)
    python scripts/build_brand_categories.py --dump-color-ids
    python scripts/build_brand_categories.py --dump-color-ids --countries ua
    python scripts/build_brand_categories.py --dump-color-ids --delay 0.2

    The --dump-color-ids mode harvests numeric color id -> localised label pairs
    from listing params (not metadata filters — those require auth).  It samples
    many listing pages across multiple sort orders, collects every ``color`` param
    value encountered, and writes the result to:
        src/data/_color_ids_ua.json
        src/data/_color_ids_kz.json
    It also prints a Python-literal snippet suitable for pasting into
    src/data/param_maps.py.  Only UA and KZ are targeted (RO/PL/BG/PT return
    text slugs, not numeric ids, so no map is needed for them).
    The --dump-color-ids mode does NOT touch brand_categories.json.

How it works (brand discovery)
------------
For each country, the script:

1. Pulls listings from the parent cars category using multiple sort
   orders (so the sample covers the long tail of brands, not just the
   most-recent listings).
2. Collects the unique ``listing.category.id`` values that appear.
   These ARE the brand-leaf category IDs — OLX assigns each listing to
   the most-specific category, which for cars is the brand.
3. Probes each unique cat-id with a 1-item ``/api/v1/offers/`` lookup
   and reads ``metadata.adverts.config.targeting.cat_l2_name`` to get
   the human-readable brand name.
4. Filters out anything whose ``cat_l1_id`` doesn't match the parent
   cars cat-id (defensive — skips motos / boats / scooters etc.).

Output is written to src/data/brand_categories.json in the format:
    {country: {brand_name_lowercase: {"id": category_id, "label": "Display Name"}}}

The display ``label`` is the localised OLX ``cat_l2_name`` (e.g. "BMW"
on olx.ro, "Pozostałe osobowe" on olx.pl). It is used by the spider
as the ``make`` field value when listings are returned via a query
path that does NOT expose ``cat_l2_name`` at the metadata level — i.e.
parent-cat queries (startUrls without brand filter, free-text search).
See issue #40.

The script writes the JSON incrementally — after each successful brand
discovery — so an interrupted run loses at most one in-flight probe.

Notes:
  - RO and PL share the parent cars category id (84) and most legacy
    brand cat-ids (181-208), but newer brand-leaf cat-ids diverge
    (e.g. Dacia is 742 on olx.ro, 1347 on olx.pl). PL is discovered
    standalone — do NOT copy the RO map to PL.
  - This script replaces an earlier range-scan approach that hardcoded
    per-country category-id ranges. The listing-based discovery here
    works for any country without prior knowledge of where the brand
    IDs live.

Requirements:
  pip install requests  (only needed for this script, not the actor)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    logger.error(
        'requests library is required for this script. '
        'Install with: pip install requests'
    )
    sys.exit(1)

ALL_COUNTRIES = ('ro', 'pl', 'bg', 'pt', 'ua', 'kz')

# Per-country parent cars category. Discovered brand-leaf IDs are
# derived from listings, not from a hardcoded range.
PARENT_CAT = {
    'ro': 84,
    'pl': 84,
    'bg': 1117,
    'pt': 378,
    'ua': 108,
    'kz': 108,
}

DOMAIN = {
    'ro': 'www.olx.ro',
    'pl': 'www.olx.pl',
    'bg': 'www.olx.bg',
    'pt': 'www.olx.pt',
    'ua': 'www.olx.ua',
    'kz': 'www.olx.kz',
}

ACCEPT_LANGUAGE = {
    'ro': 'ro-RO,ro;q=0.9',
    'pl': 'pl-PL,pl;q=0.9',
    'bg': 'bg-BG,bg;q=0.9',
    'pt': 'pt-PT,pt;q=0.9',
    'ua': 'uk-UA,uk;q=0.9',
    'kz': 'ru-KZ,ru;q=0.9',
}

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)

SORT_ORDERS = ('created_at:desc', 'filter_float_price:asc', 'filter_float_price:desc')
SAMPLE_PAGES_PER_SORT = 11   # offsets 0, 40, ..., 400 — stays under offset>=1000 cap
PAGE_LIMIT = 40


def _headers(country: str) -> dict[str, str]:
    return {
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': ACCEPT_LANGUAGE.get(country, 'en'),
        'User-Agent': USER_AGENT,
    }


def collect_listing_categories(
    country: str, parent: int, delay: float,
) -> set[int]:
    """Pull many listings from the parent cars category and collect the
    unique listing.category.id values — those are the brand-leaf cats."""
    domain = DOMAIN[country]
    seen: set[int] = set()
    session = requests.Session()
    for sort in SORT_ORDERS:
        for offset in range(0, SAMPLE_PAGES_PER_SORT * PAGE_LIMIT, PAGE_LIMIT):
            url = (
                f'https://{domain}/api/v1/offers/?category_id={parent}'
                f'&limit={PAGE_LIMIT}&offset={offset}&sort={sort}'
            )
            try:
                resp = session.get(url, headers=_headers(country), timeout=15)
            except Exception as exc:
                logger.warning('  page sort=%s offset=%d: %s', sort, offset, exc)
                continue
            if resp.status_code != 200:
                logger.warning(
                    '  page sort=%s offset=%d: HTTP %d',
                    sort, offset, resp.status_code,
                )
                continue
            try:
                data = resp.json()
            except ValueError:
                continue
            listings = data.get('data') or []
            if not listings:
                break
            for listing in listings:
                cat = listing.get('category') or {}
                cid = cat.get('id')
                if isinstance(cid, int):
                    seen.add(cid)
            if delay > 0:
                time.sleep(delay)
        logger.info(
            '  %s sort=%s: %d unique listing.category.ids so far',
            country, sort, len(seen),
        )
    return seen


def probe_brand(
    session: requests.Session,
    country: str, parent: int, cat_id: int, delay: float,
    max_retries: int,
) -> str | None:
    """Probe a category-id and return its brand label if it's a valid
    car-brand leaf (cat_l1_id == parent and cat_l2_name present)."""
    domain = DOMAIN[country]
    url = f'https://{domain}/api/v1/offers/?category_id={cat_id}&limit=1&offset=0'
    backoff = 1.0
    for attempt in range(max_retries + 1):
        try:
            resp = session.get(url, headers=_headers(country), timeout=15)
        except Exception as exc:
            logger.debug('  cat=%d: network error: %s', cat_id, exc)
            return None
        if resp.status_code == 400:
            return None
        if resp.status_code == 403:
            if attempt < max_retries:
                logger.info(
                    '  cat=%d: HTTP 403 attempt %d/%d — backoff %.1fs',
                    cat_id, attempt + 1, max_retries, backoff,
                )
                time.sleep(backoff)
                backoff *= 2
                continue
            logger.warning('  cat=%d: HTTP 403 — retries exhausted', cat_id)
            return None
        if resp.status_code != 200:
            logger.warning('  cat=%d: HTTP %d', cat_id, resp.status_code)
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        md = data.get('metadata') or {}
        if not isinstance(md, dict):
            return None
        targeting = ((md.get('adverts') or {}).get('config') or {}).get('targeting') or {}
        cat_l2_name = (targeting.get('cat_l2_name') or '').strip()
        cat_l1_id = targeting.get('cat_l1_id')
        try:
            cat_l1_match = cat_l1_id is not None and int(cat_l1_id) == parent
        except (TypeError, ValueError):
            cat_l1_match = False
        if delay > 0:
            time.sleep(delay)
        if not cat_l2_name or not cat_l1_match:
            return None
        return cat_l2_name
    return None


def _extract_cat_id(entry) -> int | None:
    """Return the int cat-id from either an int (old format) or a dict
    with an "id" key (new format).
    """
    if isinstance(entry, int):
        return entry
    if isinstance(entry, dict):
        cid = entry.get('id')
        if isinstance(cid, int):
            return cid
    return None


def discover_brands(
    country: str, delay: float, max_retries: int,
    output_path: str,
    current_result: dict[str, dict],
    write_lock: threading.Lock,
) -> dict[str, dict[str, object]]:
    parent = PARENT_CAT[country]
    logger.info(
        'Scanning %s: parent=%d (delay=%.2fs, max_retries=%d)',
        DOMAIN[country], parent, delay, max_retries,
    )
    cat_ids = collect_listing_categories(country, parent, delay)
    # Seed with previously-known brands so rare ones (that may not appear
    # in this run's listing sample) survive across refreshes. The probe
    # still validates each cat-id is currently a valid car-brand leaf.
    existing_country_map = current_result.get(country) or {}
    seeded_ids: set[int] = set()
    for v in existing_country_map.values():
        cid = _extract_cat_id(v)
        if cid is not None:
            seeded_ids.add(cid)
    cat_ids = cat_ids | seeded_ids
    logger.info('  %s: %d unique cat-ids (incl. %d seeded from prior data) — probing labels',
                country, len(cat_ids), len(seeded_ids))

    country_map: dict[str, dict[str, object]] = {}
    session = requests.Session()
    for cid in sorted(cat_ids):
        label = probe_brand(session, country, parent, cid, delay, max_retries)
        if label is None:
            continue
        key = label.lower()
        if key in country_map:
            continue
        country_map[key] = {'id': cid, 'label': label}
        logger.info('  cat=%d: %s', cid, label)
        with write_lock:
            current_result[country] = country_map
            _write_json(output_path, current_result)

    logger.info('Country %s: %d brands.', country, len(country_map))
    return country_map


def _write_json(output_path: str, data: dict[str, dict]) -> None:
    output: dict = {
        '_comment': (
            'Per-country brand-name → {id, label} map. '
            'Schema: {country: {brand_lowercase: {"id": category_id, "label": "Display Name"}}}. '
            'The label is the localised OLX cat_l2_name; used by the spider as the '
            '`make` field value when listings come via a parent-cat query path (issue #40). '
            'Generated by scripts/build_brand_categories.py. Refresh quarterly.'
        ),
    }
    for country in ALL_COUNTRIES:
        output[country] = data.get(country) or {}
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tmp_path = output_path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
    os.replace(tmp_path, output_path)


# ---------------------------------------------------------------------------
# Color ID discovery (--dump-color-ids subcommand)
# Only UA and KZ return numeric color ids; other countries use text slugs.
# ---------------------------------------------------------------------------

COLOR_COUNTRIES = ('ua', 'kz')

# Listing pages sampled per sort order for color discovery.
# 20 pages × 50 items × 3 sort orders = up to 3,000 listing rows — enough to
# cover all active color ids in practice (typically ~20-25 unique values).
COLOR_SAMPLE_PAGES = 20
COLOR_PAGE_LIMIT = 50


def collect_color_ids(
    country: str, delay: float,
) -> dict[str, str]:
    """Sample many listing pages and collect all unique color id -> label pairs.

    The OLX category-params endpoint (/api/v1/categories/{id}/attributes/) requires
    an auth token.  Instead, color ids are harvested directly from the ``color``
    param in individual listing responses — the same unauthenticated endpoint used
    by the spider.  Sampling across multiple sort orders covers the full range of
    active color ids in practice.

    Returns a dict mapping numeric string id -> localised OLX label (Ukrainian for
    UA, Russian for KZ).
    """
    domain = DOMAIN[country]
    parent = PARENT_CAT[country]
    session = requests.Session()
    color_map: dict[str, str] = {}  # id_str -> label

    for sort in SORT_ORDERS:
        for page_idx in range(COLOR_SAMPLE_PAGES):
            offset = page_idx * COLOR_PAGE_LIMIT
            url = (
                f'https://{domain}/api/v1/offers/?category_id={parent}'
                f'&limit={COLOR_PAGE_LIMIT}&offset={offset}&sort={sort}'
            )
            try:
                resp = session.get(url, headers=_headers(country), timeout=15)
            except Exception as exc:
                logger.warning(
                    '  color %s sort=%s offset=%d: %s', country, sort, offset, exc,
                )
                continue
            if resp.status_code == 400:
                break  # offset cap hit
            if resp.status_code != 200:
                logger.warning(
                    '  color %s sort=%s offset=%d: HTTP %d',
                    country, sort, offset, resp.status_code,
                )
                continue
            try:
                data = resp.json()
            except ValueError:
                continue
            listings = data.get('data') or []
            if not listings:
                break  # no more results on this sort
            for listing in listings:
                for param in (listing.get('params') or []):
                    if param.get('key') != 'color':
                        continue
                    value = param.get('value') or {}
                    raw_key = value.get('key')
                    label = (value.get('label') or '').strip()
                    id_str = str(raw_key) if raw_key is not None else ''
                    if id_str and label and id_str not in color_map:
                        color_map[id_str] = label
            if delay > 0:
                time.sleep(delay)
        logger.info(
            '  color %s sort=%s: %d unique ids so far',
            country, sort, len(color_map),
        )

    return color_map


def _write_color_json(output_path: str, color_map: dict[str, str]) -> None:
    """Write color id map to a JSON file incrementally (tmp + rename)."""
    # Sort by numeric id for deterministic output
    ordered: dict[str, str] = dict(
        sorted(color_map.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 9999)
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tmp_path = output_path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as fh:
        json.dump(ordered, fh, ensure_ascii=False, indent=2)
    os.replace(tmp_path, output_path)


def _print_python_snippet(country: str, color_map: dict[str, str]) -> None:
    """Print a Python-literal snippet for pasting into param_maps.py.

    Labels are printed as Unicode escape sequences so the snippet is safe on
    Windows terminals with a narrow code-page (e.g. cp1252).
    """
    ordered = sorted(color_map.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 9999)
    var = 'UA_COLOR_MAP' if country == 'ua' else 'KZ_COLOR_MAP'
    lines = [f'\n# --- Python snippet for {var} ---', f'{var}: dict[str, str] = {{']
    for id_str, label in ordered:
        # Use ascii() to produce a safe representation of the Cyrillic label
        lines.append(f'    {id_str!r}: ...,  # {ascii(label)[1:-1]}')
    lines.append('}')
    snippet = '\n'.join(lines)
    try:
        print(snippet)
    except UnicodeEncodeError:
        print(snippet.encode('ascii', 'replace').decode('ascii'))


def main_dump_color_ids(args: argparse.Namespace) -> None:
    """Subcommand: discover color id maps for UA and KZ."""
    requested = [c.strip().lower() for c in args.countries.split(',') if c.strip()]
    # Only UA and KZ are supported for color id discovery
    scan = [c for c in requested if c in COLOR_COUNTRIES]
    skipped = [c for c in requested if c not in COLOR_COUNTRIES]
    if skipped:
        logger.info(
            'Skipping %s: color id maps only needed for ua/kz '
            '(other countries use text slugs).',
            skipped,
        )
    if not scan:
        logger.error('No valid color-id countries to scan. Pass --countries ua,kz or similar.')
        sys.exit(2)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    data_dir = os.path.join(repo_root, 'src', 'data')

    for country in scan:
        logger.info(
            'Discovering color ids for %s (delay=%.2fs)', DOMAIN[country], args.delay,
        )
        color_map = collect_color_ids(country, args.delay)
        logger.info('  %s: %d color ids discovered', country, len(color_map))

        # Write JSON output
        out_path = os.path.join(data_dir, f'_color_ids_{country}.json')
        _write_color_json(out_path, color_map)
        logger.info('  Written %s', out_path)

        # Print Python snippet
        _print_python_snippet(country, color_map)

    logger.info(
        '\nNext step: map each localised label to an English slug in '
        'src/data/param_maps.py (UA_COLOR_MAP / KZ_COLOR_MAP).'
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument(
        '--dump-color-ids',
        action='store_true',
        help=(
            'Discover color numeric id maps for UA and KZ by sampling listing '
            'params.  Writes src/data/_color_ids_ua.json and _color_ids_kz.json. '
            'Does NOT touch brand_categories.json.'
        ),
    )
    parser.add_argument(
        '--countries',
        default=','.join(ALL_COUNTRIES),
        help='Comma-separated country codes to refresh (default: all). '
             'Existing data for excluded countries is preserved. '
             'For --dump-color-ids: only ua/kz are valid targets.',
    )
    parser.add_argument(
        '--delay', type=float, default=0.15,
        help='Per-request delay in seconds (default: 0.15). '
             'Raise on rate-limit-prone domains.',
    )
    parser.add_argument(
        '--max-retries', type=int, default=3,
        help='Max retries on HTTP 403 with exponential backoff (default: 3). '
             'Brand discovery only; ignored for --dump-color-ids.',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.dump_color_ids:
        main_dump_color_ids(args)
        return

    requested = [c.strip().lower() for c in args.countries.split(',') if c.strip()]
    unknown = [c for c in requested if c not in ALL_COUNTRIES]
    if unknown:
        logger.error('Unknown country codes: %s. Valid: %s', unknown, ALL_COUNTRIES)
        sys.exit(2)

    scan_countries = [c for c in requested if c in PARENT_CAT]

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    output_path = os.path.join(repo_root, 'src', 'data', 'brand_categories.json')

    existing: dict[str, dict] = {}
    if os.path.exists(output_path):
        with open(output_path, encoding='utf-8') as fh:
            raw = json.load(fh)
        existing = {k: v for k, v in raw.items() if not k.startswith('_')}
        logger.info('Loaded existing brand_categories.json (%d countries)', len(existing))

    result: dict[str, dict[str, int]] = {k: dict(v) for k, v in existing.items()}
    write_lock = threading.Lock()

    for country in scan_countries:
        brands = discover_brands(
            country, args.delay, args.max_retries,
            output_path, result, write_lock,
        )
        if brands:
            result[country] = brands

    _write_json(output_path, result)
    logger.info('Written %s', output_path)
    total = sum(
        len(v) for k, v in result.items()
        if isinstance(v, dict) and k in ALL_COUNTRIES
    )
    logger.info('Total brands across all countries: %d', total)


if __name__ == '__main__':
    main()
