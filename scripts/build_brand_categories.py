"""One-off script to build / refresh src/data/brand_categories.json.

Usage:
    python scripts/build_brand_categories.py

This script walks per-domain numeric category ID ranges, calls the OLX
listing API with limit=1, and reads ``metadata.adverts.config.targeting``
to extract the brand name (cat_l2_name) and its listing count.

The output is written to src/data/brand_categories.json in the format:
    {country: {brand_name_lowercase: category_id}}

Run once before first deployment; refresh quarterly.

Requirements:
  pip install requests  (only needed for this script, not the actor)

Notes:
  - RO and PL share taxonomy (cat=183 is BMW on both, confirmed by
    efficiency-researcher).  The script scans RO and copies the result
    to PL.
  - BG brand range is contiguous 1119–1190.
  - UA range starts around 109; the script scans up to 200.
  - PT and KZ: the script scans up to 100 IDs above the parent cat.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# ---------------------------------------------------------------------------
# Domain → scan configuration
# ---------------------------------------------------------------------------

SCAN_CONFIG = {
    'ro': {
        'domain': 'www.olx.ro',
        'parent_cat_id': 84,
        # Empirically: RO brand range ~181–235
        'scan_start': 181,
        'scan_end': 240,
        'parent_l0_substring': 'Auto',  # cat_l0_name contains "Auto" for vehicles
    },
    'bg': {
        'domain': 'www.olx.bg',
        'parent_cat_id': 1117,
        # BG brand range confirmed 1119–1190
        'scan_start': 1119,
        'scan_end': 1200,
        'parent_l0_substring': 'Автомобили',
    },
    'pt': {
        'domain': 'www.olx.pt',
        'parent_cat_id': 378,
        'scan_start': 379,
        'scan_end': 500,
        'parent_l0_substring': 'Carros',
    },
    'ua': {
        'domain': 'www.olx.ua',
        'parent_cat_id': 108,
        # UA range approximately 109–200 based on efficiency-researcher findings
        'scan_start': 109,
        'scan_end': 200,
        'parent_l0_substring': '',  # Empty — match by parent cat ID
    },
    'kz': {
        'domain': 'www.olx.kz',
        'parent_cat_id': 108,
        'scan_start': 109,
        'scan_end': 200,
        'parent_l0_substring': '',
    },
}

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)

REQUEST_DELAY = 0.1  # seconds between requests per domain
MAX_WORKERS = 4


# ---------------------------------------------------------------------------
# Discovery functions
# ---------------------------------------------------------------------------

def fetch_category_info(
    session: requests.Session,
    domain: str,
    category_id: int,
    accept_language: str,
) -> dict | None:
    """Fetch one offer from a category and return targeting metadata.

    Returns a dict with keys: category_id, brand_name, visible_count
    or None if the category is not a valid car-brand leaf.
    """
    url = f'https://{domain}/api/v1/offers/?category_id={category_id}&limit=1&offset=0'
    try:
        resp = session.get(
            url,
            headers={
                'Accept': 'application/json',
                'Accept-Language': accept_language,
                'User-Agent': USER_AGENT,
            },
            timeout=15,
        )
        if resp.status_code == 400:
            return None  # Category does not exist
        if resp.status_code != 200:
            logger.warning('HTTP %d for cat=%d on %s', resp.status_code, category_id, domain)
            return None
        data = resp.json()
        metadata = data.get('metadata') or {}
        targeting = (
            metadata.get('adverts', {})
            .get('config', {})
            .get('targeting', {})
        )
        cat_l2_name = targeting.get('cat_l2_name') or ''
        cat_l1_id = targeting.get('cat_l1_id')
        cat_l0_name = targeting.get('cat_l0_name') or ''
        cat_l1_name = targeting.get('cat_l1_name') or ''
        visible_count = metadata.get('visible_total_count', 0)

        if not cat_l2_name:
            return None

        return {
            'category_id': category_id,
            'brand_name': cat_l2_name,
            'cat_l1_id': cat_l1_id,
            'cat_l0_name': cat_l0_name,
            'cat_l1_name': cat_l1_name,
            'visible_count': visible_count,
        }
    except Exception as exc:
        logger.debug('Error fetching cat=%d on %s: %s', category_id, domain, exc)
        return None


def discover_brands(
    country: str,
    config: dict,
    accept_language: str,
) -> dict[str, int]:
    """Walk the category range for a country and return brand→category_id map."""
    domain = config['domain']
    parent_cat_id = config['parent_cat_id']
    scan_start = config['scan_start']
    scan_end = config['scan_end']
    parent_l0_sub = config.get('parent_l0_substring', '')

    logger.info(
        'Scanning %s: cat range %d–%d (parent=%d)',
        domain, scan_start, scan_end, parent_cat_id,
    )

    result: dict[str, int] = {}
    session = requests.Session()

    cat_ids = list(range(scan_start, scan_end + 1))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                fetch_category_info, session, domain, cid, accept_language
            ): cid
            for cid in cat_ids
        }
        completed = 0
        for future in as_completed(futures):
            completed += 1
            info = future.result()
            if info is None:
                continue

            # Filter: only keep entries that belong to the car-brand level
            cat_l1_id = info.get('cat_l1_id')
            cat_l0_name = info.get('cat_l0_name', '')
            brand_name = info['brand_name']
            vis = info['visible_count']
            cid = info['category_id']

            # Accept this entry if:
            #   (a) cat_l1_id matches parent_cat_id (most reliable), OR
            #   (b) cat_l0_name contains the expected substring
            is_car_brand = (
                (cat_l1_id is not None and int(cat_l1_id) == parent_cat_id)
                or (parent_l0_sub and parent_l0_sub.lower() in cat_l0_name.lower())
            )
            if not is_car_brand:
                continue

            brand_key = brand_name.strip().lower()
            if brand_key in result:
                # Keep the one with more listings (more likely to be the primary cat)
                existing_cid = result[brand_key]
                logger.debug(
                    'Duplicate brand %r: existing cat=%d vs new cat=%d (%d visible) — keeping higher',
                    brand_name, existing_cid, cid, vis,
                )
                # We can't compare visible counts here without re-fetching; keep first
                continue

            result[brand_key] = cid
            logger.info('  Found: %s (cat=%d, visible=%d)', brand_name, cid, vis)

            # Polite delay
            time.sleep(REQUEST_DELAY / MAX_WORKERS)

    logger.info('Country %s: discovered %d brands.', country, len(result))
    return result


ACCEPT_LANGUAGE_MAP: dict[str, str] = {
    'ro': 'ro-RO,ro;q=0.9',
    'pl': 'pl-PL,pl;q=0.9',
    'bg': 'bg-BG,bg;q=0.9',
    'pt': 'pt-PT,pt;q=0.9',
    'ua': 'uk-UA,uk;q=0.9',
    'kz': 'ru-KZ,ru;q=0.9',
}


def main() -> None:
    # Output path: src/data/brand_categories.json relative to repo root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    output_path = os.path.join(repo_root, 'src', 'data', 'brand_categories.json')

    # Load existing data so we can update incrementally
    existing: dict[str, dict] = {}
    if os.path.exists(output_path):
        with open(output_path, encoding='utf-8') as fh:
            raw = json.load(fh)
        existing = {k: v for k, v in raw.items() if not k.startswith('_')}
        logger.info('Loaded existing brand_categories.json (%d countries)', len(existing))
    else:
        logger.info('No existing brand_categories.json — building from scratch.')

    result: dict[str, dict[str, int]] = {
        k: dict(v) for k, v in existing.items()
    }

    # Scan each country
    for country, config in SCAN_CONFIG.items():
        accept_lang = ACCEPT_LANGUAGE_MAP.get(country, 'en')
        brands = discover_brands(country, config, accept_lang)
        if brands:
            result[country] = brands
            logger.info('Updated country %r with %d brands.', country, len(brands))
        else:
            logger.warning('No brands discovered for country %r — keeping existing data.', country)

    # PL shares RO taxonomy (efficiency-researcher confirmed)
    if 'ro' in result and result['ro']:
        result['pl'] = dict(result['ro'])
        logger.info('Copied RO brand map to PL (%d brands).', len(result['pl']))

    # Write output
    output_data: dict = {
        '_comment': (
            'Per-country brand-name → OLX category_id map. '
            'Schema: {country: {brand_lowercase: category_id}}. '
            'Generated by scripts/build_brand_categories.py. Refresh quarterly.'
        ),
    }
    for country in ('ro', 'pl', 'bg', 'pt', 'ua', 'kz'):
        output_data[country] = result.get(country) or {}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as fh:
        json.dump(output_data, fh, ensure_ascii=False, indent=2)

    logger.info('Written %s', output_path)
    total_brands = sum(len(v) for v in output_data.values() if isinstance(v, dict))
    logger.info('Total brands across all countries: %d', total_brands)


if __name__ == '__main__':
    main()
