"""PR #35 — verify FailOnItemErrorExtension flips OlxCarsSpider.crawl_failed=True
when a pipeline raises during process_item.

Strategy:
  - Build a minimal Scrapy CrawlerProcess with:
      * a tiny spider that yields one item via start_requests
      * a custom pipeline that raises a deliberate exception
      * FailOnItemErrorExtension registered via EXTENSIONS
  - Verify type(spider).crawl_failed is True after the crawl completes.

This exercises the same signal path that would fire under Apify when the
ActorDatasetPushPipeline raises ApifyApiError on schema validation failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

ACTOR = Path(r"D:\projects\personal\claude\apify\apify-olx-cars")
sys.path.insert(0, str(ACTOR))

import scrapy
from scrapy.crawler import CrawlerProcess

from src.extensions import FailOnItemErrorExtension
from src.spiders.olx_cars import OlxCarsSpider


class FailingPipeline:
    """Always raises — simulates the ApifyApiError from a schema-validation failure."""

    def process_item(self, item, spider):
        raise RuntimeError("simulated dataset push schema-validation failure")


class _SingleItemSpider(scrapy.Spider):
    """Minimal spider that yields one item from a data: URL (no network)."""

    name = "_pr35_test_spider"
    custom_settings = {
        "LOG_LEVEL": "ERROR",
        "ITEM_PIPELINES": {f"{__name__}.FailingPipeline": 100},
        "EXTENSIONS": {
            "src.extensions.FailOnItemErrorExtension": 500,
            # Disable telnet/logstats noise
            "scrapy.extensions.telnet.TelnetConsole": None,
            "scrapy.extensions.logstats.LogStats": None,
        },
    }

    # Bind to OlxCarsSpider so we can check OlxCarsSpider.crawl_failed
    # (FailOnItemErrorExtension calls type(spider).crawl_failed — so we need
    # to run a spider that IS OlxCarsSpider, otherwise the flag goes onto
    # _SingleItemSpider's class, not OlxCarsSpider's).
    # Instead: we test by checking type(spider).crawl_failed on _SingleItemSpider,
    # since the extension uses type(spider) directly.

    def start_requests(self):
        yield scrapy.Request("data:text/plain;base64,aGVsbG8=", callback=self.parse)

    def parse(self, response):
        yield {"offerId": 12345, "url": "https://example.com/test"}


def main() -> int:
    # Reset the class-level flag
    _SingleItemSpider.crawl_failed = False

    process = CrawlerProcess(settings={
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "TELNETCONSOLE_ENABLED": False,
    })
    process.crawl(_SingleItemSpider)
    process.start()  # blocks until crawl finishes

    flag = getattr(_SingleItemSpider, "crawl_failed", False)
    if flag is True:
        print("PASS — FailOnItemErrorExtension flipped crawl_failed=True after pipeline raised")
        return 0
    print(f"FAIL — crawl_failed is {flag!r} (expected True)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
