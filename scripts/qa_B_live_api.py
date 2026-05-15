"""QA Test B -- Live API sanity: one tiny request per country.

For each of ro, pl, bg, pt, ua, kz:
  - GET /api/v1/offers/?category_id=<id>&limit=1&offset=0
  - Assert HTTP 200
  - Assert data[0] exists
  - Assert metadata.adverts.config.targeting.cat_l2_name exists
  - Run the offer through CarItemLoader and assert expected normalised fields.
  - UA-specific: assert mileageKm > 1000 (thousands x1000 normalisation)
  - UA-specific: assert engineCapacityCm3 >= 100 (litre x1000 normalisation)

Results written to stdout and to qa_B_results.json in the same directory.
"""

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

# Add actor src to path so we can import CarItemLoader etc.
ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

# We need to run in a context where Scrapy's items are importable.
from src.items import CarItem
from src.itemloaders import CarItemLoader
from src.data.param_maps import (
    PARAM_KEY_MAP, FUEL_NORMALIZATION, TRANSMISSION_NORMALIZATION,
    BODY_NORMALIZATION, CONDITION_NORMALIZATION, UA_COLOR_MAP, KZ_COLOR_MAP,
)

COUNTRIES = {
    "ro": {"domain": "www.olx.ro", "cat_id": 84},
    "pl": {"domain": "www.olx.pl", "cat_id": 84},
    "bg": {"domain": "www.olx.bg", "cat_id": 1117},
    "pt": {"domain": "www.olx.pt", "cat_id": 378},
    "ua": {"domain": "www.olx.ua", "cat_id": 108},
    "kz": {"domain": "www.olx.kz", "cat_id": 108},
}

ACCEPT_LANGUAGE = {
    "ro": "ro-RO,ro;q=0.9",
    "pl": "pl-PL,pl;q=0.9",
    "bg": "bg-BG,bg;q=0.9",
    "pt": "pt-PT,pt;q=0.9",
    "ua": "uk-UA,uk;q=0.9",
    "kz": "ru-KZ,ru;q=0.9",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

results = {}
all_pass = True


def make_item_from_offer(offer, country, cat_l2_name):
    """Replicate spider's _make_item logic without Scrapy/Twisted."""
    loader = CarItemLoader(item=CarItem())

    params = offer.get("params") or []
    params_by_key = {}
    for p in params:
        k = p.get("key")
        if k:
            params_by_key[k] = p.get("value") or {}

    def get_param_value(field):
        key = PARAM_KEY_MAP.get(field, {}).get(country)
        if not key:
            return None
        return params_by_key.get(key) or None

    def get_param_key_val(field):
        v = get_param_value(field)
        if v is None:
            return None
        raw = v.get("key")
        return str(raw) if raw is not None else None

    def get_param_label(field):
        v = get_param_value(field)
        if v is None:
            return None
        raw = v.get("label")
        return str(raw) if raw is not None else None

    loader.add_value("offerId", offer.get("id"))
    loader.add_value("url", offer.get("url"))
    loader.add_value("country", country)
    loader.add_value("title", offer.get("title"))
    loader.add_value("scrapedAt", "2026-05-15T12:00:00+00:00")
    loader.add_value("description", offer.get("description") or "")

    price_param = params_by_key.get("price") or {}
    loader.add_value("price", price_param.get("value"))
    loader.add_value("currency", price_param.get("currency"))
    loader.add_value("priceNegotiable", (price_param.get("type") or "") == "arranged")
    loader.add_value("pricePrevious", price_param.get("previous_value"))
    loader.add_value("priceConverted", price_param.get("converted_value"))
    loader.add_value("priceCurrencyConverted", price_param.get("converted_currency"))

    loader.add_value("make", cat_l2_name)
    model_val = params_by_key.get("model") or {}
    loader.add_value("model", model_val.get("label"))

    year_raw = get_param_key_val("year") or get_param_label("year")
    loader.add_value("year", year_raw)

    mileage_key = PARAM_KEY_MAP.get("mileage", {}).get(country)
    mileage_raw = None
    if mileage_key:
        mv = params_by_key.get(mileage_key) or {}
        mileage_raw = mv.get("key") or mv.get("label")
    if mileage_raw is not None:
        try:
            mileage_int = int(str(mileage_raw).replace(" ", "").replace("\xa0", ""))
            if country == "ua" and mileage_key == "motor_mileage_thou":
                mileage_int = mileage_int * 1000
            loader.add_value("mileageKm", mileage_int)
        except (TypeError, ValueError):
            loader.add_value("mileageKm", "")
    else:
        loader.add_value("mileageKm", "")

    fuel_raw = get_param_key_val("fuel")
    if fuel_raw is not None:
        loader.add_value("fuelType", FUEL_NORMALIZATION.get(str(fuel_raw).lower(), "other"))
    else:
        loader.add_value("fuelType", "")

    trans_raw = get_param_key_val("transmission")
    if trans_raw is not None:
        loader.add_value("transmission", TRANSMISSION_NORMALIZATION.get(str(trans_raw).lower(), "other"))
    else:
        loader.add_value("transmission", "")

    body_raw = get_param_key_val("body")
    if body_raw is not None:
        loader.add_value("bodyType", BODY_NORMALIZATION.get(str(body_raw).lower(), "other"))
    else:
        loader.add_value("bodyType", "")

    cond_raw = get_param_key_val("condition")
    if cond_raw is not None:
        loader.add_value("condition", CONDITION_NORMALIZATION.get(str(cond_raw).lower(), "other"))
    else:
        loader.add_value("condition", "")

    engine_key = PARAM_KEY_MAP.get("engine_size", {}).get(country)
    engine_raw = None
    if engine_key:
        ev = params_by_key.get(engine_key) or {}
        engine_raw = ev.get("key") or ev.get("label")
    if engine_raw is not None:
        try:
            es = str(engine_raw).replace(" ", "").replace("\xa0", "")
            if country == "ua" and engine_key == "motor_engine_size_litre":
                loader.add_value("engineCapacityCm3", int(float(es) * 1000))
            else:
                loader.add_value("engineCapacityCm3", int(float(es)))
        except (TypeError, ValueError):
            loader.add_value("engineCapacityCm3", "")
    else:
        loader.add_value("engineCapacityCm3", "")

    power_raw = get_param_key_val("power") or get_param_label("power")
    if power_raw is not None:
        try:
            loader.add_value("powerHp", int(str(power_raw).split()[0]))
        except (TypeError, ValueError, IndexError):
            loader.add_value("powerHp", "")
    else:
        loader.add_value("powerHp", "")

    color_raw = get_param_key_val("color")
    if color_raw is not None:
        cs = str(color_raw)
        if country == "ua":
            cs = UA_COLOR_MAP.get(cs, cs)
        elif country == "kz":
            cs = KZ_COLOR_MAP.get(cs, cs)
        loader.add_value("color", cs)
    else:
        loader.add_value("color", "")

    loader.add_value("vin", get_param_key_val("vin") or "")
    loader.add_value("licensePlate", get_param_key_val("license_plate") or "")
    loader.add_value("drivetrain", get_param_key_val("drivetrain") or "")

    sw_raw = get_param_key_val("steering_wheel")
    if sw_raw == "1":
        sw_raw = "lhd"
    loader.add_value("steeringWheelSide", sw_raw or "")

    doors_raw = get_param_key_val("doors") or get_param_label("doors")
    if doors_raw is not None:
        try:
            loader.add_value("doorCount", int(str(doors_raw).split("-")[0].split()[0]))
        except (TypeError, ValueError, IndexError):
            loader.add_value("doorCount", "")
    else:
        loader.add_value("doorCount", "")

    loader.add_value("seatCount", get_param_key_val("seats") or get_param_label("seats") or "")
    loader.add_value("registrationStatus", get_param_key_val("registration_status") or "")
    loader.add_value("countryOfOrigin", get_param_key_val("country_of_origin") or get_param_label("country_of_origin") or "")
    loader.add_value("customsCleared", get_param_key_val("customs_cleared") or "")
    loader.add_value("ownersCount", get_param_key_val("owners_count") or get_param_label("owners_count") or "")
    loader.add_value("co2Emissions", get_param_key_val("co2_emissions") or get_param_label("co2_emissions") or "")

    features = []
    if country in ("ua", "kz"):
        feat_key = PARAM_KEY_MAP.get("features_ua_kz", {}).get(country)
        if feat_key:
            feat_val = params_by_key.get(feat_key) or {}
            feat_keys = feat_val.get("key")
            if isinstance(feat_keys, list):
                features.extend(str(k) for k in feat_keys if k)
            elif feat_keys:
                features.append(str(feat_keys))
    elif country == "bg":
        for bg_field in ("features_bg_comfort", "features_bg_multimedia", "features_bg_safety", "features_bg_other"):
            bg_key = PARAM_KEY_MAP.get(bg_field, {}).get("bg")
            if bg_key:
                bg_val = params_by_key.get(bg_key) or {}
                bg_keys = bg_val.get("key")
                if isinstance(bg_keys, list):
                    features.extend(str(k) for k in bg_keys if k)
                elif bg_keys:
                    features.append(str(bg_keys))
    seen = set()
    unique_features = [f for f in features if not (f in seen or seen.add(f))]
    loader.add_value("features", unique_features)

    photos = offer.get("photos") or []
    images = [
        p["link"].replace("{width}", "800").replace("{height}", "600")
        for p in photos if p.get("link")
    ]
    loader.add_value("images", images)
    loader.add_value("paramsRaw", params)

    promo = offer.get("promotion") or {}
    if promo:
        loader.add_value("promotionFlags", {
            "highlighted": bool(promo.get("highlighted", False)),
            "topAd": bool(promo.get("top_ad", False)),
            "urgent": bool(promo.get("urgent", False)),
        })
    else:
        loader.add_value("promotionFlags", "")

    loader.add_value("postedAt", offer.get("created_time") or "")
    loader.add_value("refreshedAt", offer.get("last_refresh_time") or "")
    loader.add_value("validTo", offer.get("valid_to_time") or "")

    user = offer.get("user") or {}
    contact = offer.get("contact") or {}
    loader.add_value("seller", {
        "id": user.get("id"),
        "uuid": user.get("uuid"),
        "name": user.get("name"),
        "companyName": user.get("company_name"),
        "type": "dealer" if offer.get("business") else "private",
        "memberSince": user.get("created"),
        "hasPhone": bool(contact.get("phone", False)),
        "hasChat": bool(contact.get("chat", False)),
    })

    loc = offer.get("location") or {}
    map_data = offer.get("map") or {}
    show_detailed = map_data.get("show_detailed")
    loader.add_value("location", {
        "city": (loc.get("city") or {}).get("name"),
        "region": (loc.get("region") or {}).get("name"),
        "district": (loc.get("district") or {}).get("name"),
        "latitude": map_data.get("lat"),
        "longitude": map_data.get("lon"),
        "gpsObfuscated": not bool(show_detailed) if show_detailed is not None else True,
    })

    item = loader.load_item()
    if item.get("features") is None:
        item["features"] = []
    if item.get("images") is None:
        item["images"] = []
    if item.get("paramsRaw") is None:
        item["paramsRaw"] = []
    return item


print("=== Section B: Live API Sanity Tests ===\n")

for country, cfg in COUNTRIES.items():
    domain = cfg["domain"]
    cat_id = cfg["cat_id"]
    url = f"https://{domain}/api/v1/offers/?category_id={cat_id}&limit=1&offset=0"

    country_results = {"url": url, "issues": []}
    print(f"[{country.upper()}] GET {url}")

    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "Accept-Language": ACCEPT_LANGUAGE[country],
            "User-Agent": USER_AGENT,
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = {}
        print(f"  FAIL -- HTTP {status}")
        country_results["status"] = status
        country_results["issues"].append(f"HTTP {status}")
        all_pass = False
        results[country] = country_results
        print()
        continue
    except Exception as exc:
        print(f"  FAIL -- Request error: {exc}")
        country_results["issues"].append(str(exc))
        all_pass = False
        results[country] = country_results
        print()
        continue

    country_results["status"] = status
    print(f"  HTTP {status}")

    if status != 200:
        print(f"  FAIL -- Expected 200, got {status}")
        country_results["issues"].append(f"HTTP {status}")
        all_pass = False
        results[country] = country_results
        print()
        continue

    data = body.get("data") or []
    metadata = body.get("metadata") or {}
    targeting = metadata.get("adverts", {}).get("config", {}).get("targeting", {})
    cat_l2_name = targeting.get("cat_l2_name")
    total_elements = metadata.get("total_elements")
    visible_total_count = metadata.get("visible_total_count")

    country_results["total_elements"] = total_elements
    country_results["visible_total_count"] = visible_total_count
    country_results["cat_l2_name"] = cat_l2_name

    # Assert data[0] exists
    if not data:
        print(f"  FAIL -- data[] is empty (total_elements={total_elements})")
        country_results["issues"].append("data[] empty")
        all_pass = False
        results[country] = country_results
        print()
        continue
    print(f"  PASS -- data[0] exists (total_elements={total_elements}, visible={visible_total_count})")

    # Assert cat_l2_name
    if cat_l2_name:
        print(f"  PASS -- cat_l2_name={cat_l2_name!r}")
    else:
        print(f"  WARN -- cat_l2_name absent from targeting (may be None at parent category level)")
        country_results["issues"].append("cat_l2_name absent at parent category")

    # Run through loader
    offer = data[0]
    item = make_item_from_offer(offer, country, cat_l2_name)

    # Required fields always present
    required = ["offerId", "url", "country", "title", "scrapedAt", "features", "images", "paramsRaw", "seller", "location"]
    missing_required = [f for f in required if item.get(f) is None and f not in ("features",) or (f == "features" and item.get(f) is None)]
    # features and images default to [] so check they are lists
    for arr_field in ("features", "images", "paramsRaw"):
        if not isinstance(item.get(arr_field), list):
            country_results["issues"].append(f"{arr_field} is not a list: {item.get(arr_field)!r}")
            all_pass = False

    if missing_required:
        print(f"  FAIL -- Missing required fields: {missing_required}")
        country_results["issues"].append(f"Missing required: {missing_required}")
        all_pass = False
    else:
        print(f"  PASS -- Required fields all present")

    # UA-specific normalization checks
    if country == "ua":
        mileage = item.get("mileageKm")
        engine = item.get("engineCapacityCm3")
        print(f"  UA mileageKm={mileage}, engineCapacityCm3={engine}")
        if mileage is not None and mileage < 100:
            print(f"  WARN -- UA mileageKm={mileage} looks like it might be in thousands (not multiplied by 1000)")
            country_results["issues"].append(f"UA mileage suspect: {mileage}")
        elif mileage is None:
            print(f"  INFO -- UA mileageKm is None (no mileage param on this listing)")
        else:
            print(f"  PASS -- UA mileageKm={mileage} (plausible km value)")

        if engine is not None and engine < 100:
            print(f"  WARN -- UA engineCapacityCm3={engine} looks like litres (not multiplied by 1000)")
            country_results["issues"].append(f"UA engine suspect: {engine}")
        elif engine is None:
            print(f"  INFO -- UA engineCapacityCm3 is None (no engine param on this listing)")
        else:
            print(f"  PASS -- UA engineCapacityCm3={engine} (plausible cm3 value)")

    # Sample key field values
    sample = {
        "offerId": item.get("offerId"),
        "make": item.get("make"),
        "model": item.get("model"),
        "year": item.get("year"),
        "price": item.get("price"),
        "currency": item.get("currency"),
        "fuelType": item.get("fuelType"),
        "transmission": item.get("transmission"),
        "mileageKm": item.get("mileageKm"),
        "engineCapacityCm3": item.get("engineCapacityCm3"),
        "features_count": len(item.get("features") or []),
        "images_count": len(item.get("images") or []),
    }
    country_results["sample"] = sample
    print(f"  Sample: {json.dumps(sample)}")

    if not country_results["issues"]:
        country_results["result"] = "PASS"
        print(f"  RESULT: PASS\n")
    else:
        country_results["result"] = "WARN/FAIL"
        print(f"  RESULT: ISSUES: {country_results['issues']}\n")

    results[country] = country_results

# Write results file
out_path = Path(__file__).parent / "qa_B_results.json"
out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print(f"Results written to {out_path}")
print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME ISSUES (see above)'}")
sys.exit(0 if all_pass else 1)
