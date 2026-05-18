"""S1: enrichVIN=false — regression test that no VIN enrichment happens."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json, tempfile, os
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

out_file = Path(tempfile.mktemp(suffix=".jsonl"))

settings = get_project_settings()
settings.setmodule("src.settings")
settings.set("INPUT_DATA", {
    "country": "pl",
    "brands": ["bmw"],
    "maxItems": 5,
    "enrichVIN": False,        # <--- default off
    "_vinCache": None,         # no cache
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
settings.set("FEEDS", {str(out_file): {"format": "jsonlines", "overwrite": True}}, priority="spider")
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

# Read items from FairPrice buffer (items are buffered, not written to FEEDS)
items = list(FairPricePipeline.items_buffer)
print(f"ITEM_COUNT: {len(items)}")

if items:
    sample = items[0]
    has_vin_decoded = 'vinDecoded' in sample
    print(f"SAMPLE_HAS_VINDECODED: {has_vin_decoded}")
    print(f"SAMPLE_VIN: {sample.get('vin', 'N/A')}")
else:
    print("SAMPLE_HAS_VINDECODED: False")
    print("SAMPLE_VIN: N/A")

print(f"VPIC_SUCCESS: {OlxCarsSpider._vpic_success_count}")
print(f"VPIC_ERROR: {OlxCarsSpider._vpic_error_count}")
print(f"CRAWL_FAILED: {OlxCarsSpider.crawl_failed}")
try:
    out_file.unlink(missing_ok=True)
except:
    pass
