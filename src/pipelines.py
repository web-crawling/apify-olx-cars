"""Item pipelines for OLX Cars actor.

Pipelines:
  MaxItemsPipeline — enforces the maxItems ceiling at process_item time.
    Raises CloseSpider when the limit is reached, which signals Scrapy to
    shut down cleanly and lets Apify report SUCCEEDED with the items collected.

  HistoryFilterPipeline — client-side post-filter implementing three filter
    checks: excludeDamaged, firstOwnerOnly, and serviceBookOnly. Runs at
    priority 150 (after MaxItemsPipeline at 100, before IncrementalDiffPipeline
    at 200). Raises DropItem for filtered listings so they never enter the
    incremental snapshot. On countries where a filter has no API signal, emits
    a one-time INFO log per (filter, country) pair.

  IncrementalDiffPipeline — diffs each item against the KV snapshot loaded
    by main.py, attaches changeType/firstSeenAt/lastSeenAt, deduplicates
    by offerId within a run, and drops UNCHANGED items when emitUnchanged
    is False. Pass-through when incrementalMode: false.

  NotificationBufferPipeline — observational pipeline (priority 250) that
    collects compact summaries of NEW items and qualifying price-drop UPDATED
    items into class-attribute buffers for the post-crawl digest builder in
    main.py. Near-zero overhead when notifyOn='none'. Never raises DropItem
    — items continue through DropNonesPipeline, FairPricePipeline, and the
    Apify push pipeline unchanged. See issue #29.

  DropNonesPipeline — recursively removes None values from items before
    they reach the Apify dataset push pipeline. Apify's dataset schema
    rejects null for typed fields (Draft7 default behavior), so items
    with country-specific fields (e.g. district=None for PT/RO/BG/KZ)
    must be cleaned before push. See issue #33 for the failing run that
    motivated this pipeline.

  OutputShapingPipeline — applies outputMode and descriptionMaxLength
    transforms at priority 700. When outputMode='compact', retains only the
    18-field COMPACT_FIELDS slice. When descriptionMaxLength is set, truncates
    the description field to that many characters (0 drops it entirely). In
    practice, FairPricePipeline at 600 drops all items before this fires;
    the real work happens in main.py's post-crawl push blocks via shape_output().
    See issue #24.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from itemadapter import ItemAdapter
from scrapy.exceptions import CloseSpider, DropItem

logger = logging.getLogger(__name__)


class MaxItemsPipeline:
    """Pipeline that enforces the maxItems ceiling.

    Reads ``INPUT_DATA['maxItems']`` from the Scrapy settings (set by
    main.py) and raises CloseSpider when the count is reached.

    Item count is tracked at the pipeline level (not the spider level) to
    ensure it is accurate even when multiple spiders run in the same engine
    (which Apify does not do in practice, but is defensive coding).
    """

    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        input_data = crawler.settings.get('INPUT_DATA') or {}
        max_items_raw = input_data.get('maxItems', 1000)
        try:
            obj.max_items: int = int(max_items_raw)
        except (ValueError, TypeError):
            obj.max_items = 1000
        obj._count: int = 0
        logger.info('MaxItemsPipeline: max_items=%d', obj.max_items)
        return obj

    def open_spider(self) -> None:
        pass

    def process_item(self, item):
        """Pass item through or raise CloseSpider when limit is hit."""
        self._count += 1
        if self._count > self.max_items:
            raise CloseSpider(
                f'maxItems={self.max_items} reached — stopping spider.'
            )
        return item


class HistoryFilterPipeline:
    """Client-side post-filter for excludeDamaged, firstOwnerOnly, and serviceBookOnly inputs.

    Pipeline priority: 150 — after MaxItemsPipeline (100), before
    IncrementalDiffPipeline (200). Filtered items are DropItem'd so they
    never enter the incremental snapshot, never reach FairPrice/DropNones/Apify.

    On countries where a filter has no OLX API signal, the filter is a no-op
    and a single INFO log is emitted per (filter_name, country) pair per run.
    The log is gated by a class-level set so it fires exactly once — not once
    per item (which would flood the log at maxItems=1000).

    Per-country support:
      excludeDamaged: ro, pl, pt, ua, kz — uses normalised item['condition']
      firstOwnerOnly: bg, ua, kz — uses conditionRaw (bg/ua) or ownersCount (kz)
      serviceBookOnly: bg — uses conditionRaw (exact 'service-book' slug match)
      BG is excluded from excludeDamaged (no damage flag in BG condition enum).
      RO/PL/PT/UA/KZ are excluded from serviceBookOnly (no service-book slug
      observed in the params[] enum across the 10-offer probe sample).
    """

    # Per-filter supported country sets (client-side signal confirmed)
    _DAMAGED_COUNTRIES: frozenset = frozenset({'ro', 'pl', 'pt', 'ua', 'kz'})
    _FIRST_OWNER_COUNTRIES: frozenset = frozenset({'bg', 'ua', 'kz'})
    _SERVICE_BOOK_COUNTRIES: frozenset = frozenset({'bg'})

    # Class-level set of (filter_name, country) cells already logged as inapplicable.
    # Class attribute (not instance) so main.py can reset it before each run.
    _logged_inapplicable: set = set()

    @classmethod
    def reset(cls) -> None:
        """Reset per-run class-level state. Called from open_spider and main.py."""
        cls._logged_inapplicable = set()

    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        obj.reset()
        input_data = crawler.settings.get('INPUT_DATA') or {}
        obj._exclude_damaged: bool = bool(input_data.get('excludeDamaged', False))
        obj._first_owner_only: bool = bool(input_data.get('firstOwnerOnly', False))
        obj._service_book_only: bool = bool(input_data.get('serviceBookOnly', False))
        if obj._exclude_damaged or obj._first_owner_only or obj._service_book_only:
            logger.info(
                'HistoryFilterPipeline: excludeDamaged=%s firstOwnerOnly=%s serviceBookOnly=%s',
                obj._exclude_damaged, obj._first_owner_only, obj._service_book_only,
            )
        return obj

    def open_spider(self) -> None:
        pass

    def process_item(self, item):
        if not (self._exclude_damaged or self._first_owner_only or self._service_book_only):
            return item

        d = item if isinstance(item, dict) else ItemAdapter(item).asdict()
        country = str(d.get('country') or '').lower()

        # --- excludeDamaged ---------------------------------------------------
        if self._exclude_damaged:
            if country in self._DAMAGED_COUNTRIES:
                if self._is_damaged(d):
                    raise DropItem(f'HistoryFilter: excludeDamaged — offerId {d.get("offerId")}')
            else:
                self._log_once('excludeDamaged', country)

        # --- firstOwnerOnly ---------------------------------------------------
        if self._first_owner_only:
            if country in self._FIRST_OWNER_COUNTRIES:
                if not self._is_first_owner(d, country):
                    raise DropItem(f'HistoryFilter: firstOwnerOnly — offerId {d.get("offerId")}')
            else:
                self._log_once('firstOwnerOnly', country)

        # --- serviceBookOnly --------------------------------------------------
        if self._service_book_only:
            if country in self._SERVICE_BOOK_COUNTRIES:
                if not self._has_service_book(d):
                    raise DropItem(f'HistoryFilter: serviceBookOnly — offerId {d.get("offerId")}')
            else:
                self._log_once('serviceBookOnly', country)

        return item

    @staticmethod
    def _is_damaged(d: dict) -> bool:
        """Return True when the listing is flagged as damaged (normalised condition)."""
        return d.get('condition') == 'damaged'

    @staticmethod
    def _is_first_owner(d: dict, country: str) -> bool:
        """Return True when the listing is a first-owner vehicle.

        KZ: ownersCount == 1 (int or str coerced).
        BG/UA: conditionRaw contains 'first-owner'. conditionRaw is always a
        str (never list) — UA multi-element arrays are ';'-joined by the spider
        before the item is emitted (e.g. "first-owner;after-accident").
        Missing conditionRaw: condition unknown — pass through (false negative
        preferred over false positive drop). See risk R2 in architecture doc.
        """
        if country == 'kz':
            try:
                return int(d.get('ownersCount') or 0) == 1
            except (TypeError, ValueError):
                return False

        # BG/UA — conditionRaw is always a str; UA slugs are ';'-separated
        cr = d.get('conditionRaw')
        if cr is None:
            # No condition data: unknown — pass through rather than false-positive drop
            return True
        if not isinstance(cr, str):
            # Defensive — should not happen with current spider; pass through (True)
            # to match the cr-is-None branch (prefer false-negative-keep over false-positive-drop)
            return True
        # Split on ';' to handle UA joined arrays; non-UA values won't contain ';'
        parts = {p.strip() for p in cr.split(';')}
        return 'first-owner' in parts

    @staticmethod
    def _has_service_book(d: dict) -> bool:
        """Return True when the BG listing's conditionRaw contains 'service-book'.

        BG only — caller must have already gated on country == 'bg'.
        conditionRaw is always a str at this point (spider emits scalar BG
        values directly; UA arrays are ';'-joined but UA is not in
        _SERVICE_BOOK_COUNTRIES so this method never sees a joined UA string).
        Missing conditionRaw: pass through (false-negative-keep over
        false-positive-drop). Match is exact-slug, not substring — prevents
        spurious matches on hypothetical compound keys like 'with-service-book'.
        """
        cr = d.get('conditionRaw')
        if cr is None:
            return True  # unknown → pass through
        if not isinstance(cr, str):
            return True  # defensive — should not happen
        parts = {p.strip() for p in cr.split(';')}
        return 'service-book' in parts

    @classmethod
    def _log_once(cls, filter_name: str, country: str) -> None:
        """Emit a one-time INFO log for an inapplicable (filter, country) cell."""
        key = (filter_name, country)
        if key in cls._logged_inapplicable:
            return
        cls._logged_inapplicable.add(key)
        logger.info(
            "HistoryFilter: filter %r is not available on country %r "
            "(no OLX API signal). Items pass through unchanged for this country.",
            filter_name, country,
        )


def _drop_nones(obj):
    """Recursively drop None values from dicts; preserve list/scalar structure."""
    if isinstance(obj, dict):
        return {
            k: _drop_nones(v)
            for k, v in obj.items()
            if v is not None
        }
    if isinstance(obj, list):
        return [_drop_nones(v) for v in obj]
    return obj


class IncrementalDiffPipeline:
    """Diff each item against the incremental state snapshot.

    When incrementalMode is False, passes items through unchanged.
    When incrementalMode is True:
      - Deduplicates by offerId within a single run (first-seen wins)
      - Computes changeType / firstSeenAt / lastSeenAt via state.compute_diff
      - Drops UNCHANGED items (unless emitUnchanged: true)
      - Accumulates updated_snapshot for main.py to write after crawl

    Priority: 200 — after MaxItemsPipeline (100) but before DropNonesPipeline (500).
    Rationale: must run BEFORE DropNonesPipeline so it can compare item fields that
    may be None against the snapshot (e.g. mileageKm=None vs prior None — unchanged,
    not a spurious diff). Running before the None-strip also means we always compare
    the original item shape accurately.
    """

    # Class attributes: read by main.py after the crawl completes.
    # Reset in open_spider() for each run.
    updated_snapshot: dict = {}
    seen_offer_ids: set = set()
    was_truncated: bool = False

    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        input_data = crawler.settings.get('INPUT_DATA') or {}
        obj.incremental_mode = bool(input_data.get('incrementalMode', False))
        obj.emit_unchanged = bool(input_data.get('emitUnchanged', False))
        obj.emit_missing = bool(input_data.get('emitMissing', False))
        obj._max_items = int(input_data.get('maxItems', 1000))
        # Snapshot loaded by main.py and passed via INPUT_DATA['_snapshot']
        obj._snapshot = dict(input_data.get('_snapshot') or {})
        obj._run_ts = (
            input_data.get('_runTs')
            or datetime.now(tz=timezone.utc).isoformat()
        )
        # Reset class attributes for this run (start from the loaded snapshot)
        cls.updated_snapshot = dict(obj._snapshot)
        cls.seen_offer_ids = set()
        cls.was_truncated = False
        return obj

    def open_spider(self) -> None:
        pass

    def process_item(self, item):
        if not self.incremental_mode:
            return item  # pass-through; no change fields added

        adapter = ItemAdapter(item)
        item_dict = adapter.asdict()
        offer_id = item_dict.get('offerId')
        if offer_id is None:
            return item  # cannot diff without offerId

        offer_id_str = str(offer_id)

        # Deduplicate within a single run (first-seen wins)
        if offer_id_str in type(self).seen_offer_ids:
            raise DropItem(f'Duplicate offerId {offer_id_str} in same run — dropping.')
        type(self).seen_offer_ids.add(offer_id_str)

        # Compute diff against snapshot
        from .state import compute_diff
        change_type, first_seen_at, last_seen_at, new_entry = compute_diff(
            item_dict, self._snapshot, self._run_ts
        )

        # Update in-memory snapshot (class attribute so main.py can read it)
        type(self).updated_snapshot[offer_id_str] = new_entry

        # Cold-start baseline build: when the loaded snapshot was empty at
        # open_spider time, suppress all NEW items so the first run silently
        # initialises state instead of dumping the full dataset. This matches
        # the approved UX (Gate 1) and the README's "First run behaviour"
        # callout. Without this, an enabled-but-uninitialised incrementalMode
        # behaves identically to a non-incremental run on day 1.
        if change_type == 'NEW' and not self._snapshot:
            raise DropItem(
                f'offerId {offer_id_str} is NEW on cold-start baseline build — suppressed.'
            )

        # Drop UNCHANGED unless emitUnchanged was requested
        if change_type == 'UNCHANGED' and not self.emit_unchanged:
            raise DropItem(f'offerId {offer_id_str} is UNCHANGED — suppressed.')

        # Attach change fields to item (works for both Scrapy Items and dicts)
        item['changeType'] = change_type
        item['firstSeenAt'] = first_seen_at
        item['lastSeenAt'] = last_seen_at
        offer_entry = type(self).updated_snapshot.get(offer_id_str, {})
        item['priceHistory'] = offer_entry.get('priceHistory', [])
        item['isRepost'] = (change_type == 'REAPPEARED')

        return item

    def close_spider(self, spider) -> None:
        # Detect truncation: if we saw >= maxItems listings, the run was capped.
        # CloseSpider raised by MaxItemsPipeline shuts down the spider, but
        # close_spider fires afterwards — we can compare seen count to maxItems.
        if len(type(self).seen_offer_ids) >= self._max_items:
            type(self).was_truncated = True
            spider.logger.warning(
                'maxItems cap reached — MISSING detection suppressed for this run '
                'to avoid false positives.'
            )


class DropNonesPipeline:
    """Strip None values (top-level and nested) before the Apify dataset push.

    Apify's dataset_schema declares typed fields (string, integer, etc.) and
    rejects null values for those types — items with country-specific optional
    fields would otherwise fail HTTP 400 at push time with "Schema validation
    failed", causing a silent 0-items SUCCEEDED run. By dropping null keys
    here, the resulting dict only contains fields that have real values, and
    JSON Schema's default "additionalProperties allowed, missing fields OK"
    behavior accepts them cleanly.
    """

    def process_item(self, item):
        cleaned = _drop_nones(ItemAdapter(item).asdict())
        return cleaned


class FairPricePipeline:
    """Buffer items for post-crawl fair-price median enrichment.

    Receives items at priority 600, after DropNonesPipeline (500) has cleaned
    them (so items arrive as plain dicts with no None values). Stashes each
    item dict and its bucketing key in class-attribute lists, then raises
    DropItem so the Apify push pipeline at priority 1000 does NOT receive them.

    After the crawl completes, main.py reads the class-attribute buffers,
    computes per-bucket medians (statistics.median), enriches each item with
    priceVsMedianPct and priceRating (only when bucket >= min_bucket_size),
    and pushes each enriched item directly to the Apify dataset via
    dataset.push_data().

    This mirrors the IncrementalDiffPipeline.updated_snapshot class-attribute
    pattern — main.py reads the buffer through the class, not an instance,
    because CrawlerRunner.crawl() returns None (not the pipeline instance).

    Priority: 600 — after DropNonesPipeline (500), before Apify push (1000).

    Bucket key: (make, model, year_bucket, mileage_bucket, currency)
      - year_bucket: 5-year bands via (year // 5) * 5
      - mileage_bucket: 50k km linear bands via (mileageKm // 50_000) * 50_000
      - currency included so PLN/UAH/EUR run independently; no EUR restriction
    """

    # Class attributes — main.py reads these after the crawl completes.
    # Reset in open_spider() on each run (mirrors IncrementalDiffPipeline pattern).
    items_buffer: list = []
    keys_buffer: list = []
    min_bucket_size: int = 5  # minimum items per bucket for median to be emitted (was 10, tuned in PR #49)

    def open_spider(self) -> None:
        # Reset class attributes for this run so stale data from a prior
        # run (e.g. if the process is reused) does not bleed in.
        type(self).items_buffer = []
        type(self).keys_buffer = []

    def process_item(self, item):
        """Stash item in class-level buffer; raise DropItem to prevent double-push.

        Items arrive here as plain dicts (output of DropNonesPipeline at 500).
        We store a reference directly — no ItemAdapter needed.
        """
        # item is already a plain dict at this priority (DropNonesPipeline ran at 500)
        d = item if isinstance(item, dict) else ItemAdapter(item).asdict()
        key = self._bucket_key(d)
        type(self).items_buffer.append(d)
        type(self).keys_buffer.append(key)
        raise DropItem('FairPricePipeline: buffered for post-crawl median enrichment')

    @staticmethod
    def _bucket_key(item: dict):
        """Compute the bucket key for median grouping.

        Returns a 5-tuple (make, model, year_bucket, mileage_bucket, currency)
        or None when the required fields are absent or non-numeric.

        Currency is included in the key so that per-country single-currency
        runs (PLN, UAH, EUR, etc.) each get their own bucket, preventing
        cross-currency median pollution when startUrls mixes domains.
        """
        make = item.get('make')
        model = item.get('model')
        year = item.get('year')
        mileage_km = item.get('mileageKm')
        price = item.get('price')
        currency = item.get('currency')
        if not make or not model or not year or mileage_km is None:
            return None
        if price is None or not currency:
            return None
        try:
            year_bucket = (int(year) // 5) * 5      # 5-year bands (was //2 *2 in PR #48; tuned in PR #49)
            mileage_bucket = (int(mileage_km) // 50_000) * 50_000  # 50k km bands (was //20_000 *20_000 in PR #48; tuned in PR #49)
        except (TypeError, ValueError):
            return None
        return (str(make).lower(), str(model).lower(), year_bucket, mileage_bucket, str(currency).upper())

    @staticmethod
    def _pct_to_rating(pct: float) -> str:
        """Map a percentage deviation to a qualitative fair-price rating.

        Thresholds (approved at Gate 1):
          very_good : pct <= -15.0  (>= 15% below median)
          good      : pct <= -5.0   (5–15% below median)
          fair      : pct <   5.0   (within ±5% of median)
          high      : pct <  15.0   (5–15% above median)
          very_high : pct >= 15.0   (>= 15% above median)
        """
        if pct <= -15.0:
            return 'very_good'
        if pct <= -5.0:
            return 'good'
        if pct < 5.0:
            return 'fair'
        if pct < 15.0:
            return 'high'
        return 'very_high'


class NotificationBufferPipeline:
    """Observational pipeline that buffers compact item summaries for the post-crawl digest.

    Runs at priority 250 — AFTER IncrementalDiffPipeline (200) so that
    ``changeType`` and ``priceHistory`` are already attached to each item,
    and BEFORE DropNonesPipeline (500) so None values are still present
    (read-only; we never mutate item content).

    Class-attribute buffers (mirroring FairPricePipeline pattern):
      new_items_buffer  — compact dicts for NEW items
      price_drop_buffer — compact dicts for UPDATED items with qualifying price drops
      _counts           — running totals keyed by changeType plus 'total'

    These are class attributes so main.py can read them after the crawl via
    ``NotificationBufferPipeline.new_items_buffer`` etc.  CrawlerRunner.crawl()
    returns None, not a pipeline instance, so instance attribute access from
    main.py is impossible — class attributes are the only safe path.

    When ``notifyOn == 'none'`` (default), open_spider sets ``_enabled = False``
    and process_item returns early with near-zero overhead.  No buffers are
    populated, no changeType is accessed.

    Never raises DropItem.  Items continue through the full pipeline chain:
    DropNonesPipeline (500) → FairPricePipeline (600) → Apify push (1000).

    See issue #29 and architecture doc section 4 for the full design rationale.
    """

    # Class-attribute buffers — reset in open_spider() and in main.py pre-run reset.
    new_items_buffer: list = []
    price_drop_buffer: list = []
    _counts: dict = {}

    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        # Defensive reset (mirrors FairPricePipeline pattern).
        # main.py also resets these before the crawl, but the pipeline-level
        # reset guards against edge cases where from_crawler fires multiple times.
        cls.new_items_buffer = []
        cls.price_drop_buffer = []
        cls._counts = {}

        input_data = crawler.settings.get('INPUT_DATA') or {}
        notify_on = str(input_data.get('notifyOn') or 'none').lower()

        valid_notify_on = {'none', 'new_listings', 'price_drops', 'both'}
        if notify_on not in valid_notify_on:
            notify_on = 'none'

        obj._enabled: bool = notify_on in {'new_listings', 'price_drops', 'both'}
        obj._include_new: bool = notify_on in {'new_listings', 'both'}
        obj._include_drops: bool = notify_on in {'price_drops', 'both'}

        try:
            obj._min_pct: int = int(input_data.get('notifyMinPriceDropPct', 5))
        except (TypeError, ValueError):
            obj._min_pct = 5

        if obj._enabled:
            logger.info(
                'NotificationBufferPipeline: enabled — notifyOn=%r '
                'include_new=%s include_drops=%s min_pct=%d',
                notify_on, obj._include_new, obj._include_drops, obj._min_pct,
            )
        return obj

    def open_spider(self) -> None:
        pass

    def process_item(self, item):
        """Observe item; update counts and buffers. Never raises DropItem."""
        if not self._enabled:
            return item

        # changeType is attached by IncrementalDiffPipeline (priority 200).
        # When incrementalMode=False, changeType is absent; the pipeline is
        # disabled for that case too (notifyOn != none + incrementalMode=False
        # triggers Actor.fail() in main.py before the crawl starts).
        change_type = item.get('changeType')
        if change_type is None:
            # incrementalMode=False path — should not happen due to main.py
            # guard, but be defensive.
            return item

        # Always count every item by changeType
        type(self)._counts[change_type] = (
            type(self)._counts.get(change_type, 0) + 1
        )
        type(self)._counts['total'] = (
            type(self)._counts.get('total', 0) + 1
        )

        # --- Buffer NEW items ---
        if self._include_new and change_type == 'NEW':
            type(self).new_items_buffer.append({
                'offerId': item.get('offerId'),
                'url': item.get('url'),
                'title': item.get('title'),
                'price': item.get('price'),
                'currency': item.get('currency'),
                'year': item.get('year'),
                'mileageKm': item.get('mileageKm'),
                'make': item.get('make'),
                'model': item.get('model'),
                'firstSeenAt': item.get('firstSeenAt'),
            })

        # --- Buffer qualifying price drops for UPDATED items ---
        if self._include_drops and change_type == 'UPDATED':
            price_history = item.get('priceHistory') or []
            curr_price = item.get('price')

            if len(price_history) >= 2 and curr_price is not None:
                prev_entry = price_history[-2]
                prev_price = prev_entry.get('price') if isinstance(prev_entry, dict) else None

                if prev_price is not None and prev_price > 0 and curr_price < prev_price:
                    try:
                        pct = round(
                            (prev_price - curr_price) / prev_price * 100.0, 2
                        )
                        if pct >= self._min_pct:
                            type(self).price_drop_buffer.append({
                                'offerId': item.get('offerId'),
                                'url': item.get('url'),
                                'title': item.get('title'),
                                'priceCurrent': curr_price,
                                'pricePrevious': prev_price,
                                'priceDropPct': pct,
                                'currency': item.get('currency'),
                            })
                    except (TypeError, ValueError, ZeroDivisionError):
                        # Bad numeric data in priceHistory — skip silently.
                        pass

        return item


# ---------------------------------------------------------------------------
# Output shaping (issue #24)
# ---------------------------------------------------------------------------

#: Approved 18-field compact slice (Gate 1, 2026-05-18).
#: architect's 15 base fields + engineCapacityCm3, powerHp, color.
COMPACT_FIELDS: frozenset = frozenset({
    'offerId', 'url', 'country', 'title', 'price', 'currency',
    'make', 'model', 'year', 'mileageKm', 'fuelType', 'transmission',
    'bodyType', 'condition', 'description',
    'engineCapacityCm3', 'powerHp', 'color',
})


def shape_output(item: dict, output_mode: str, desc_max_len: 'int | None') -> dict:
    """Apply description truncation and compact-mode field filtering to an item dict.

    This is the canonical implementation shared by OutputShapingPipeline.process_item
    and the two post-crawl push blocks in main.py (FairPrice buffer and MISSING items).

    Args:
        item: plain dict (DropNonesPipeline has already run; no None values expected).
        output_mode: 'full' (no-op filter) or 'compact' (retain COMPACT_FIELDS only).
        desc_max_len: None = no truncation; 0 = drop the field; >0 = truncate to N chars.

    Returns:
        The mutated item dict (mutated in-place for efficiency; returned for chaining).
    """
    # Description truncation (applies in both modes)
    if desc_max_len is not None:
        if desc_max_len == 0:
            item.pop('description', None)
        else:
            desc = item.get('description')
            if desc is not None:
                item['description'] = desc[:desc_max_len]

    # Compact field filter
    if output_mode == 'compact':
        for k in [k for k in list(item.keys()) if k not in COMPACT_FIELDS]:
            del item[k]

    return item


class OutputShapingPipeline:
    """Apply outputMode and descriptionMaxLength transforms to every item.

    Priority: 700 — after FairPricePipeline (600), before Apify push (1000).

    Note: FairPricePipeline raises DropItem for every item at priority 600, so
    in the current architecture no item reaches this pipeline through the normal
    Scrapy chain. The real work is performed by calling shape_output() directly
    in main.py's two post-crawl push blocks (FairPrice buffer and MISSING items).
    This pipeline is registered for defensive completeness and to handle any
    future pipeline reordering.

    Reads INPUT_DATA['outputMode'] (default 'full') and
    INPUT_DATA['descriptionMaxLength'] (default None) from the Scrapy settings.
    """

    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        input_data = crawler.settings.get('INPUT_DATA') or {}
        raw_mode = input_data.get('outputMode', 'full') or 'full'
        obj._output_mode: str = raw_mode if raw_mode in ('full', 'compact') else 'full'
        if raw_mode not in ('full', 'compact'):
            logger.warning(
                'OutputShapingPipeline: invalid outputMode %r — defaulting to "full".',
                raw_mode,
            )
        raw_len = input_data.get('descriptionMaxLength')
        if raw_len is None:
            obj._desc_max_len = None
        else:
            try:
                obj._desc_max_len = int(raw_len)
            except (TypeError, ValueError):
                logger.warning(
                    'OutputShapingPipeline: invalid descriptionMaxLength %r — disabling truncation.',
                    raw_len,
                )
                obj._desc_max_len = None
        logger.info(
            'OutputShapingPipeline: outputMode=%r descriptionMaxLength=%r',
            obj._output_mode, obj._desc_max_len,
        )
        return obj

    def open_spider(self) -> None:
        pass

    def process_item(self, item):
        d = item if isinstance(item, dict) else ItemAdapter(item).asdict()
        return shape_output(d, self._output_mode, self._desc_max_len)
