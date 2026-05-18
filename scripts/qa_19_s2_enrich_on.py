"""S2: enrichVIN=true with in-memory mock KV store."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import asyncio, json, tempfile, os
from pathlib import Path

ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from src.spiders.olx_cars import OlxCarsSpider
from src.pipelines import FairPricePipeline, HistoryFilterPipeline, IncrementalDiffPipeline, NotificationBufferPipeline


class MockKVStore:
    """In-memory mock for Apify KeyValueStore with async get/set."""
    def __init__(self):
        self._data: dict = {}

    async def get_value(self, key: str):
        return self._data.get(key)

    async def set_value(self, key: str, value):
        self._data[key] = value


mock_vin_cache = MockKVStore()

# As of the lazy-open fix (#61), the spider opens the named KV store via
# `Actor.open_key_value_store(name='olx-cars-vin-cache')` on first VIN-bearing
# item. Patch that call to return our in-memory mock instead of touching the
# real Apify SDK.
from unittest.mock import AsyncMock, patch
from apify import Actor
_open_kvs_patcher = patch.object(
    Actor, "open_key_value_store", new=AsyncMock(return_value=mock_vin_cache),
)
_open_kvs_patcher.start()

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

settings = get_project_settings()
settings.setmodule("src.settings")
settings.set("INPUT_DATA", {
    "country": "pl",
    "brands": ["bmw"],
    "maxItems": 8,
    "enrichVIN": True,
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
print(f"VPIC_SUCCESS: {OlxCarsSpider._vpic_success_count}")
print(f"VPIC_ERROR: {OlxCarsSpider._vpic_error_count}")
print(f"CRAWL_FAILED: {OlxCarsSpider.crawl_failed}")
print(f"CACHE_SIZE: {len(mock_vin_cache._data)}")

# Count items with VIN present
vin_items = [i for i in items if i.get("vin")]
enriched_items = [i for i in items if i.get("vinDecoded")]
print(f"ITEMS_WITH_VIN: {len(vin_items)}")
print(f"ITEMS_WITH_VINDECODED: {len(enriched_items)}")

if enriched_items:
    sample = enriched_items[0]
    vd = sample.get("vinDecoded", {})
    print(f"SAMPLE_VINDECODED_KEYS: {sorted(vd.keys())}")
    # Check VPIC_FIELD_MAP keys in decoded
    from src.spiders.olx_cars import VPIC_FIELD_MAP
    expected_keys = set(VPIC_FIELD_MAP.keys())
    actual_keys = set(vd.keys())
    overlap = expected_keys & actual_keys
    print(f"VPIC_FIELD_MAP_KEYS_IN_SAMPLE: {len(overlap)}/{len(expected_keys)}")
