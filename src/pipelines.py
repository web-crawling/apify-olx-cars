"""Item pipelines for OLX Cars actor.

Pipelines:
  MaxItemsPipeline — enforces the maxItems ceiling at process_item time.
    Raises CloseSpider when the limit is reached, which signals Scrapy to
    shut down cleanly and lets Apify report SUCCEEDED with the items collected.

  DropNonesPipeline — recursively removes None values from items before
    they reach the Apify dataset push pipeline. Apify's dataset schema
    rejects null for typed fields (Draft7 default behavior), so items
    with country-specific fields (e.g. district=None for PT/RO/BG/KZ)
    must be cleaned before push. See issue #33 for the failing run that
    motivated this pipeline.
"""

from __future__ import annotations

import logging

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
