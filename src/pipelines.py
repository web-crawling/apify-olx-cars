"""Item pipelines for OLX Cars actor.

Pipelines:
  MaxItemsPipeline — enforces the maxItems ceiling at process_item time.
    Raises CloseSpider when the limit is reached, which signals Scrapy to
    shut down cleanly and lets Apify report SUCCEEDED with the items collected.
"""

from __future__ import annotations

import logging

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
