"""OLX Cars spider.

Scrapes car listings from OLX across six country domains:
  RO, PL, BG, PT, UA, KZ

All data is fetched from the unauthenticated JSON API:
  GET https://www.<domain>/api/v1/offers/?category_id=<id>&limit=50&offset=<n>&...

No detail-page follow-ups are required — the listing payload contains
every field that the single-offer detail endpoint returns.

Two input modes:
  1. Structured-filter mode: use ``country`` + optional brand/year/price
     filters.  Brand names are resolved to per-country category_ids via
     the bundled ``src/data/brand_categories.json``.
  2. startUrls mode: paginate any OLX car listing or search URL directly.
     Structured filters (except maxItems and sortBy) are ignored.

Pagination:
  offset 0 → 50 → 100 … up to min(total_elements, 1000).
  Server returns HTTP 400 when offset > 1000 — this is the normal
  pagination termination signal (not an error).

1000-cap strategy:
  When maxItems > 1000 and no startUrls, the spider slices by brand-leaf
  category_id (primary), then year band (secondary), then price band
  (tertiary) to maximise coverage.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Generator
from urllib.parse import urlencode, urlparse, parse_qs, urljoin

import scrapy
from scrapy.exceptions import CloseSpider

from ..items import CarItem
from ..itemloaders import CarItemLoader
from ..data.param_maps import (
    PARAM_KEY_MAP,
    FUEL_NORMALIZATION,
    TRANSMISSION_NORMALIZATION,
    BODY_NORMALIZATION,
    CONDITION_NORMALIZATION,
    CONDITION_SEVERITY,
    UA_COLOR_MAP,
    KZ_COLOR_MAP,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)

ACCEPT_LANGUAGE: dict[str, str] = {
    'ro': 'ro-RO,ro;q=0.9,en;q=0.8',
    'pl': 'pl-PL,pl;q=0.9,en;q=0.8',
    'bg': 'bg-BG,bg;q=0.9,en;q=0.8',
    'pt': 'pt-PT,pt;q=0.9,en;q=0.8',
    'ua': 'uk-UA,uk;q=0.9,ru;q=0.8,en;q=0.7',
    'kz': 'ru-KZ,ru;q=0.9,kk;q=0.8,en;q=0.7',
}

COUNTRY_DOMAIN: dict[str, str] = {
    'ro': 'www.olx.ro',
    'pl': 'www.olx.pl',
    'bg': 'www.olx.bg',
    'pt': 'www.olx.pt',
    'ua': 'www.olx.ua',
    'kz': 'www.olx.kz',
}

DOMAIN_COUNTRY: dict[str, str] = {v: k for k, v in COUNTRY_DOMAIN.items()}

CARS_CATEGORY_ID: dict[str, int] = {
    'ro': 84,
    'pl': 84,
    'bg': 1117,
    'pt': 378,
    'ua': 108,
    'kz': 108,
}

# Secondary slice axis: year bands for brands with > 1000 visible listings
YEAR_BANDS = [
    (None, 1990),
    (1990, 2000),
    (2000, 2005),
    (2005, 2010),
    (2010, 2015),
    (2015, 2020),
    (2020, None),
]

# Tertiary slice axis: price bands (EUR) for brand×year cells still > 1000
PRICE_BANDS = [
    (0, 5000),
    (5000, 10000),
    (10000, 20000),
    (20000, 50000),
    (50000, None),
]

PAGE_LIMIT = 50


def _load_brand_categories() -> dict[str, dict[str, int]]:
    """Load brand→category_id map from bundled JSON file."""
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    path = os.path.normpath(os.path.join(data_dir, 'brand_categories.json'))
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        # Strip internal comment keys
        return {k: v for k, v in data.items() if not k.startswith('_')}
    except FileNotFoundError:
        logger.error('brand_categories.json not found at %s', path)
        return {}
    except Exception as exc:
        logger.error('Failed to load brand_categories.json: %s', exc)
        return {}


def _build_api_headers(country: str) -> dict[str, str]:
    """Build the HTTP headers for a per-country OLX API request."""
    return {
        'Accept': 'application/json',
        'Accept-Language': ACCEPT_LANGUAGE.get(country, 'en'),
        'User-Agent': USER_AGENT,
    }


def _api_url(domain: str, params: dict[str, Any]) -> str:
    """Build an OLX listing API URL with query parameters."""
    base = f'https://{domain}/api/v1/offers/'
    return f'{base}?{urlencode(params)}'


def _detect_country_from_url(url: str) -> str | None:
    """Detect the OLX country code from a URL's hostname."""
    try:
        parsed = urlparse(url)
        hostname = parsed.netloc.lower()
        # Strip port if present
        hostname = hostname.split(':')[0]
        return DOMAIN_COUNTRY.get(hostname)
    except Exception:
        return None


def _strip_pagination_params(url: str) -> str:
    """Return the URL with offset, page, and limit params removed.

    The spider owns pagination; any offset in a user-supplied URL is
    replaced with our own sequence starting at 0.
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    for p in ('offset', 'page', 'limit'):
        qs.pop(p, None)
    from urllib.parse import urlencode as _urlencode
    new_query = _urlencode({k: v[0] for k, v in qs.items()})
    return parsed._replace(query=new_query).geturl()


class OlxCarsSpider(scrapy.Spider):
    """Main OLX Cars spider."""

    name = 'olx_cars'

    # Class-level flag — set True on fatal error; checked by main.py after crawl.
    # CRITICAL: must be a CLASS attribute (not instance attribute) because
    # CrawlerRunner.crawl() returns None, so main.py cannot access the instance.
    crawl_failed: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        # Read all actor input from the INPUT_DATA Scrapy setting (set by main.py)
        settings = kwargs.get('_settings') or {}
        input_data: dict[str, Any] = {}
        # Note: settings are accessed via self.settings after Scrapy injects them.
        # We defer reading to start_requests() where self.settings is available.

        # Spider-level counters
        self._total_yielded: int = 0
        self.skipped_partner_count: int = 0

        # Track max total_elements seen per category_id for cap detection
        self._total_elements_by_cat: dict[str, int] = {}

        logger.info('OlxCarsSpider initialised.')

    def start_requests(self) -> Generator:
        """Build initial requests from actor input.

        Input is read from the Scrapy setting INPUT_DATA (a dict) which
        is populated by main.py before the crawl starts.

        Precedence: startUrls > structured filters.
        """
        input_data: dict[str, Any] = self.settings.get('INPUT_DATA') or {}

        start_urls_raw: list = input_data.get('startUrls') or []
        country: str = str(input_data.get('country') or 'ro').lower()
        brands_raw: list[str] = input_data.get('brands') or []
        query: str | None = input_data.get('query') or None
        year_from: int | None = input_data.get('yearFrom')
        year_to: int | None = input_data.get('yearTo')
        price_from: int | None = input_data.get('priceFrom')
        price_to: int | None = input_data.get('priceTo')
        price_currency: str = str(input_data.get('priceCurrency') or 'EUR')
        sort_by: str = str(input_data.get('sortBy') or 'created_at:desc')
        max_items: int = int(input_data.get('maxItems') or 1000)

        # Validate country
        if country not in COUNTRY_DOMAIN:
            logger.warning(
                'Unknown country %r — defaulting to "ro". '
                'Valid values: ro, pl, bg, pt, ua, kz.',
                country,
            )
            country = 'ro'

        # Normalise startUrls: accept both plain strings and {"url": "..."} dicts
        start_urls: list[str] = []
        for entry in start_urls_raw:
            if isinstance(entry, str) and entry.strip():
                start_urls.append(entry.strip())
            elif isinstance(entry, dict) and entry.get('url'):
                start_urls.append(str(entry['url']).strip())

        # Warn if structured filters are set alongside startUrls (they're ignored)
        if start_urls and any([brands_raw, query, year_from, year_to,
                                price_from, price_to]):
            logger.warning(
                'startUrls provided — structured filters (brands, query, yearFrom, '
                'yearTo, priceFrom, priceTo) are IGNORED. Only maxItems and sortBy apply.'
            )

        # Stash common kwargs for callbacks
        self._max_items = max_items
        self._sort_by = sort_by

        # -------------------------------------------------------------------
        # Mode A: startUrls
        # -------------------------------------------------------------------
        if start_urls:
            logger.info('startUrls mode: %d URLs provided.', len(start_urls))
            for url in start_urls:
                detected_country = _detect_country_from_url(url)
                if detected_country is None:
                    logger.warning(
                        'URL %r does not match any supported OLX domain '
                        '(ro/pl/bg/pt/ua/kz) — skipping.', url
                    )
                    continue

                domain = COUNTRY_DOMAIN[detected_country]
                clean_url = _strip_pagination_params(url)

                # Extract any existing filter params from the URL to forward them,
                # but we control offset/limit ourselves.
                parsed = urlparse(clean_url)
                qs = parse_qs(parsed.query, keep_blank_values=True)
                base_params: dict[str, Any] = {
                    k: v[0] for k, v in qs.items()
                    if k not in ('offset', 'limit', 'page')
                }
                # Try to extract category_id from the URL params
                category_id = int(base_params.get('category_id', 0)) or None
                if category_id is None:
                    # Fallback to parent cars category for this country
                    category_id = CARS_CATEGORY_ID[detected_country]
                    base_params['category_id'] = category_id

                yield from self._page_requests(
                    domain=domain,
                    country=detected_country,
                    category_id=category_id,
                    base_params=base_params,
                    sort_by=sort_by,
                    offset=0,
                    cat_l2_name=None,
                    slice_label=f'startUrl:{url[:60]}',
                )
            return

        # -------------------------------------------------------------------
        # Mode B: Structured filters
        # -------------------------------------------------------------------
        domain = COUNTRY_DOMAIN[country]
        brand_categories = _load_brand_categories()
        country_brand_map: dict[str, int] = brand_categories.get(country) or {}

        # Resolve brand names to category_ids
        if brands_raw:
            category_ids: list[int] = []
            for brand_name in brands_raw:
                key = brand_name.strip().lower()
                cat_id = country_brand_map.get(key)
                if cat_id is not None:
                    category_ids.append(cat_id)
                else:
                    available = ', '.join(sorted(country_brand_map.keys())) or '(none yet — run build_brand_categories.py)'
                    logger.warning(
                        'Brand %r not found in brand map for country %r. '
                        'Available brands: %s',
                        brand_name, country, available,
                    )
            if not category_ids:
                logger.error(
                    'None of the requested brands could be resolved for country %r. '
                    'Falling back to parent cars category.',
                    country,
                )
                category_ids = [CARS_CATEGORY_ID[country]]
        elif max_items <= 1000:
            # No brands specified + maxItems fits in one slice: use parent category
            logger.info(
                'No brands specified; using parent cars category_id=%d for %r.',
                CARS_CATEGORY_ID[country], country,
            )
            category_ids = [CARS_CATEGORY_ID[country]]
        else:
            # Full-enumeration mode: iterate all known brand-leaf categories
            if country_brand_map:
                category_ids = list(set(country_brand_map.values()))
                logger.info(
                    'Full-enumeration mode: %d brand categories for %r.',
                    len(category_ids), country,
                )
            else:
                logger.warning(
                    'Full-enumeration mode requested (maxItems=%d) but brand_categories.json '
                    'has no entries for country %r. '
                    'Falling back to parent cars category — results will be capped at 1000. '
                    'Run scripts/build_brand_categories.py to build the brand map.',
                    max_items, country,
                )
                category_ids = [CARS_CATEGORY_ID[country]]

        # Build common filter params (applied to all category_id slices)
        base_params: dict[str, Any] = {}
        if query:
            base_params['query'] = query
        if year_from is not None:
            base_params['filter_float_year:from'] = year_from
        if year_to is not None:
            base_params['filter_float_year:to'] = year_to
        if price_from is not None:
            base_params['filter_float_price:from'] = price_from
        if price_to is not None:
            base_params['filter_float_price:to'] = price_to
        # Note: priceCurrency filter is applied at API level via the filter param
        # OLX uses the currency of the listed price; there is no explicit currency
        # param for the filter endpoint — the price filter values are compared
        # against whatever currency the seller used.  We pass priceCurrency for
        # reference but the API does not accept it as a distinct query param.
        # Log a note so users understand filter behaviour.
        if price_from is not None or price_to is not None:
            logger.info(
                'Price filter applied: %s–%s %s. Note: OLX filters by the listed '
                'price regardless of currency — results may include listings in '
                'other currencies whose numeric values fall in this range.',
                price_from, price_to, price_currency,
            )

        for category_id in category_ids:
            yield from self._page_requests(
                domain=domain,
                country=country,
                category_id=category_id,
                base_params=base_params,
                sort_by=sort_by,
                offset=0,
                cat_l2_name=None,
                slice_label=f'cat:{category_id}',
            )

    # ------------------------------------------------------------------
    # Request builder helpers
    # ------------------------------------------------------------------

    def _page_requests(
        self,
        domain: str,
        country: str,
        category_id: int,
        base_params: dict[str, Any],
        sort_by: str,
        offset: int,
        cat_l2_name: str | None,
        slice_label: str,
    ) -> Generator:
        """Yield the first paginated API request for a given slice."""
        params: dict[str, Any] = {
            'category_id': category_id,
            'limit': PAGE_LIMIT,
            'offset': offset,
            'sort_by': sort_by,
            **base_params,
        }
        url = _api_url(domain, params)
        yield scrapy.Request(
            url=url,
            method='GET',
            callback=self.parse_listing,
            errback=self.errback_fatal,
            headers=_build_api_headers(country),
            cb_kwargs={
                'domain': domain,
                'country': country,
                'category_id': category_id,
                'base_params': base_params,
                'sort_by': sort_by,
                'offset': offset,
                'cat_l2_name': cat_l2_name,
                'slice_label': slice_label,
            },
            dont_filter=True,
        )

    # ------------------------------------------------------------------
    # Parse: listing API page
    # ------------------------------------------------------------------

    def parse_listing(
        self,
        response,
        domain: str,
        country: str,
        category_id: int,
        base_params: dict[str, Any],
        sort_by: str,
        offset: int,
        cat_l2_name: str | None,
        slice_label: str,
    ) -> Generator:
        """Parse one page of OLX listing API results.

        Yields CarItems and schedules the next page when more results exist.
        Also handles the 1000-cap detection and brand×year sub-slicing.
        """
        if response.status == 400:
            # Expected when offset > 1000 — normal pagination termination
            if offset > 0:
                logger.debug(
                    'HTTP 400 at offset=%d for %s — pagination cap reached (expected).',
                    offset, slice_label,
                )
            else:
                # offset=0 with 400 means invalid category_id or bad params
                logger.error(
                    'HTTP 400 at offset=0 for %s — invalid category_id=%d or params. '
                    'Skipping this slice.',
                    slice_label, category_id,
                )
            return

        if response.status != 200:
            logger.error(
                'HTTP %s from OLX API for %s (offset=%d) — marking crawl as failed.',
                response.status, slice_label, offset,
            )
            type(self).crawl_failed = True
            return

        try:
            data = response.json()
        except Exception as exc:
            logger.error(
                'Failed to parse JSON from OLX API (offset=%d, %s): %s',
                offset, slice_label, exc,
            )
            type(self).crawl_failed = True
            return

        offers: list[dict] = data.get('data') or []
        metadata: dict = data.get('metadata') or {}
        total_elements: int = int(metadata.get('total_elements') or 0)
        visible_total_count: int = int(metadata.get('visible_total_count') or 0)

        # Capture cat_l2_name from first page metadata (brand display name)
        if cat_l2_name is None and offset == 0:
            targeting = (
                metadata.get('adverts', {})
                .get('config', {})
                .get('targeting', {})
            )
            cat_l2_name = targeting.get('cat_l2_name') or None
            if cat_l2_name:
                logger.debug(
                    'Resolved cat_l2_name=%r for category_id=%d (country=%s)',
                    cat_l2_name, category_id, country,
                )

        # Track total_elements for this slice (used for cap detection)
        slice_key = f'{slice_label}'
        self._total_elements_by_cat[slice_key] = total_elements

        if offset == 0:
            logger.info(
                'Slice %s: total_elements=%d, visible_total_count=%d',
                slice_label, total_elements, visible_total_count,
            )

        if not offers:
            if offset == 0:
                logger.debug(
                    'Slice %s returned 0 offers (total_elements=%d) — skipping.',
                    slice_label, total_elements,
                )
            return

        scraped_at = datetime.now(tz=timezone.utc).isoformat()

        for offer in offers:
            if self._max_items > 0 and self._total_yielded >= self._max_items:
                logger.info(
                    'maxItems=%d reached at offset=%d for %s — stopping.',
                    self._max_items, offset, slice_label,
                )
                return

            # PT standvirtual cross-listing skip
            partner = offer.get('partner') or {}
            if partner:
                partner_url = partner.get('url') or ''
                if 'standvirtual.com' in partner_url.lower():
                    self.skipped_partner_count += 1
                    continue

            yield self._make_item(
                offer=offer,
                country=country,
                cat_l2_name=cat_l2_name,
                scraped_at=scraped_at,
            )
            self._total_yielded += 1

        # ------------------------------------------------------------------
        # Pagination: schedule next page
        # ------------------------------------------------------------------
        next_offset = offset + PAGE_LIMIT
        max_offset = min(total_elements, 1000)

        if next_offset > max_offset:
            # Pagination complete for this slice
            if visible_total_count > 1000 and offset == 0 and not base_params.get('filter_float_year:from'):
                # Only log the cap warning once, on the first page, for unfiltered slices
                logger.info(
                    'INFO: OLX API caps unfiltered results at 1,000 for slice %s. '
                    'Retrieved %d of %d visible listings. '
                    'Set maxItems > 1000 to trigger full enumeration, or use '
                    'startUrls with brand-specific URLs for targeted scraping.',
                    slice_label, min(total_elements, self._total_yielded), visible_total_count,
                )

            # Check whether this brand slice still needs sub-slicing
            # (full-enumeration mode: maxItems > 1000 and total_elements hit the cap)
            if (
                self._max_items > 1000
                and total_elements >= 1000
                and visible_total_count > 1000
                and not base_params.get('filter_float_year:from')  # don't re-slice year slices
                and not base_params.get('filter_float_price:from')  # don't re-slice price slices
            ):
                logger.info(
                    'Brand slice %s is capped (visible=%d > 1000). '
                    'Sub-slicing by year bands.',
                    slice_label, visible_total_count,
                )
                yield from self._year_band_requests(
                    domain=domain,
                    country=country,
                    category_id=category_id,
                    base_params=base_params,
                    sort_by=sort_by,
                    cat_l2_name=cat_l2_name,
                    parent_slice_label=slice_label,
                )
            return

        if self._max_items > 0 and self._total_yielded >= self._max_items:
            return

        yield from self._page_requests(
            domain=domain,
            country=country,
            category_id=category_id,
            base_params=base_params,
            sort_by=sort_by,
            offset=next_offset,
            cat_l2_name=cat_l2_name,
            slice_label=slice_label,
        )

    def _year_band_requests(
        self,
        domain: str,
        country: str,
        category_id: int,
        base_params: dict[str, Any],
        sort_by: str,
        cat_l2_name: str | None,
        parent_slice_label: str,
    ) -> Generator:
        """Yield page requests for each year band sub-slice."""
        for year_from, year_to in YEAR_BANDS:
            band_params = dict(base_params)
            if year_from is not None:
                band_params['filter_float_year:from'] = year_from
            if year_to is not None:
                band_params['filter_float_year:to'] = year_to
            label = f'{parent_slice_label}|year:{year_from}-{year_to}'
            yield from self._page_requests(
                domain=domain,
                country=country,
                category_id=category_id,
                base_params=band_params,
                sort_by=sort_by,
                offset=0,
                cat_l2_name=cat_l2_name,
                slice_label=label,
            )

    def _price_band_requests(
        self,
        domain: str,
        country: str,
        category_id: int,
        base_params: dict[str, Any],
        sort_by: str,
        cat_l2_name: str | None,
        parent_slice_label: str,
    ) -> Generator:
        """Yield page requests for each price band sub-slice (tertiary axis)."""
        for p_from, p_to in PRICE_BANDS:
            band_params = dict(base_params)
            if p_from is not None:
                band_params['filter_float_price:from'] = p_from
            if p_to is not None:
                band_params['filter_float_price:to'] = p_to
            label = f'{parent_slice_label}|price:{p_from}-{p_to}'
            yield from self._page_requests(
                domain=domain,
                country=country,
                category_id=category_id,
                base_params=band_params,
                sort_by=sort_by,
                offset=0,
                cat_l2_name=cat_l2_name,
                slice_label=label,
            )

    # ------------------------------------------------------------------
    # Item construction
    # ------------------------------------------------------------------

    def _make_item(
        self,
        offer: dict,
        country: str,
        cat_l2_name: str | None,
        scraped_at: str,
    ) -> CarItem:
        """Construct a CarItem from a raw OLX offer dict using CarItemLoader.

        Extraction strategy:
        - All param-based fields are looked up from offer['params'] using the
          per-country PARAM_KEY_MAP.  value.key is used for normalisation
          lookups (fuel, transmission, body, condition, color); value.label
          is used for free-form string fields (model) where no normalisation
          is needed.
        - make: passed in as cat_l2_name from the first-page metadata capture.
        - seller: assembled from offer['user'] and offer['contact'].
        - location: assembled from offer['location'] and offer['map'].
        - promotionFlags: mapped from offer['promotion'].
        - features: UA/KZ car_option (array of strings), BG comfort +
          multimedia + safety + other (each an array); deduplicated.
        - images: photos[].link template substituted to 800x600.
        - paramsRaw: entire params list passed through unchanged.
        """
        loader = CarItemLoader(item=CarItem())

        # ---- Build a convenient params lookup: key → value object -----------
        # params is a list of {key, value, ...} dicts.
        params: list[dict] = offer.get('params') or []
        params_by_key: dict[str, Any] = {}
        for p in params:
            k = p.get('key')
            if k:
                params_by_key[k] = p.get('value') or {}

        # Helper: get the normalised value for a conceptual field from PARAM_KEY_MAP.
        def get_param_value(field: str) -> dict | None:
            """Return the raw value dict for conceptual field name, or None."""
            key = PARAM_KEY_MAP.get(field, {}).get(country)
            if not key:
                return None
            return params_by_key.get(key) or None

        # Helper: get value.key (slug) for a param field, or None.
        def get_param_key(field: str) -> str | None:
            v = get_param_value(field)
            if v is None:
                return None
            raw = v.get('key')
            if raw is None:
                return None
            return str(raw)

        # Helper: get value.label for a param field, or None.
        def get_param_label(field: str) -> str | None:
            v = get_param_value(field)
            if v is None:
                return None
            raw = v.get('label')
            if raw is None:
                return None
            return str(raw)

        # ---- Identity fields -----------------------------------------------
        loader.add_value('offerId', offer.get('id'))
        loader.add_value('url', offer.get('url'))
        loader.add_value('country', country)
        loader.add_value('title', offer.get('title'))
        loader.add_value('scrapedAt', scraped_at)

        # ---- Description (HTML stripped by loader input processor) ---------
        loader.add_value('description', offer.get('description') or '')

        # ---- Price fields --------------------------------------------------
        price_param = params_by_key.get('price') or {}
        loader.add_value('price', price_param.get('value'))
        loader.add_value('currency', price_param.get('currency'))
        # priceNegotiable: type == "arranged" means negotiable
        price_type = price_param.get('type') or ''
        # priceNegotiable: always a computable bool — pass directly (no or '' sentinel needed).
        # pass_bool in the loader converts bool → bool unchanged.
        loader.add_value('priceNegotiable', price_type == 'arranged')
        loader.add_value('pricePrevious', price_param.get('previous_value'))
        loader.add_value('priceConverted', price_param.get('converted_value'))
        loader.add_value('priceCurrencyConverted', price_param.get('converted_currency'))

        # ---- Make / Model --------------------------------------------------
        loader.add_value('make', cat_l2_name)
        # model: value.label is localised free-form text.
        # key is always 'model' across all six countries per 01-data-points.md.
        model_val = params_by_key.get('model') or {}
        loader.add_value('model', model_val.get('label'))

        # ---- Year ----------------------------------------------------------
        year_raw = get_param_key('year') or get_param_label('year')
        loader.add_value('year', year_raw)

        # ---- Mileage (normalised to km) ------------------------------------
        mileage_key = PARAM_KEY_MAP.get('mileage', {}).get(country)
        mileage_raw = None
        if mileage_key:
            mileage_val = params_by_key.get(mileage_key) or {}
            mileage_raw = mileage_val.get('key') or mileage_val.get('label')
        if mileage_raw is not None:
            try:
                mileage_int = int(str(mileage_raw).replace(' ', '').replace('\xa0', ''))
                if country == 'ua' and mileage_key == 'motor_mileage_thou':
                    mileage_int = mileage_int * 1000
                loader.add_value('mileageKm', mileage_int)
            except (TypeError, ValueError):
                loader.add_value('mileageKm', '')
        else:
            loader.add_value('mileageKm', '')

        # ---- Fuel type (normalised enum) -----------------------------------
        fuel_raw_key = get_param_key('fuel')
        if fuel_raw_key is not None:
            fuel_norm = FUEL_NORMALIZATION.get(str(fuel_raw_key).lower(), 'other')
            loader.add_value('fuelType', fuel_norm)
        else:
            loader.add_value('fuelType', '')

        # ---- Transmission (normalised enum) --------------------------------
        trans_raw_key = get_param_key('transmission')
        if trans_raw_key is not None:
            trans_norm = TRANSMISSION_NORMALIZATION.get(str(trans_raw_key).lower(), 'other')
            loader.add_value('transmission', trans_norm)
        else:
            loader.add_value('transmission', '')

        # ---- Body type (normalised enum) -----------------------------------
        body_raw_key = get_param_key('body')
        if body_raw_key is not None:
            body_norm = BODY_NORMALIZATION.get(str(body_raw_key).lower(), 'other')
            loader.add_value('bodyType', body_norm)
        else:
            loader.add_value('bodyType', '')

        # ---- Condition (normalised enum) -----------------------------------
        # UA returns `value.key` as a LIST of flags (e.g. ["fine_condition",
        # "garage-storage", "after-an-accident"]); other countries return a
        # scalar slug. Normalise both shapes and pick the most-severe member.
        cond_val = get_param_value('condition') or {}
        cond_raw = cond_val.get('key') if isinstance(cond_val, dict) else None
        if isinstance(cond_raw, list):
            severities = [
                CONDITION_NORMALIZATION.get(str(k).lower(), 'other')
                for k in cond_raw
            ]
            known = [s for s in severities if s in CONDITION_SEVERITY]
            cond_norm = max(known, key=CONDITION_SEVERITY.get) if known else 'other'
            loader.add_value('condition', cond_norm)
        elif cond_raw is not None:
            cond_norm = CONDITION_NORMALIZATION.get(str(cond_raw).lower(), 'other')
            loader.add_value('condition', cond_norm)
        else:
            loader.add_value('condition', '')

        # ---- Engine capacity (cm³, normalised) ----------------------------
        engine_key = PARAM_KEY_MAP.get('engine_size', {}).get(country)
        engine_raw = None
        if engine_key:
            engine_val = params_by_key.get(engine_key) or {}
            engine_raw = engine_val.get('key') or engine_val.get('label')
        if engine_raw is not None:
            try:
                engine_str = str(engine_raw).replace(' ', '').replace('\xa0', '')
                if country == 'ua' and engine_key == 'motor_engine_size_litre':
                    # UA returns litres (e.g. "1.4") → convert to cm³
                    engine_cm3 = int(float(engine_str) * 1000)
                else:
                    engine_cm3 = int(float(engine_str))
                loader.add_value('engineCapacityCm3', engine_cm3)
            except (TypeError, ValueError):
                loader.add_value('engineCapacityCm3', '')
        else:
            loader.add_value('engineCapacityCm3', '')

        # ---- Engine power (HP) --------------------------------------------
        power_raw = get_param_key('power') or get_param_label('power')
        if power_raw is not None:
            try:
                loader.add_value('powerHp', int(str(power_raw).split()[0]))
            except (TypeError, ValueError, IndexError):
                loader.add_value('powerHp', '')
        else:
            loader.add_value('powerHp', '')

        # ---- Color --------------------------------------------------------
        color_raw_key = get_param_key('color')
        if color_raw_key is not None:
            color_str = str(color_raw_key)
            if country == 'ua':
                color_str = UA_COLOR_MAP.get(color_str, color_str)
            elif country == 'kz':
                color_str = KZ_COLOR_MAP.get(color_str, color_str)
            loader.add_value('color', color_str)
        else:
            loader.add_value('color', '')

        # ---- VIN -----------------------------------------------------------
        vin_raw = get_param_key('vin') or get_param_label('vin')
        loader.add_value('vin', vin_raw or '')

        # ---- License plate -------------------------------------------------
        plate_raw = get_param_key('license_plate') or get_param_label('license_plate')
        loader.add_value('licensePlate', plate_raw or '')

        # ---- Drivetrain ----------------------------------------------------
        drivetrain_raw = get_param_key('drivetrain')
        loader.add_value('drivetrain', drivetrain_raw or '')

        # ---- Steering wheel side -------------------------------------------
        sw_raw = get_param_key('steering_wheel')
        if sw_raw is not None:
            # PL uses '1' for left-hand drive
            if sw_raw == '1':
                sw_raw = 'lhd'
            loader.add_value('steeringWheelSide', sw_raw)
        else:
            loader.add_value('steeringWheelSide', '')

        # ---- Door count ----------------------------------------------------
        doors_raw = get_param_key('doors') or get_param_label('doors')
        if doors_raw is not None:
            # PT may return a range string like "4-5"; take first number
            try:
                loader.add_value('doorCount', int(str(doors_raw).split('-')[0].split()[0]))
            except (TypeError, ValueError, IndexError):
                loader.add_value('doorCount', '')
        else:
            loader.add_value('doorCount', '')

        # ---- Seat count ----------------------------------------------------
        seats_raw = get_param_key('seats') or get_param_label('seats')
        loader.add_value('seatCount', seats_raw or '')

        # ---- Registration status (RO only) ---------------------------------
        reg_raw = get_param_key('registration_status')
        loader.add_value('registrationStatus', reg_raw or '')

        # ---- Country of origin (PL/PT/BG) ----------------------------------
        origin_raw = get_param_key('country_of_origin') or get_param_label('country_of_origin')
        loader.add_value('countryOfOrigin', origin_raw or '')

        # ---- Customs cleared (UA only) -------------------------------------
        customs_raw = get_param_key('customs_cleared')
        loader.add_value('customsCleared', customs_raw or '')

        # ---- Owners count (KZ only) ----------------------------------------
        owners_raw = get_param_key('owners_count') or get_param_label('owners_count')
        loader.add_value('ownersCount', owners_raw or '')

        # ---- CO2 emissions (PT only) ----------------------------------------
        co2_raw = get_param_key('co2_emissions') or get_param_label('co2_emissions')
        loader.add_value('co2Emissions', co2_raw or '')

        # ---- Features (UA/KZ car_option; BG comfort+multimedia+safety+other) -
        features: list[str] = []
        if country in ('ua', 'kz'):
            feat_key = PARAM_KEY_MAP.get('features_ua_kz', {}).get(country)
            if feat_key:
                feat_val = params_by_key.get(feat_key) or {}
                feat_keys = feat_val.get('key')
                if isinstance(feat_keys, list):
                    features.extend(str(k) for k in feat_keys if k)
                elif feat_keys:
                    # Fallback: single value
                    features.append(str(feat_keys))
        elif country == 'bg':
            for bg_field in ('features_bg_comfort', 'features_bg_multimedia',
                             'features_bg_safety', 'features_bg_other'):
                bg_key = PARAM_KEY_MAP.get(bg_field, {}).get('bg')
                if bg_key:
                    bg_val = params_by_key.get(bg_key) or {}
                    bg_keys = bg_val.get('key')
                    if isinstance(bg_keys, list):
                        features.extend(str(k) for k in bg_keys if k)
                    elif bg_keys:
                        features.append(str(bg_keys))
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_features: list[str] = []
        for f in features:
            if f not in seen:
                seen.add(f)
                unique_features.append(f)
        loader.add_value('features', unique_features)

        # ---- Images (800x600 CDN URLs) -------------------------------------
        photos: list[dict] = offer.get('photos') or []
        images: list[str] = []
        for photo in photos:
            link = photo.get('link') or ''
            if link:
                # Template: "...;s={width}x{height}" — substitute dimensions
                url_800 = link.replace('{width}', '800').replace('{height}', '600')
                images.append(url_800)
        loader.add_value('images', images)

        # ---- paramsRaw (pass-through) ---------------------------------------
        loader.add_value('paramsRaw', params)

        # ---- Promotion flags -----------------------------------------------
        promo = offer.get('promotion') or {}
        if promo:
            promo_dict = {
                'highlighted': bool(promo.get('highlighted', False)),
                'topAd': bool(promo.get('top_ad', False)),
                'urgent': bool(promo.get('urgent', False)),
            }
            loader.add_value('promotionFlags', promo_dict)
        else:
            loader.add_value('promotionFlags', '')

        # ---- Timestamps ----------------------------------------------------
        loader.add_value('postedAt', offer.get('created_time') or '')
        loader.add_value('refreshedAt', offer.get('last_refresh_time') or '')
        loader.add_value('validTo', offer.get('valid_to_time') or '')

        # ---- Seller sub-object --------------------------------------------
        user: dict = offer.get('user') or {}
        contact: dict = offer.get('contact') or {}
        seller_dict: dict = {
            'id': user.get('id'),
            'uuid': user.get('uuid'),
            'name': user.get('name'),
            'companyName': user.get('company_name'),
            'type': 'dealer' if offer.get('business') else 'private',
            'memberSince': user.get('created'),
            'hasPhone': bool(contact.get('phone', False)),
            'hasChat': bool(contact.get('chat', False)),
        }
        loader.add_value('seller', seller_dict)

        # ---- Location sub-object ------------------------------------------
        loc: dict = offer.get('location') or {}
        map_data: dict = offer.get('map') or {}
        city_obj: dict = loc.get('city') or {}
        region_obj: dict = loc.get('region') or {}
        district_obj: dict = loc.get('district') or {}
        show_detailed = map_data.get('show_detailed')
        location_dict: dict = {
            'city': city_obj.get('name'),
            'region': region_obj.get('name'),
            'district': district_obj.get('name') if district_obj else None,
            'latitude': map_data.get('lat'),
            'longitude': map_data.get('lon'),
            'gpsObfuscated': not bool(show_detailed) if show_detailed is not None else True,
        }
        loader.add_value('location', location_dict)

        # ---- Post-load defaults for mandatory list fields ------------------
        item = loader.load_item()

        # Ensure array fields are always lists (never None or absent)
        if item.get('features') is None:
            item['features'] = []
        if item.get('images') is None:
            item['images'] = []
        if item.get('paramsRaw') is None:
            item['paramsRaw'] = []

        return item

    # ------------------------------------------------------------------
    # Error callback
    # ------------------------------------------------------------------

    def errback_fatal(self, failure) -> None:
        """Handle network-level errors on any API request.

        Sets crawl_failed on the class so main.py can call Actor.fail().
        """
        logger.error(
            'Fatal request error (all retries exhausted): %s', failure
        )
        type(self).crawl_failed = True

    # ------------------------------------------------------------------
    # Spider closed hook
    # ------------------------------------------------------------------

    def closed(self, reason: str) -> None:
        """Log summary statistics when the spider closes."""
        logger.info(
            'OlxCarsSpider closed (reason=%s). Total yielded: %d.',
            reason, self._total_yielded,
        )

        if self.skipped_partner_count > 0:
            logger.info(
                'Skipped %d offers on olx.pt that link to standvirtual.com '
                '(a sister site not covered by this actor).',
                self.skipped_partner_count,
            )

        # Check for cap warnings across all slices
        for slice_label, total_el in self._total_elements_by_cat.items():
            if total_el >= 1000:
                logger.info(
                    'INFO: Slice %s was capped by the OLX API 1000-result limit. '
                    'Some listings may not have been retrieved.',
                    slice_label,
                )
