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

from datetime import datetime, timezone

from apify import Actor
from apify.scrapy import apply_apify_settings
from scrapy.crawler import CrawlerRunner
from scrapy.utils.defer import deferred_to_future

from .pipelines import IncrementalDiffPipeline, _drop_nones
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

        # --- Incremental mode setup ---
        incremental_mode = bool(actor_input.get('incrementalMode', False))
        state_key_raw = actor_input.get('stateKey') or 'olx-cars-state'
        state_key = str(state_key_raw).strip() or 'olx-cars-state'
        emit_missing = bool(actor_input.get('emitMissing', False))
        run_ts = datetime.now(tz=timezone.utc).isoformat()

        snapshot: dict = {}
        kv_store = None
        if incremental_mode:
            from .state import INCREMENTAL_STORE_NAME, load_snapshot
            # IMPORTANT: open a NAMED key-value store. Without `name=...`,
            # Actor.open_key_value_store() returns the per-run default store,
            # which is unique to each run — state would never persist across
            # runs. The named store is created on first use and persists for
            # the actor's lifetime.
            kv_store = await Actor.open_key_value_store(name=INCREMENTAL_STORE_NAME)
            snapshot = await load_snapshot(kv_store, state_key)
            Actor.log.info(
                'Incremental mode: loaded %d entries from state key %r '
                '(named store %r).',
                len(snapshot), state_key, INCREMENTAL_STORE_NAME,
            )

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
                # --- Incremental mode fields ---
                'incrementalMode': incremental_mode,
                'stateKey': state_key,
                'emitUnchanged': bool(actor_input.get('emitUnchanged', False)),
                'emitMissing': emit_missing,
                '_snapshot': snapshot,
                '_runTs': run_ts,
            },
            priority='spider',
        )

        # --- Reset class-level flags before each run ---
        # (prevents false positives if Actor is somehow re-run in the same process)
        OlxCarsSpider.crawl_failed = False
        IncrementalDiffPipeline.updated_snapshot = {}
        IncrementalDiffPipeline.seen_offer_ids = set()
        IncrementalDiffPipeline.was_truncated = False

        # --- Run the spider ---
        crawler_runner = CrawlerRunner(settings)
        crawl_deferred = crawler_runner.crawl(OlxCarsSpider)
        await deferred_to_future(crawl_deferred)

        # --- Post-crawl: incremental state save + MISSING emission ---
        if incremental_mode and kv_store is not None:
            from .state import compute_missing, save_snapshot

            updated_snapshot = IncrementalDiffPipeline.updated_snapshot
            seen_offer_ids = IncrementalDiffPipeline.seen_offer_ids
            was_truncated = IncrementalDiffPipeline.was_truncated

            # Compute and emit MISSING items (mutates updated_snapshot _missingCount)
            missing_items = compute_missing(
                snapshot=updated_snapshot,
                seen_ids=seen_offer_ids,
                emit_missing=emit_missing,
                run_ts=run_ts,
                was_truncated=was_truncated,
            )
            if missing_items:
                dataset = await Actor.open_dataset()
                for missing_item in missing_items:
                    # MISSING items bypass Scrapy pipelines — strip Nones manually
                    # here, otherwise Apify schema-validates and rejects.
                    missing_item['isRepost'] = False
                    await dataset.push_data(_drop_nones(missing_item))
                Actor.log.info(
                    'Incremental mode: emitted %d MISSING items.', len(missing_items)
                )

            # Save updated snapshot back to KV
            await save_snapshot(kv_store, state_key, updated_snapshot)

            # Log baseline-build-run notice when this was the first run
            if len(snapshot) == 0:
                Actor.log.info(
                    'Incremental mode: baseline built — %d listings stored in '
                    'state key %r. Next run will emit changes.',
                    len(updated_snapshot), state_key,
                )

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
