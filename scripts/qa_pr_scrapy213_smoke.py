"""Smoke test: verify that OlxCarsSpider.start() is a working async generator.

Checks:
1. spider.start() returns an async generator (not a coroutine or sync generator).
2. At least one scrapy.Request is yielded for a known startUrl (olx.ro/auto-moto/).
3. No full crawl is performed — just the async generator entry point.
"""
import asyncio
import sys
import os
import types
import inspect

# Ensure the src package is importable from the actor root
actor_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, actor_root)

import scrapy
from scrapy.utils.test import get_crawler

# Import the spider
from src.spiders.olx_cars import OlxCarsSpider


def make_spider(input_data: dict) -> OlxCarsSpider:
    """Instantiate a spider with a mock Scrapy settings dict via get_crawler."""
    crawler = get_crawler(OlxCarsSpider, settings_dict={
        'INPUT_DATA': input_data,
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',
    })
    spider = OlxCarsSpider.from_crawler(crawler)
    return spider


async def run_smoke_test():
    print("=== Smoke Test: async def start() ===\n")

    # Test input: startUrls mode with one known RO URL
    input_data = {
        'startUrls': [{'url': 'https://www.olx.ro/auto-moto/'}],
        'maxItems': 5,
        'sortBy': 'created_at:desc',
    }

    spider = make_spider(input_data)

    # --- Check 1: start() returns an async generator ---
    gen = spider.start()
    is_async_gen = inspect.isasyncgen(gen)
    is_coroutine = inspect.iscoroutine(gen)
    is_sync_gen = inspect.isgenerator(gen)

    print(f"Check 1: spider.start() return type")
    print(f"  is_async_gen  = {is_async_gen}  (expected True)")
    print(f"  is_coroutine  = {is_coroutine}  (expected False)")
    print(f"  is_sync_gen   = {is_sync_gen}  (expected False)")

    if not is_async_gen:
        print("\nFAIL: start() did not return an async generator.")
        return False

    # --- Check 2: iterate and collect requests ---
    requests = []
    try:
        async for item in gen:
            if isinstance(item, scrapy.Request):
                requests.append(item)
            # stop after first batch to keep the test fast
            if len(requests) >= 1:
                break
    except StopAsyncIteration:
        pass
    except Exception as exc:
        print(f"\nFAIL: Exception while iterating start(): {exc}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up the generator
        await gen.aclose()

    print(f"\nCheck 2: Requests yielded from start()")
    print(f"  requests collected = {len(requests)}")
    if requests:
        print(f"  first request URL  = {requests[0].url}")
    else:
        print("  WARNING: No requests were yielded.")

    if not requests:
        print("\nFAIL: No scrapy.Request was yielded by start().")
        return False

    # Verify that the URL contains olx.ro (startUrl mode took effect)
    first_url = requests[0].url
    if 'olx.ro' not in first_url:
        print(f"\nFAIL: Expected URL containing 'olx.ro', got: {first_url}")
        return False

    print(f"\n  URL contains 'olx.ro': OK")
    print("\nAll checks PASSED.")
    return True


if __name__ == '__main__':
    ok = asyncio.run(run_smoke_test())
    sys.exit(0 if ok else 1)
