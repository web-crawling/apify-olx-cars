"""Build / refresh src/data/brand_categories.json.

Usage:
    # Refresh all 6 countries
    python scripts/build_brand_categories.py

    # Refresh a subset
    python scripts/build_brand_categories.py --countries pt,ua,kz

    # Polite mode (slower, useful if a domain throttles)
    python scripts/build_brand_categories.py --delay 0.5

How it works
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
    {country: {brand_name_lowercase: category_id}}

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


def discover_brands(
    country: str, delay: float, max_retries: int,
    output_path: str,
    current_result: dict[str, dict[str, int]],
    write_lock: threading.Lock,
) -> dict[str, int]:
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
    seeded_ids = {int(v) for v in existing_country_map.values() if isinstance(v, int)}
    cat_ids = cat_ids | seeded_ids
    logger.info('  %s: %d unique cat-ids (incl. %d seeded from prior data) — probing labels',
                country, len(cat_ids), len(seeded_ids))

    country_map: dict[str, int] = {}
    session = requests.Session()
    for cid in sorted(cat_ids):
        label = probe_brand(session, country, parent, cid, delay, max_retries)
        if label is None:
            continue
        key = label.lower()
        if key in country_map:
            continue
        country_map[key] = cid
        logger.info('  cat=%d: %s', cid, label)
        with write_lock:
            current_result[country] = country_map
            _write_json(output_path, current_result)

    logger.info('Country %s: %d brands.', country, len(country_map))
    return country_map


def _write_json(output_path: str, data: dict[str, dict[str, int]]) -> None:
    output: dict = {
        '_comment': (
            'Per-country brand-name → OLX category_id map. '
            'Schema: {country: {brand_lowercase: category_id}}. '
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument(
        '--countries',
        default=','.join(ALL_COUNTRIES),
        help='Comma-separated country codes to refresh (default: all). '
             'Existing data for excluded countries is preserved.',
    )
    parser.add_argument(
        '--delay', type=float, default=0.15,
        help='Per-request delay in seconds (default: 0.15). '
             'Raise on rate-limit-prone domains.',
    )
    parser.add_argument(
        '--max-retries', type=int, default=3,
        help='Max retries on HTTP 403 with exponential backoff (default: 3).',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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
