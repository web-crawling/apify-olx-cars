"""Item pipelines for OLX Cars actor.

Pipelines:
  MaxItemsPipeline — enforces the maxItems ceiling at process_item time.
    Raises CloseSpider when the limit is reached, which signals Scrapy to
    shut down cleanly and lets Apify report SUCCEEDED with the items collected.

  IncrementalDiffPipeline — diffs each item against the KV snapshot loaded
    by main.py, attaches changeType/firstSeenAt/lastSeenAt, deduplicates
    by offerId within a run, and drops UNCHANGED items when emitUnchanged
    is False. Pass-through when incrementalMode: false.

  DropNonesPipeline — recursively removes None values from items before
    they reach the Apify dataset push pipeline. Apify's dataset schema
    rejects null for typed fields (Draft7 default behavior), so items
    with country-specific fields (e.g. district=None for PT/RO/BG/KZ)
    must be cleaned before push. See issue #33 for the failing run that
    motivated this pipeline.
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

    def open_spider(self, spider) -> None:
        input_data = spider.settings.get('INPUT_DATA') or {}
        max_items_raw = input_data.get('maxItems', 1000)
        try:
            self.max_items: int = int(max_items_raw)
        except (ValueError, TypeError):
            self.max_items = 1000
        self._count: int = 0
        logger.info('MaxItemsPipeline: max_items=%d', self.max_items)

    def process_item(self, item, spider):
        """Pass item through or raise CloseSpider when limit is hit."""
        self._count += 1
        if self._count > self.max_items:
            raise CloseSpider(
                f'maxItems={self.max_items} reached — stopping spider.'
            )
        return item


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

    def open_spider(self, spider) -> None:
        input_data = spider.settings.get('INPUT_DATA') or {}
        self.incremental_mode = bool(input_data.get('incrementalMode', False))
        self.emit_unchanged = bool(input_data.get('emitUnchanged', False))
        self.emit_missing = bool(input_data.get('emitMissing', False))
        self._max_items = int(input_data.get('maxItems', 1000))
        # Snapshot loaded by main.py and passed via INPUT_DATA['_snapshot']
        self._snapshot = dict(input_data.get('_snapshot') or {})
        self._run_ts = (
            input_data.get('_runTs')
            or datetime.now(tz=timezone.utc).isoformat()
        )
        # Reset class attributes for this run (start from the loaded snapshot)
        type(self).updated_snapshot = dict(self._snapshot)
        type(self).seen_offer_ids = set()
        type(self).was_truncated = False

    def process_item(self, item, spider):
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

    def process_item(self, item, spider):
        cleaned = _drop_nones(ItemAdapter(item).asdict())
        return cleaned
