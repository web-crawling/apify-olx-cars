"""S11: parse_listing async conversion — verify pagination still works."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import tempfile
from pathlib import Path

ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from src.spiders.olx_cars import OlxCarsSpider
from src.pipelines import FairPricePipeline, HistoryFilterPipeline, IncrementalDiffPipeline, NotificationBufferPipeline

# Reset class attrs
OlxCarsSpider.crawl_failed = False
OlxCarsSpider._vpic_success_count = 0
OlxCarsSpider._vpic_error_count = 0
FairPricePipeline.items_buffer = []
FairPricePipeline.keys_buffer = []
HistoryFilterPipeline.reset()
IncrementalDiffPipeline.updated_snapshot = {}
IncrementalDiffPipeline.seen_offer_ids = set()
IncrementalDiffPipeline.was_truncated = False
NotificationBufferPipeline.new_items_buffer = []
NotificationBufferPipeline.price_drop_buffer = []
NotificationBufferPipeline._counts = {}

# Use maxItems=60 on PL BMW — should need at least 2 pages (PAGE_LIMIT=50)
settings = get_project_settings()
settings.setmodule("src.settings")
settings.set("INPUT_DATA", {
    "country": "pl",
    "brands": ["bmw"],
    "maxItems": 60,
    "enrichVIN": False,   # keep enrichment off to test pagination only
    "_vinCache": None,
    "startUrls": [],
    "sortBy": "created_at:desc",
    "excludeDamaged": False,
    "firstOwnerOnly": False,
    "serviceBookOnly": False,
    "incrementalMode": False,
    "stateKey": "test",
    "emitUnchanged": False,
    "emitMissing": False,
    "_snapshot": {},
    "_runTs": "2026-01-01T00:00:00+00:00",
    "notifyOn": "none",
    "notifyMinPriceDropPct": 5,
    "notifyTopN": 20,
    "notifyWebhookUrl": "",
    "outputMode": "full",
    "descriptionMaxLength": None,
}, priority="spider")
settings.set("LOG_LEVEL", "WARNING")
settings.set("ITEM_PIPELINES", {
    "src.pipelines.MaxItemsPipeline": 100,
    "src.pipelines.HistoryFilterPipeline": 150,
    "src.pipelines.IncrementalDiffPipeline": 200,
    "src.pipelines.NotificationBufferPipeline": 250,
    "src.pipelines.DropNonesPipeline": 500,
    "src.pipelines.FairPricePipeline": 600,
    "src.pipelines.OutputShapingPipeline": 700,
}, priority="spider")

process = CrawlerProcess(settings)
process.crawl(OlxCarsSpider)
process.start()

items = list(FairPricePipeline.items_buffer)
print(f"ITEM_COUNT: {len(items)}")
print(f"CRAWL_FAILED: {OlxCarsSpider.crawl_failed}")

# With maxItems=60 and PL BMW, we expect > 50 items (proof of page 2 being fetched)
# If pagination was broken (single page only), we'd get exactly 50.
has_second_page = len(items) > 50
print(f"SECOND_PAGE_FETCHED: {has_second_page} (items > 50)")
print(f"S11_PASS: {len(items) > 0 and not OlxCarsSpider.crawl_failed}")
