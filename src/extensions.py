"""Scrapy extensions for OLX Cars actor.

FailOnItemErrorExtension — hooks Scrapy's `item_error` signal which fires
whenever an item pipeline raises an exception (e.g. ApifyApiError on
dataset push due to schema validation failure). Sets the spider's
class-level ``crawl_failed`` flag so main.py propagates the failure as
``await Actor.fail()`` instead of letting the run silently complete with
SUCCEEDED and 0 items.

See issue #34 — the silent-failure pattern that motivates this extension.

Why a Scrapy extension (and not a pipeline wrapper):
- Scrapy emits the ``item_error`` signal AFTER any pipeline raises, with
  the failing pipeline already isolated. Subscribing to the signal lets
  us observe pipeline-level errors without needing to wrap or replace the
  apify-provided ActorDatasetPushPipeline.
- Mirrors the existing class-attribute pattern already used for HTTP-level
  failures in OlxCarsSpider — see ``src/main.py`` and ``src/spiders/olx_cars.py``
  for the rationale (CrawlerRunner.crawl() returns None, so the spider
  instance can't carry state out of the crawl).
"""

from __future__ import annotations

import logging

from scrapy import signals

logger = logging.getLogger(__name__)


class FailOnItemErrorExtension:
    """Marks the spider's class-level ``crawl_failed`` flag when any item
    pipeline raises during ``process_item``. Logs the failing item's
    identity and the exception type at ERROR level."""

    @classmethod
    def from_crawler(cls, crawler):
        ext = cls()
        crawler.signals.connect(ext.item_error, signal=signals.item_error)
        return ext

    def item_error(self, item, response, spider, failure) -> None:
        exc_type = failure.type.__name__ if hasattr(failure, 'type') else type(failure).__name__
        exc_value = failure.value if hasattr(failure, 'value') else failure
        # Pull a usable identity from the item; tolerate non-dict items.
        try:
            offer_id = item.get('offerId') if hasattr(item, 'get') else None
            url = item.get('url') if hasattr(item, 'get') else None
        except Exception:
            offer_id = None
            url = None
        logger.error(
            'Item pipeline error — propagating as fatal: %s: %s (offerId=%s url=%s)',
            exc_type, exc_value, offer_id, url,
        )
        type(spider).crawl_failed = True
