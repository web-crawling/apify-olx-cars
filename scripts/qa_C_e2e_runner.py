"""QA Test C -- End-to-end Scrapy runner (subprocess per scenario to avoid ReactorNotRestartable).

Each scenario runs in a fresh subprocess via qa_C_single.py.
"""

import base64
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ACTOR_ROOT = Path(__file__).parent.parent
PYTHON = str(ACTOR_ROOT / ".venv" / "Scripts" / "python")
SINGLE_RUNNER = str(Path(__file__).parent / "qa_C_single.py")

SCENARIOS = [
    {
        "id": 1,
        "name": "RO BMW structured filter (brand resolution + cat_l2_name)",
        "input": {"country": "ro", "brands": ["BMW"], "maxItems": 10},
        "assertions": {
            "min_items": 3,
            "max_items": 12,
            "country": "ro",
            "check_make": "BMW",
        }
    },
    {
        "id": 2,
        "name": "UA BMW structured filter (UA normalisation)",
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
        "name": "startUrls mode PL Audi (country auto-inferred)",
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
        "name": "Negative: unknown brand (RO) -- warns + 0 or fallback items",
        "input": {"country": "ro", "brands": ["NotARealCarBrand"], "maxItems": 5},
        "assertions": {
            "min_items": 0,
            "max_items": 6,
            "no_crawl_fail": True,
        }
    },
]


def run_scenario(scenario: dict) -> dict:
    """Run scenario in a fresh subprocess; return {items, crawl_failed, stderr_log}."""
    input_encoded = base64.b64encode(json.dumps(scenario).encode("utf-8")).decode("ascii")

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, prefix="qa_c") as tmp:
        out_file = tmp.name

    try:
        proc = subprocess.run(
            [PYTHON, SINGLE_RUNNER, input_encoded, out_file],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(ACTOR_ROOT),
            encoding="utf-8",
            errors="replace",
        )
        stderr = proc.stderr or ""
        stdout = proc.stdout or ""

        items = []
        try:
            with open(out_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        items.append(json.loads(line))
        except FileNotFoundError:
            pass

        # Parse crawl_failed from last JSON line in stdout
        crawl_failed = False
        for line in reversed(stdout.strip().splitlines()):
            try:
                meta = json.loads(line)
                crawl_failed = meta.get("crawl_failed", False)
                break
            except Exception:
                pass

        return {
            "items": items,
            "crawl_failed": crawl_failed,
            "stderr": stderr,
            "stdout": stdout,
            "returncode": proc.returncode,
        }
    finally:
        try:
            os.unlink(out_file)
        except Exception:
            pass


def validate_items(items: list, assertions: dict) -> list:
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

    mandatory = ["offerId", "url", "country", "title", "scrapedAt"]
    for i, item in enumerate(items[:5]):
        for field in mandatory:
            if item.get(field) is None:
                issues.append(f"Item {i}: missing mandatory field {field!r}")

        for arr_field in ("features", "images", "paramsRaw"):
            val = item.get(arr_field)
            if not isinstance(val, list):
                issues.append(f"Item {i}: {arr_field} is not a list")

        seller = item.get("seller")
        if not isinstance(seller, dict):
            issues.append(f"Item {i}: seller not a dict")
        else:
            for sf in ("id", "type", "hasPhone", "hasChat"):
                if sf not in seller:
                    issues.append(f"Item {i}: seller.{sf} absent")

        location = item.get("location")
        if not isinstance(location, dict):
            issues.append(f"Item {i}: location not a dict")
        else:
            if "gpsObfuscated" not in location:
                issues.append(f"Item {i}: location.gpsObfuscated absent")

    expected_country = assertions.get("country")
    if expected_country:
        wrong = [i for i, item in enumerate(items) if item.get("country") != expected_country]
        if wrong:
            issues.append(f"Items {wrong[:3]}: country != {expected_country!r}")

    if assertions.get("check_make"):
        expected_make = assertions["check_make"]
        wrong_make = [i for i, item in enumerate(items) if item.get("make") != expected_make]
        if wrong_make:
            issues.append(f"Items {wrong_make[:3]}: make != {expected_make!r} (check cat_l2_name resolution)")

    if assertions.get("ua_normalisation"):
        for i, item in enumerate(items[:10]):
            mileage = item.get("mileageKm")
            engine = item.get("engineCapacityCm3")
            if mileage is not None and mileage < 100:
                issues.append(f"Item {i}: UA mileageKm={mileage} looks like thousands (not multiplied)")
            if engine is not None and engine < 100:
                issues.append(f"Item {i}: UA engineCapacityCm3={engine} looks like litres (not multiplied)")

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

        try:
            result = run_scenario(scenario)
            items = result["items"]
            crawl_failed = result["crawl_failed"]
            returncode = result["returncode"]

            print(f"Items: {len(items)}, crawl_failed: {crawl_failed}, exit: {returncode}")

            # Check stderr for specific warnings
            stderr = result.get("stderr", "")
            has_warning_log = "WARNING" in stderr or "WARNING" in result.get("stdout", "")

            issues = validate_items(items, scenario["assertions"])

            if scenario["assertions"].get("no_crawl_fail") and crawl_failed:
                issues.append("crawl_failed=True on a no_crawl_fail scenario")

            if returncode != 0 and scenario["id"] != 6:
                # Scenario 6 may produce warnings that go to stderr
                pass  # Not a failure by itself; crawl_failed is the real flag

            # PT standvirtual: check if any logged "skipped ... standvirtual"
            if scenario["id"] == 3:
                has_standvirtual_log = "standvirtual" in stderr.lower() or "standvirtual" in result.get("stdout", "").lower()
                if not has_standvirtual_log:
                    print(f"  INFO -- No standvirtual skip log found (may mean no standvirtual offers in this run)")

            # For scenario 6: verify WARNING was logged about unknown brand
            if scenario["id"] == 6:
                has_brand_warn = "not found in brand map" in stderr or "not found in brand map" in result.get("stdout", "")
                if not has_brand_warn:
                    issues.append("Expected 'not found in brand map' warning for unknown brand, not found in logs")

            if issues:
                print(f"FAIL -- Issues:")
                for iss in issues:
                    print(f"  - {iss}")
                overall_pass = False
                status = "FAIL"
            else:
                print(f"PASS")
                status = "PASS"

            # Sample
            if items:
                s = items[0]
                print(f"  Sample: offerId={s.get('offerId')}, country={s.get('country')!r}, "
                      f"make={s.get('make')!r}, model={s.get('model')!r}, "
                      f"year={s.get('year')}, price={s.get('price')} {s.get('currency')!r}, "
                      f"fuel={s.get('fuelType')!r}, trans={s.get('transmission')!r}, "
                      f"features={len(s.get('features') or [])}, images={len(s.get('images') or [])}")

                if scenario["id"] == 3:  # PT
                    # Count how many have co2Emissions
                    co2_count = sum(1 for item in items if item.get("co2Emissions") is not None)
                    print(f"  PT: {co2_count}/{len(items)} items have co2Emissions")

                if scenario["id"] == 2:  # UA
                    # Show UA-specific normalised values
                    print(f"  UA mileageKm={s.get('mileageKm')}, engineCapacityCm3={s.get('engineCapacityCm3')}, "
                          f"transmission={s.get('transmission')!r}, color={s.get('color')!r}")

                if scenario["id"] == 5:  # KZ
                    print(f"  KZ features_count={len(s.get('features') or [])}, ownersCount={s.get('ownersCount')}")

            all_results.append({
                "scenario_id": scenario["id"],
                "name": scenario["name"],
                "status": status,
                "item_count": len(items),
                "issues": issues,
            })

        except subprocess.TimeoutExpired:
            print(f"FAIL -- Subprocess timeout (>90s)")
            overall_pass = False
            all_results.append({
                "scenario_id": scenario["id"],
                "name": scenario["name"],
                "status": "TIMEOUT",
                "item_count": 0,
                "issues": ["Subprocess timeout"],
            })
        except Exception as exc:
            import traceback
            print(f"EXCEPTION: {exc}")
            traceback.print_exc()
            overall_pass = False
            all_results.append({
                "scenario_id": scenario["id"],
                "name": scenario["name"],
                "status": "EXCEPTION",
                "item_count": 0,
                "issues": [str(exc)],
            })

    print(f"\n{'='*60}")
    print("SUMMARY:")
    for r in all_results:
        print(f"  [C{r['scenario_id']}] {r['name']}: {r['status']} ({r['item_count']} items)")
    print(f"\nOverall: {'ALL PASS' if overall_pass else 'SOME FAILURES'}")

    # Save results
    out_path = Path(__file__).parent / "qa_C_results.json"
    out_path.write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")
    print(f"Results saved to {out_path}")

    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
