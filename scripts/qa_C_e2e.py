"""QA Test C -- End-to-end Scrapy runs for all scenarios.

Runs the spider directly via CrawlerProcess (no Apify SDK) using the
INPUT_DATA Scrapy setting. Writes output to a temp JSONL file and validates.

Usage:
  python scripts/qa_C_e2e.py [scenario_number]
  # e.g. python scripts/qa_C_e2e.py 1  (runs only scenario 1)
  # omit argument to run all scenarios sequentially
"""

import io
import json
import os
import sys
import tempfile
from pathlib import Path

# Force UTF-8 on stdout for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

# Scrapy must be imported before crawling
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# We will directly use our settings module + INPUT_DATA approach
from src.spiders.olx_cars import OlxCarsSpider
from src.items import CarItem
from src.pipelines import FairPricePipeline

SCENARIOS = [
    {
        "id": 1,
        "name": "RO BMW structured filter",
        "input": {"country": "ro", "brands": ["BMW"], "maxItems": 10},
        "assertions": {
            "min_items": 3,
            "max_items": 12,
            "country": "ro",
        }
    },
    {
        "id": 2,
        "name": "UA BMW structured filter (normalisation)",
        "input": {"country": "ua", "brands": ["BMW"], "maxItems": 10},
        "assertions": {
            "min_items": 3,
            "max_items": 12,
            "country": "ua",
            "ua_normalisation": True,
        }
    },
    {
        "id": 3,
        "name": "PT all-brands (standvirtual skip path)",
        "input": {"country": "pt", "maxItems": 50},
        "assertions": {
            "min_items": 5,
            "max_items": 55,
            "country": "pt",
        }
    },
    {
        "id": 4,
        "name": "startUrls mode PL (Audi)",
        "input": {
            "startUrls": [{"url": "https://www.olx.pl/motoryzacja/samochody/audi/"}],
            "maxItems": 10
        },
        "assertions": {
            "min_items": 3,
            "max_items": 12,
            "country": "pl",
        }
    },
    {
        "id": 5,
        "name": "KZ low-volume (category 108)",
        "input": {"country": "kz", "maxItems": 5},
        "assertions": {
            "min_items": 1,
            "max_items": 7,
            "country": "kz",
        }
    },
    {
        "id": 6,
        "name": "Negative: unknown brand (RO)",
        "input": {"country": "ro", "brands": ["NotARealCarBrand"], "maxItems": 5},
        "assertions": {
            "min_items": 0,   # May yield 0 (fallback to parent cat) or up to 5
            "max_items": 6,
            "no_traceback": True,
        }
    },
]

def run_scenario(scenario: dict, out_file: str) -> dict:
    """Run a single scenario and return results."""
    input_data = dict(scenario["input"])
    # Set defaults
    input_data.setdefault("country", "ro")
    input_data.setdefault("sortBy", "created_at:desc")
    input_data.setdefault("maxItems", 100)
    input_data.setdefault("startUrls", [])
    input_data.setdefault("brands", [])

    max_items = input_data["maxItems"]

    # Build Scrapy settings
    settings = get_project_settings()
    settings.setmodule("src.settings")
    settings.set("INPUT_DATA", input_data, priority="spider")
    settings.set("FEEDS", {out_file: {"format": "jsonlines", "overwrite": True}}, priority="spider")
    settings.set("LOG_LEVEL", "WARNING")
    # Disable Apify pipeline — match production chain (minus the Apify push at 1000).
    # FairPricePipeline is included so items are buffered (and NOT written to FEEDS
    # via the normal Scrapy FEEDS writer, which runs after all pipelines). Without
    # it, items would flow through to the FEEDS writer directly — a different chain
    # than production. Note: buffered items are NOT pushed to Apify here (no Actor
    # SDK context), but the buffer is populated and accessible for assertion checks.
    settings.set("ITEM_PIPELINES", {
        "src.pipelines.MaxItemsPipeline": 100,
        "src.pipelines.HistoryFilterPipeline": 150,
        "src.pipelines.IncrementalDiffPipeline": 200,
        # NotificationBufferPipeline observes items after IncrementalDiffPipeline
        # has attached changeType/priceHistory. Purely observational — no DropItem.
        "src.pipelines.NotificationBufferPipeline": 250,
        "src.pipelines.DropNonesPipeline": 500,
        "src.pipelines.FairPricePipeline": 600,
        "src.pipelines.OutputShapingPipeline": 700,
    }, priority="spider")

    # Reset class-level flags
    OlxCarsSpider.crawl_failed = False
    FairPricePipeline.items_buffer = []
    FairPricePipeline.keys_buffer = []

    process = CrawlerProcess(settings)
    process.crawl(OlxCarsSpider)
    process.start()  # blocks until done

    # FairPricePipeline raises DropItem for every item, so the Scrapy FEEDS
    # writer receives nothing (FEEDS file stays empty). Read items from the
    # class-attribute buffer instead — this mirrors the production path where
    # main.py reads FairPricePipeline.items_buffer after the crawl.
    items = list(FairPricePipeline.items_buffer)

    return {
        "items": items,
        "crawl_failed": OlxCarsSpider.crawl_failed,
    }


def validate_items(items: list, assertions: dict, scenario_name: str) -> list:
    """Validate items against assertions. Return list of issues."""
    issues = []
    n = len(items)

    min_items = assertions.get("min_items", 1)
    max_items = assertions.get("max_items", 10000)

    if n < min_items:
        issues.append(f"Too few items: got {n}, expected >= {min_items}")
    if n > max_items:
        issues.append(f"Too many items: got {n}, expected <= {max_items}")

    if not items:
        return issues

    # Check required fields always present
    mandatory_fields = ["offerId", "url", "country", "title", "scrapedAt"]
    for i, item in enumerate(items[:5]):
        for field in mandatory_fields:
            if item.get(field) is None:
                issues.append(f"Item {i}: missing mandatory field {field!r}")

        # features and images always lists
        for arr_field in ("features", "images", "paramsRaw"):
            val = item.get(arr_field)
            if not isinstance(val, list):
                issues.append(f"Item {i}: {arr_field} is not a list (got {type(val).__name__})")

        # seller and location are dicts
        seller = item.get("seller")
        if not isinstance(seller, dict):
            issues.append(f"Item {i}: seller is not a dict")
        else:
            for sf in ("id", "type", "hasPhone", "hasChat"):
                if sf not in seller:
                    issues.append(f"Item {i}: seller.{sf} missing")

        location = item.get("location")
        if not isinstance(location, dict):
            issues.append(f"Item {i}: location is not a dict")
        else:
            if "gpsObfuscated" not in location:
                issues.append(f"Item {i}: location.gpsObfuscated missing")

    # Country check
    expected_country = assertions.get("country")
    if expected_country:
        wrong_country = [i for i, item in enumerate(items) if item.get("country") != expected_country]
        if wrong_country:
            issues.append(f"Items {wrong_country[:3]}: country != {expected_country!r}")

    # UA normalisation check
    if assertions.get("ua_normalisation"):
        for i, item in enumerate(items[:10]):
            mileage = item.get("mileageKm")
            engine = item.get("engineCapacityCm3")
            if mileage is not None and mileage < 100:
                issues.append(f"Item {i}: UA mileageKm={mileage} looks like thousands (not converted)")
            if engine is not None and engine < 100:
                issues.append(f"Item {i}: UA engineCapacityCm3={engine} looks like litres (not converted)")

    return issues


def main():
    run_ids = set()
    if len(sys.argv) > 1:
        try:
            run_ids = {int(x) for x in sys.argv[1:]}
        except ValueError:
            pass

    all_results = []
    overall_pass = True

    for scenario in SCENARIOS:
        if run_ids and scenario["id"] not in run_ids:
            continue

        print(f"\n{'='*60}")
        print(f"[C{scenario['id']}] {scenario['name']}")
        print(f"Input: {json.dumps(scenario['input'])}")

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
            out_file = tmp.name

        try:
            result = run_scenario(scenario, out_file)
            items = result["items"]
            crawl_failed = result["crawl_failed"]

            print(f"Items yielded: {len(items)}, crawl_failed: {crawl_failed}")

            issues = validate_items(items, scenario["assertions"], scenario["name"])

            if crawl_failed and scenario["id"] not in (6,):
                issues.append("crawl_failed=True on a scenario that should not fail")

            if issues:
                print(f"FAIL -- Issues:")
                for iss in issues:
                    print(f"  - {iss}")
                overall_pass = False
                status = "FAIL"
            else:
                print(f"PASS")
                status = "PASS"

            # Show sample of first item
            if items:
                sample = items[0]
                print(f"First item sample: offerId={sample.get('offerId')}, "
                      f"country={sample.get('country')!r}, make={sample.get('make')!r}, "
                      f"model={sample.get('model')!r}, year={sample.get('year')}, "
                      f"price={sample.get('price')}, currency={sample.get('currency')!r}, "
                      f"fuelType={sample.get('fuelType')!r}, "
                      f"features={len(sample.get('features', []))} items")

                # BG: check features merged from comfort+multimedia+safety+other
                if scenario.get("assertions", {}).get("country") == "bg":
                    feat_count = [len(item.get("features") or []) for item in items]
                    avg_feat = sum(feat_count) / len(feat_count) if feat_count else 0
                    print(f"  BG features: avg {avg_feat:.1f} per item, "
                          f"max {max(feat_count) if feat_count else 0}")

            all_results.append({
                "scenario_id": scenario["id"],
                "name": scenario["name"],
                "status": status,
                "item_count": len(items),
                "issues": issues,
            })

        except Exception as exc:
            import traceback
            print(f"EXCEPTION: {exc}")
            traceback.print_exc()
            issues = [f"Exception: {exc}"]
            overall_pass = False
            all_results.append({
                "scenario_id": scenario["id"],
                "name": scenario["name"],
                "status": "EXCEPTION",
                "item_count": 0,
                "issues": issues,
            })
        finally:
            try:
                os.unlink(out_file)
            except Exception:
                pass

    print(f"\n{'='*60}")
    print("SUMMARY:")
    for r in all_results:
        print(f"  [C{r['scenario_id']}] {r['name']}: {r['status']} ({r['item_count']} items)")
    print(f"\nOverall: {'ALL PASS' if overall_pass else 'SOME FAILURES'}")
    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
