"""S4: vPIC returns 404 — item yields without vinDecoded, error count increments."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import asyncio
from pathlib import Path

ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

from scrapy.http import Request, TextResponse
from scrapy.exceptions import IgnoreRequest
from src.spiders.olx_cars import OlxCarsSpider
from src.items import CarItem

# Test parse_vpic directly with a mocked 404-equivalent response.
# Since handle_httpstatus_list routes non-2xx to parse_vpic (not errback_vpic),
# we test parse_vpic with a non-200 status directly.

class MockKVStore:
    def __init__(self):
        self._data = {}
    async def get_value(self, key): return self._data.get(key)
    async def set_value(self, key, value): self._data[key] = value

async def run():
    mock_cache = MockKVStore()
    # Build a minimal spider with required instance attrs
    spider = OlxCarsSpider.__new__(OlxCarsSpider)
    spider._enrich_vin = True
    spider._vin_cache = mock_cache
    spider._total_yielded = 0
    spider.skipped_partner_count = 0
    spider._total_elements_by_cat = {}
    spider._brand_categories = {}
    spider._make_lookup = {}
    OlxCarsSpider._vpic_success_count = 0
    OlxCarsSpider._vpic_error_count = 0
    OlxCarsSpider.crawl_failed = False

    # Build a minimal CarItem
    item = CarItem()
    item["offerId"] = 99999
    item["url"] = "https://www.olx.pl/d/test"
    item["vin"] = "WBAKJ6C50BCX13187"

    vin = "WBAKJ6C50BCX13187"

    # Build a 404 response
    request = Request(
        url=f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{vin}?format=json",
        meta={"handle_httpstatus_list": [404, 429, 500, 503]},
        cb_kwargs={"item": item, "vin": vin},
    )
    response = TextResponse(
        url=request.url,
        status=404,
        body=b"Not Found",
        request=request,
    )

    yielded_items = []
    async for result in spider.parse_vpic(response, item=item, vin=vin):
        yielded_items.append(result)

    print(f"ITEMS_YIELDED: {len(yielded_items)}")
    print(f"CRAWL_FAILED: {OlxCarsSpider.crawl_failed}")
    print(f"VPIC_ERROR_COUNT: {OlxCarsSpider._vpic_error_count}")
    print(f"VPIC_SUCCESS_COUNT: {OlxCarsSpider._vpic_success_count}")

    if yielded_items:
        item_out = yielded_items[0]
        has_vin_decoded = "vinDecoded" in item_out
        print(f"ITEM_HAS_VINDECODED: {has_vin_decoded}")
    else:
        print("ITEM_HAS_VINDECODED: N/A (no item yielded)")

    # For 404 in parse_vpic: error count should be 1, item yielded without vinDecoded
    ok = (
        len(yielded_items) == 1 and
        OlxCarsSpider._vpic_error_count == 1 and
        OlxCarsSpider._vpic_success_count == 0 and
        not OlxCarsSpider.crawl_failed and
        "vinDecoded" not in yielded_items[0]
    )
    print(f"S4_PASS: {ok}")

asyncio.run(run())
