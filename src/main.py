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

import sys
from datetime import datetime, timezone

from apify import Actor
from apify.scrapy import apply_apify_settings
from scrapy.crawler import CrawlerRunner
from scrapy.utils.defer import deferred_to_future

import statistics

from .pipelines import FairPricePipeline, HistoryFilterPipeline, IncrementalDiffPipeline, NotificationBufferPipeline, _drop_nones, shape_output
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

        # --- Notification input validation (#29) ---
        valid_notify_on = {'none', 'new_listings', 'price_drops', 'both'}
        notify_on_raw = actor_input.get('notifyOn', 'none')
        notify_on = str(notify_on_raw).lower() if notify_on_raw else 'none'
        if notify_on not in valid_notify_on:
            Actor.log.warning(
                'Invalid notifyOn %r — defaulting to "none".', notify_on_raw,
            )
            notify_on = 'none'

        if notify_on != 'none' and not incremental_mode:
            await Actor.fail(
                status_message=(
                    'notifyOn requires incrementalMode: true. '
                    'Enable Incremental Mode or set notifyOn to "none".'
                )
            )
            # In Scrapy-based actors, apify SDK detects Scrapy and disables
            # sys.exit() in its __aexit__ (see apify/_actor.py:_get_default_exit_process).
            # `Actor.fail()` then only sets statusMessage; the container still
            # exits with code 0 and Apify reports SUCCEEDED. To actually surface
            # this misconfiguration as FAILED, we sys.exit(1) here. Safe at this
            # point — no Twisted reactor running yet (this is a pre-crawl check).
            sys.exit(1)

        notify_min_pct_raw = actor_input.get('notifyMinPriceDropPct', 5)
        try:
            notify_min_price_drop_pct = int(notify_min_pct_raw)
            if not (1 <= notify_min_price_drop_pct <= 99):
                Actor.log.warning(
                    'notifyMinPriceDropPct %r out of range [1,99] — clamping.',
                    notify_min_pct_raw,
                )
                notify_min_price_drop_pct = max(1, min(99, notify_min_price_drop_pct))
        except (TypeError, ValueError):
            Actor.log.warning(
                'Invalid notifyMinPriceDropPct %r — defaulting to 5.', notify_min_pct_raw,
            )
            notify_min_price_drop_pct = 5

        notify_top_n_raw = actor_input.get('notifyTopN', 20)
        try:
            notify_top_n = int(notify_top_n_raw)
            if not (1 <= notify_top_n <= 200):
                Actor.log.warning(
                    'notifyTopN %r out of range [1,200] — clamping.', notify_top_n_raw,
                )
                notify_top_n = max(1, min(200, notify_top_n))
        except (TypeError, ValueError):
            Actor.log.warning(
                'Invalid notifyTopN %r — defaulting to 20.', notify_top_n_raw,
            )
            notify_top_n = 20

        notify_webhook_url_raw = actor_input.get('notifyWebhookUrl', '') or ''
        notify_webhook_url = str(notify_webhook_url_raw).strip()
        if notify_webhook_url and not notify_webhook_url.startswith(('http://', 'https://')):
            Actor.log.warning(
                'notifyWebhookUrl %r is not a valid http(s) URL — disabling outbound POST.',
                notify_webhook_url,
            )
            notify_webhook_url = ''

        # --- VIN enrichment flag (#19) ---
        # The cache (named KV store `olx-cars-vin-cache`) is opened lazily by
        # the spider on first use. We CANNOT open it here and pass the store
        # object via INPUT_DATA: Scrapy's CrawlerRunner deep-copies settings,
        # and the Apify SDK KV-store client wraps a builtins.Client that is
        # not picklable (`TypeError: cannot pickle 'builtins.Client' object`).
        # Lazy-open inside the async spider sidesteps the deepcopy entirely.
        enrich_vin = bool(actor_input.get('enrichVIN', False))

        # --- Advanced slicing fields (#16) ---
        page_limit_raw = actor_input.get('pageLimit', 50)
        try:
            page_limit = int(page_limit_raw)
            if not (1 <= page_limit <= 50):
                Actor.log.warning(
                    'pageLimit %r out of range [1,50] — clamping.', page_limit_raw,
                )
                page_limit = max(1, min(50, page_limit))
        except (TypeError, ValueError):
            Actor.log.warning(
                'Invalid pageLimit %r — defaulting to 50.', page_limit_raw,
            )
            page_limit = 50

        slice_year_step_raw = actor_input.get('sliceYearStep', 5)
        try:
            slice_year_step = int(slice_year_step_raw)
            if not (1 <= slice_year_step <= 50):
                Actor.log.warning(
                    'sliceYearStep %r out of range [1,50] — clamping.', slice_year_step_raw,
                )
                slice_year_step = max(1, min(50, slice_year_step))
        except (TypeError, ValueError):
            Actor.log.warning(
                'Invalid sliceYearStep %r — defaulting to 5.', slice_year_step_raw,
            )
            slice_year_step = 5

        slice_price_step_raw = actor_input.get('slicePriceStep', 5000)
        try:
            slice_price_step = int(slice_price_step_raw)
            if not (1000 <= slice_price_step <= 500000):
                Actor.log.warning(
                    'slicePriceStep %r out of range [1000,500000] — clamping.', slice_price_step_raw,
                )
                slice_price_step = max(1000, min(500000, slice_price_step))
        except (TypeError, ValueError):
            Actor.log.warning(
                'Invalid slicePriceStep %r — defaulting to 5000.', slice_price_step_raw,
            )
            slice_price_step = 5000

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
                'sellerType': actor_input.get('sellerType', 'any'),
                'sortBy': sort_by,
                'maxItems': max_items,
                # --- History filter fields (#23, #51) ---
                'excludeDamaged': bool(actor_input.get('excludeDamaged', False)),
                'firstOwnerOnly': bool(actor_input.get('firstOwnerOnly', False)),
                'serviceBookOnly': bool(actor_input.get('serviceBookOnly', False)),
                # --- Incremental mode fields ---
                'incrementalMode': incremental_mode,
                'stateKey': state_key,
                'emitUnchanged': bool(actor_input.get('emitUnchanged', False)),
                'emitMissing': emit_missing,
                '_snapshot': snapshot,
                '_runTs': run_ts,
                # --- Notification fields (#29) ---
                'notifyOn': notify_on,
                'notifyMinPriceDropPct': notify_min_price_drop_pct,
                'notifyTopN': notify_top_n,
                'notifyWebhookUrl': notify_webhook_url,
                # --- Output shaping fields (#24) ---
                'outputMode': actor_input.get('outputMode', 'full') or 'full',
                'descriptionMaxLength': actor_input.get('descriptionMaxLength'),
                # --- VIN enrichment fields (#19) ---
                'enrichVIN': enrich_vin,
                # --- Currency post-filter (#14) ---
                'filterByCurrency': bool(actor_input.get('filterByCurrency', False)),
                # --- Advanced slicing fields (#16) ---
                'pageLimit': page_limit,
                'sliceYearStep': slice_year_step,
                'slicePriceStep': slice_price_step,
            },
            priority='spider',
        )

        # --- Reset class-level flags before each run ---
        # (prevents false positives if Actor is somehow re-run in the same process)
        OlxCarsSpider.crawl_failed = False
        OlxCarsSpider._vpic_success_count = 0
        OlxCarsSpider._vpic_error_count = 0
        HistoryFilterPipeline.reset()
        IncrementalDiffPipeline.updated_snapshot = {}
        IncrementalDiffPipeline.seen_offer_ids = set()
        IncrementalDiffPipeline.was_truncated = False
        FairPricePipeline.items_buffer = []
        FairPricePipeline.keys_buffer = []
        NotificationBufferPipeline.new_items_buffer = []
        NotificationBufferPipeline.price_drop_buffer = []
        NotificationBufferPipeline._counts = {}

        # --- Run the spider ---
        crawler_runner = CrawlerRunner(settings)
        crawl_deferred = crawler_runner.crawl(OlxCarsSpider)
        await deferred_to_future(crawl_deferred)

        # --- Post-crawl: read output-shaping params once for both push blocks ---
        _output_mode: str = str(actor_input.get('outputMode', 'full') or 'full')
        if _output_mode not in ('full', 'compact'):
            _output_mode = 'full'
        _desc_max_len = actor_input.get('descriptionMaxLength')
        if _desc_max_len is not None:
            try:
                _desc_max_len = int(_desc_max_len)
            except (TypeError, ValueError):
                _desc_max_len = None

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
                    shaped = shape_output(_drop_nones(missing_item), _output_mode, _desc_max_len)
                    await dataset.push_data(shaped)
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

        # --- Post-crawl: fair-price median enrichment + push (#18) ---
        # FairPricePipeline buffered all items (dropped them from the Apify push
        # pipeline at priority 1000). We now compute per-bucket medians and push
        # each enriched item directly. Items whose bucket has < min_bucket_size
        # entries receive no priceVsMedianPct / priceRating (fields simply absent).
        buffered_items = FairPricePipeline.items_buffer
        buffered_keys = FairPricePipeline.keys_buffer

        if buffered_items:
            # Collect prices per bucket
            buckets: dict = {}
            for item, key in zip(buffered_items, buffered_keys):
                if key is not None and item.get('price') is not None:
                    try:
                        buckets.setdefault(key, []).append(float(item['price']))
                    except (TypeError, ValueError):
                        pass

            medians: dict = {
                k: statistics.median(prices)
                for k, prices in buckets.items()
                if len(prices) >= FairPricePipeline.min_bucket_size
            }

            dataset = await Actor.open_dataset()
            push_failed = False
            enriched_count = 0
            for item, key in zip(buffered_items, buffered_keys):
                if key is not None and key in medians:
                    median = medians[key]
                    try:
                        price_f = float(item['price'])
                        pct = round((price_f - median) / median * 100.0, 2)
                        item['priceVsMedianPct'] = pct
                        item['priceRating'] = FairPricePipeline._pct_to_rating(pct)
                        enriched_count += 1
                    except (TypeError, ValueError, ZeroDivisionError):
                        # Numeric corruption; leave the fields absent
                        pass
                try:
                    await dataset.push_data(shape_output(item, _output_mode, _desc_max_len))
                except Exception as exc:
                    push_failed = True
                    Actor.log.error(
                        'FairPricePipeline push failed for offerId=%s: %s',
                        item.get('offerId'), exc,
                    )

            if push_failed:
                # Surface via class attribute pattern (consistent with
                # FailOnItemErrorExtension and existing failure path)
                OlxCarsSpider.crawl_failed = True

            Actor.log.info(
                'FairPricePipeline: pushed %d items, %d buckets >= %d, '
                '%d items enriched with fair-price fields.',
                len(buffered_items),
                len(medians),
                FairPricePipeline.min_bucket_size,
                enriched_count,
            )

        # --- Post-crawl: notification digest emit (#29) ---
        if notify_on != 'none':
            import asyncio
            import json as _json
            import os as _os
            import urllib.error
            import urllib.request

            run_finished_at = datetime.now(tz=timezone.utc).isoformat()
            run_id = _os.environ.get('ACTOR_RUN_ID') or _os.environ.get('APIFY_ACTOR_RUN_ID') or 'local'
            actor_id = _os.environ.get('ACTOR_ID') or _os.environ.get('APIFY_ACTOR_ID') or 'local'

            counts_raw = dict(NotificationBufferPipeline._counts)
            counts = {
                'new': counts_raw.get('NEW', 0),
                'updated': counts_raw.get('UPDATED', 0),
                'unchanged': counts_raw.get('UNCHANGED', 0),
                'missing': counts_raw.get('MISSING', 0),
                'reappeared': counts_raw.get('REAPPEARED', 0),
                'total': counts_raw.get('total', 0),
                'priceDropsQualified': len(NotificationBufferPipeline.price_drop_buffer),
            }

            # Top-N new items by firstSeenAt desc (None sorts last)
            def _new_sort_key(d: dict) -> str:
                return d.get('firstSeenAt') or ''
            new_items = sorted(
                NotificationBufferPipeline.new_items_buffer,
                key=_new_sort_key,
                reverse=True,
            )[:notify_top_n]

            # Top-N price drops by priceDropPct desc
            price_drops = sorted(
                NotificationBufferPipeline.price_drop_buffer,
                key=lambda d: d.get('priceDropPct') or 0,
                reverse=True,
            )[:notify_top_n]

            # Filters echo
            filters_echo = {
                'yearFrom': actor_input.get('yearFrom'),
                'yearTo': actor_input.get('yearTo'),
                'priceFrom': actor_input.get('priceFrom'),
                'priceTo': actor_input.get('priceTo'),
                'priceCurrency': actor_input.get('priceCurrency', 'EUR'),
            }

            # Cold-start indicator: snapshot was empty at the start of this run
            is_cold_start = incremental_mode and len(snapshot) == 0
            if is_cold_start:
                seeded_count = len(IncrementalDiffPipeline.updated_snapshot)
                summary_text = (
                    f'OLX Cars baseline run ({country}, notifyOn={notify_on}): '
                    f'0 changes emitted (snapshot seeded with '
                    f'{seeded_count} listings). '
                    f'Next run will detect changes.'
                )
            else:
                bits = []
                if notify_on in ('new_listings', 'both'):
                    bits.append(f'{counts["new"]} new')
                if notify_on in ('price_drops', 'both'):
                    n_drops = counts['priceDropsQualified']
                    bits.append(
                        f'{n_drops} price drop'
                        f'{"s" if n_drops != 1 else ""} '
                        f'(>={notify_min_price_drop_pct}%)'
                    )
                summary_text = (
                    f'OLX Cars run ({country}, notifyOn={notify_on}): '
                    f'{", ".join(bits) or "no qualifying changes"}.'
                )
            # Cap at 280 chars (Telegram single-message limit)
            if len(summary_text) > 280:
                summary_text = summary_text[:277] + '...'

            digest = {
                'runId': run_id,
                'actorId': actor_id,
                'runStartedAt': run_ts,
                'runFinishedAt': run_finished_at,
                'notifyOn': notify_on,
                'country': country,
                'query': actor_input.get('query'),
                'brands': brands_raw,
                'startUrlsCount': len(start_urls_raw),
                'filters': filters_echo,
                'counts': counts,
                'newItems': new_items,
                'priceDrops': price_drops,
                'summaryText': summary_text,
            }

            # Write to named KV store (separate from incremental-state store)
            try:
                notif_store = await Actor.open_key_value_store(name='olx-cars-notifications')
                await notif_store.set_value('digest-latest', digest)
                await notif_store.set_value(f'digest-{run_id}', digest)
                Actor.log.info(
                    'NotificationDigest: emitted to KV store '
                    '"olx-cars-notifications" (runId=%s), new=%d, priceDrops=%d',
                    run_id, counts['new'], counts['priceDropsQualified'],
                )
            except Exception as exc:
                Actor.log.error(
                    'NotificationDigest: KV write failed: %s', exc,
                )
                # KV write failure IS fatal — if we can't persist the digest,
                # the user's notification pipeline is silently broken.
                OlxCarsSpider.crawl_failed = True

            # Optional outbound HTTP POST (non-fatal on failure)
            if notify_webhook_url:
                def _post_digest():
                    body = _json.dumps(digest).encode('utf-8')
                    req = urllib.request.Request(
                        notify_webhook_url,
                        data=body,
                        method='POST',
                        headers={'Content-Type': 'application/json'},
                    )
                    with urllib.request.urlopen(req, timeout=10) as r:
                        return r.status

                try:
                    status = await asyncio.get_event_loop().run_in_executor(
                        None, _post_digest,
                    )
                    Actor.log.info(
                        'NotificationDigest: webhook POST to %s -> HTTP %d',
                        notify_webhook_url, status,
                    )
                except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError) as exc:
                    Actor.log.warning(
                        'NotificationDigest: webhook POST to %s failed: %s '
                        '(non-fatal, dataset is unaffected)',
                        notify_webhook_url, exc,
                    )

        # --- Post-crawl: VIN enrichment summary (#19) ---
        if enrich_vin:
            Actor.log.info(
                'VIN enrichment summary: %d succeeded, %d failed '
                '(failed items emitted without vinDecoded — non-fatal).',
                OlxCarsSpider._vpic_success_count,
                OlxCarsSpider._vpic_error_count,
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
