"""Apify Actor entrypoint for OLX Cars scraper.

Reads Actor input, validates it, passes it to OlxCarsSpider via the
INPUT_DATA Scrapy setting, and checks the class-level crawl_failed flag
after the crawl completes to propagate fatal errors to Apify.

CRITICAL — crawl_failed pattern:
    After the crawl, we check OlxCarsSpider.crawl_failed as a CLASS
    attribute (not an instance attribute via getattr).
    CrawlerRunner.crawl() returns a Deferred that resolves to None, NOT
    the spider instance — so instance attribute access always evaluates
    to False.  The class attribute persists after the crawl and is safe
    to read from main.py.

    Reference: MEMORY.md "Apify silent-failure pattern + class-attribute fix"
"""

from __future__ import annotations

from apify import Actor
from apify.scrapy import apply_apify_settings
from scrapy.crawler import CrawlerRunner
from scrapy.utils.defer import deferred_to_future

from .spiders.olx_cars import OlxCarsSpider


async def main() -> None:
    """Apify Actor main coroutine."""
    async with Actor:
        actor_input = await Actor.get_input() or {}

        # --- Validate and normalise country ---
        country_raw = actor_input.get('country', 'ro')
        country = str(country_raw).lower() if country_raw else 'ro'
        valid_countries = {'ro', 'pl', 'bg', 'pt', 'ua', 'kz'}
        if country not in valid_countries:
            Actor.log.warning(
                'Invalid country value %r — defaulting to "ro". '
                'Valid values: ro, pl, bg, pt, ua, kz.',
                country,
            )
            country = 'ro'

        # --- Validate maxItems ---
        max_items_raw = actor_input.get('maxItems', 1000)
        try:
            max_items = int(max_items_raw)
            if max_items < 1:
                Actor.log.warning(
                    'maxItems must be >= 1; got %r — defaulting to 1000.',
                    max_items_raw,
                )
                max_items = 1000
        except (ValueError, TypeError):
            Actor.log.warning(
                'Invalid maxItems value %r — defaulting to 1000.',
                max_items_raw,
            )
            max_items = 1000

        # --- Validate sortBy ---
        valid_sort_by = {
            'created_at:desc',
            'filter_float_price:asc',
            'filter_float_price:desc',
            'relevance',
        }
        sort_by_raw = actor_input.get('sortBy', 'created_at:desc')
        sort_by = str(sort_by_raw) if sort_by_raw else 'created_at:desc'
        if sort_by not in valid_sort_by:
            Actor.log.warning(
                'Invalid sortBy value %r — defaulting to "created_at:desc".',
                sort_by_raw,
            )
            sort_by = 'created_at:desc'

        # --- Log parsed input ---
        start_urls_raw = actor_input.get('startUrls') or []
        brands_raw = actor_input.get('brands') or []
        Actor.log.info(
            'Actor input: country=%s maxItems=%d sortBy=%s startUrls=%d brands=%d',
            country, max_items, sort_by,
            len(start_urls_raw), len(brands_raw),
        )

        # --- Build Scrapy settings ---
        settings = apply_apify_settings()

        # Pass all actor input to the spider via the INPUT_DATA setting.
        # The spider reads self.settings.get('INPUT_DATA') in start_requests().
        # This avoids passing kwargs through CrawlerRunner.crawl() which does
        # not easily forward keyword arguments to the spider __init__.
        settings.set(
            'INPUT_DATA',
            {
                'startUrls': start_urls_raw,
                'country': country,
                'brands': brands_raw,
                'query': actor_input.get('query'),
                'yearFrom': actor_input.get('yearFrom'),
                'yearTo': actor_input.get('yearTo'),
                'priceFrom': actor_input.get('priceFrom'),
                'priceTo': actor_input.get('priceTo'),
                'priceCurrency': actor_input.get('priceCurrency', 'EUR'),
                'sortBy': sort_by,
                'maxItems': max_items,
            },
            priority='spider',
        )

        # --- Reset class-level flag before each run ---
        # (prevents false positives if Actor is somehow re-run in the same process)
        OlxCarsSpider.crawl_failed = False

        # --- Run the spider ---
        crawler_runner = CrawlerRunner(settings)
        crawl_deferred = crawler_runner.crawl(OlxCarsSpider)
        await deferred_to_future(crawl_deferred)

        # --- Check for fatal errors ---
        # CRITICAL: access OlxCarsSpider.crawl_failed as a CLASS attribute.
        # Do NOT use getattr(spider_instance, 'crawl_failed', False) because
        # CrawlerRunner.crawl() returns None, not the spider instance.
        if OlxCarsSpider.crawl_failed:
            await Actor.fail(
                status_message=(
                    'OLX Cars spider reported a fatal error. '
                    'Please check the actor logs for details.'
                )
            )
