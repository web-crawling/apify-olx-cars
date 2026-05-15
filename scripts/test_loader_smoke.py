"""Smoke test for CarItemLoader.

Constructs a CarItemLoader with a realistic sample RO offer dict
(based on the BMW X6 example from 01-data-points.md) and asserts
that every field in dataset_schema.json is present in the output.

Run from the apify-olx-cars directory:
    .venv/Scripts/python scripts/test_loader_smoke.py
"""

from __future__ import annotations

import sys
import os
import json
from datetime import datetime, timezone

# Add the actor src package to the path so we can import without running the
# full Scrapy machinery.  We run from the actor root directory.
sys.path.insert(0, os.path.abspath('.'))

from src.items import CarItem
from src.itemloaders import CarItemLoader
from src.spiders.olx_cars import OlxCarsSpider

# ---------------------------------------------------------------------------
# Sample offer dict — realistic RO (olx.ro) BMW X6 listing
# Based on the payload documented in 01-data-points.md
# ---------------------------------------------------------------------------

SAMPLE_OFFER_RO = {
    "id": 303514047,
    "url": "https://www.olx.ro/d/oferta/bmw-x6-in-stare-perfecta-IDkxwRR.html",
    "title": "Bmw x6 in stare perfecta",
    "description": "BMW X6 M sport<br />Stare perfecta&amp;impecabila<br />An fabricatie 2021",
    "last_refresh_time": "2026-05-15T14:39:20+03:00",
    "created_time": "2026-05-06T14:31:07+03:00",
    "valid_to_time": "2026-06-05T14:39:19+03:00",
    "business": False,
    "params": [
        {
            "key": "price",
            "value": {
                "value": 52999,
                "currency": "EUR",
                "type": "price",
                "arranged": False,
                "negotiable": False,
                "label": "52 999 €",
                "previous_value": 56000,
                "converted_value": 263000,
                "converted_currency": "RON",
            }
        },
        {
            "key": "model",
            "value": {"key": "x6", "label": "X6"}
        },
        {
            "key": "year",
            "value": {"key": "2021", "label": "2021"}
        },
        {
            "key": "rulaj_pana",
            "value": {"key": "45000", "label": "45 000 km"}
        },
        {
            "key": "petrol",
            "value": {"key": "diesel", "label": "Diesel"}
        },
        {
            "key": "gearbox",
            "value": {"key": "automatic", "label": "Automată"}
        },
        {
            "key": "car_body",
            "value": {"key": "suv", "label": "SUV"}
        },
        {
            "key": "state",
            "value": {"key": "used", "label": "Folosit"}
        },
        {
            "key": "enginesize",
            "value": {"key": "3000", "label": "3000 cm3"}
        },
        {
            "key": "engine_power",
            "value": {"key": "285", "label": "285 CP"}
        },
        {
            "key": "color",
            "value": {"key": "black", "label": "Negru"}
        },
        {
            "key": "door_count",
            "value": {"key": "4", "label": "4"}
        },
        {
            "key": "steering_wheel",
            "value": {"key": "lhd", "label": "Stânga (normal)"}
        },
        {
            "key": "registration_state",
            "value": {"key": "registered", "label": "Înmatriculat în RO"}
        },
    ],
    "photos": [
        {
            "id": "abc123",
            "filename": "v1/files/abc123/image",
            "rotation": 0,
            "width": 1600,
            "height": 1200,
            "link": "https://frankfurt.apollo.olxcdn.com/v1/files/abc123/image;s={width}x{height}",
        },
        {
            "id": "def456",
            "filename": "v1/files/def456/image",
            "rotation": 0,
            "width": 1600,
            "height": 1200,
            "link": "https://frankfurt.apollo.olxcdn.com/v1/files/def456/image;s={width}x{height}",
        },
    ],
    "user": {
        "id": 12345678,
        "uuid": "abc123-def456-ghi789",
        "name": "Ion P.",
        "company_name": None,
        "created": "2019-03-15T10:00:00+02:00",
        "last_seen": "2026-05-15T12:00:00+03:00",
    },
    "contact": {
        "name": "Ion P.",
        "phone": True,
        "chat": False,
        "negotiation": False,
        "courier": False,
    },
    "location": {
        "city": {"id": 11, "name": "București", "normalized_name": "bucuresti"},
        "region": {"id": 15, "name": "Ilfov", "normalized_name": "ilfov"},
        "district": None,
    },
    "map": {
        "zoom": 11,
        "lat": 44.4268,
        "lon": 26.1025,
        "radius": 3,
        "show_detailed": False,
    },
    "promotion": {
        "highlighted": True,
        "urgent": False,
        "top_ad": True,
        "options": ["bundle_premium"],
        "b2c_ad_page": True,
        "premium_ad_page": True,
    },
    "partner": None,
    "category": {"id": 183, "type": "automotive"},
}

# ---------------------------------------------------------------------------
# UA sample — tests mileage×1000 and engine litre conversion + features list
# ---------------------------------------------------------------------------

SAMPLE_OFFER_UA = {
    "id": 999888777,
    "url": "https://www.olx.ua/d/uk/obyavlenie/bmw-x5-ukraina-ID999888.html",
    "title": "BMW X5 відмінний стан",
    "description": "BMW X5 E70<br />3.0 бензин",
    "last_refresh_time": "2026-05-10T12:00:00+03:00",
    "created_time": "2026-05-01T09:00:00+03:00",
    "valid_to_time": "2026-05-31T09:00:00+03:00",
    "business": True,
    "params": [
        {
            "key": "price",
            "value": {
                "value": 15000,
                "currency": "USD",
                "type": "price",
                "arranged": False,
                "negotiable": False,
                "label": "15 000 $",
                "previous_value": None,
                "converted_value": 620000,
                "converted_currency": "UAH",
            }
        },
        {
            "key": "model",
            "value": {"key": "x5", "label": "X5"}
        },
        {
            "key": "motor_year",
            "value": {"key": "2010", "label": "2010"}
        },
        {
            "key": "motor_mileage_thou",
            "value": {"key": "150", "label": "150 тис. км"}
        },
        {
            "key": "fuel_type",
            "value": {"key": "petrol", "label": "Бензин"}
        },
        {
            "key": "transmission_type",
            "value": {"key": "546", "label": "Автомат"}
        },
        {
            "key": "car_body",
            "value": {"key": "suv", "label": "Позашляховик"}
        },
        {
            "key": "condition",
            "value": {"key": "good", "label": "Гарний"}
        },
        {
            "key": "motor_engine_size_litre",
            "value": {"key": "3.0", "label": "3.0"}
        },
        {
            "key": "power",
            "value": {"key": "272", "label": "272 к.с."}
        },
        {
            "key": "color",
            "value": {"key": "1", "label": "Чорний"}  # numeric → "black"
        },
        {
            "key": "vin_number",
            "value": {"key": "WBAFE81070CY12345", "label": "WBAFE81070CY12345"}
        },
        {
            "key": "drive_type",
            "value": {"key": "4x4", "label": "Повний"}
        },
        {
            "key": "cleared_customs",
            "value": {"key": "yes", "label": "Розмитнена"}
        },
        {
            "key": "car_option",
            "value": {
                "key": ["air_con", "park_assist", "electric_windows", "cruise_control"],
                "label": "Кондиціонер, Парктронік, Електросклопідйомники, Круїз-контроль"
            }
        },
        {
            "key": "doors_num",
            "value": {"key": "5", "label": "5"}
        },
        {
            "key": "seats_num",
            "value": {"key": "5", "label": "5"}
        },
    ],
    "photos": [
        {
            "id": "ua111",
            "filename": "v1/files/ua111/image",
            "rotation": 0,
            "width": 1600,
            "height": 1200,
            "link": "https://frankfurt.apollo.olxcdn.com/v1/files/ua111/image;s={width}x{height}",
        }
    ],
    "user": {
        "id": 55555555,
        "uuid": "dealer-uuid-001",
        "name": "AutoDealer Kyiv",
        "company_name": "AutoDealer SRL",
        "created": "2020-01-10T08:00:00+02:00",
    },
    "contact": {
        "phone": True,
        "chat": True,
    },
    "location": {
        "city": {"id": 100, "name": "Київ", "normalized_name": "kyiv"},
        "region": {"id": 10, "name": "Київська", "normalized_name": "kyivska"},
        "district": {"id": 5, "name": "Шевченківський"},
    },
    "map": {
        "zoom": 14,
        "lat": 50.4501,
        "lon": 30.5234,
        "radius": 0,
        "show_detailed": True,
    },
    "promotion": {
        "highlighted": False,
        "urgent": False,
        "top_ad": False,
    },
    "partner": None,
    "category": {"id": 200, "type": "automotive"},
}

# ---------------------------------------------------------------------------
# All top-level fields from dataset_schema.json
# ---------------------------------------------------------------------------

EXPECTED_FIELDS = {
    'offerId', 'url', 'country', 'title', 'description',
    'price', 'currency', 'priceNegotiable', 'pricePrevious', 'priceConverted',
    'priceCurrencyConverted', 'make', 'model', 'year', 'mileageKm',
    'fuelType', 'transmission', 'bodyType', 'condition', 'engineCapacityCm3',
    'powerHp', 'color', 'vin', 'licensePlate', 'drivetrain', 'steeringWheelSide',
    'doorCount', 'seatCount', 'registrationStatus', 'countryOfOrigin',
    'customsCleared', 'ownersCount', 'co2Emissions',
    'features', 'images', 'promotionFlags',
    'postedAt', 'refreshedAt', 'validTo', 'scrapedAt',
    'paramsRaw', 'seller', 'location',
}

# ---------------------------------------------------------------------------
# Helper: use spider's _make_item()
# ---------------------------------------------------------------------------

def make_item(offer, country, make, scraped_at):
    spider = OlxCarsSpider.__new__(OlxCarsSpider)
    return spider._make_item(
        offer=offer,
        country=country,
        cat_l2_name=make,
        scraped_at=scraped_at,
    )


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def run_tests():
    SCRAPED_AT = datetime.now(tz=timezone.utc).isoformat()
    failures = []

    # ---- Test 1: RO offer ----
    print('=== Test 1: RO offer (BMW X6) ===')
    item_ro = make_item(SAMPLE_OFFER_RO, 'ro', 'BMW', SCRAPED_AT)
    print(f'  offerId:           {item_ro.get("offerId")}')
    print(f'  title:             {item_ro.get("title")}')
    print(f'  description:       {repr(item_ro.get("description", "")[:60])}')
    print(f'  price:             {item_ro.get("price")}')
    print(f'  currency:          {item_ro.get("currency")}')
    print(f'  priceNegotiable:   {item_ro.get("priceNegotiable")}')
    print(f'  pricePrevious:     {item_ro.get("pricePrevious")}')
    print(f'  priceConverted:    {item_ro.get("priceConverted")}')
    print(f'  make:              {item_ro.get("make")}')
    print(f'  model:             {item_ro.get("model")}')
    print(f'  year:              {item_ro.get("year")}')
    print(f'  mileageKm:         {item_ro.get("mileageKm")}')
    print(f'  fuelType:          {item_ro.get("fuelType")}')
    print(f'  transmission:      {item_ro.get("transmission")}')
    print(f'  bodyType:          {item_ro.get("bodyType")}')
    print(f'  condition:         {item_ro.get("condition")}')
    print(f'  engineCapacityCm3: {item_ro.get("engineCapacityCm3")}')
    print(f'  powerHp:           {item_ro.get("powerHp")}')
    print(f'  color:             {item_ro.get("color")}')
    print(f'  doorCount:         {item_ro.get("doorCount")}')
    print(f'  steeringWheelSide: {item_ro.get("steeringWheelSide")}')
    print(f'  registrationStatus:{item_ro.get("registrationStatus")}')
    print(f'  images:            {item_ro.get("images")}')
    print(f'  features:          {item_ro.get("features")}')
    print(f'  paramsRaw len:     {len(item_ro.get("paramsRaw", []))}')
    print(f'  promotionFlags:    {item_ro.get("promotionFlags")}')
    print(f'  postedAt:          {item_ro.get("postedAt")}')
    print(f'  seller:            {item_ro.get("seller")}')
    loc_ro = item_ro.get("location") or {}
    print(f'  location.city:     {loc_ro.get("city", "").encode("ascii", "replace").decode()}')
    print(f'  location.region:   {loc_ro.get("region", "").encode("ascii", "replace").decode()}')
    print(f'  location.lat:      {loc_ro.get("latitude")}')
    print(f'  location.gpsObs:   {loc_ro.get("gpsObfuscated")}')

    # ---- Assertions for RO ----
    assert item_ro['offerId'] == 303514047, f"offerId mismatch: {item_ro['offerId']}"
    assert item_ro['url'].startswith('https://'), f"url bad: {item_ro['url']}"
    assert item_ro['country'] == 'ro', f"country: {item_ro['country']}"
    assert item_ro['title'] == 'Bmw x6 in stare perfecta', f"title: {item_ro['title']}"
    # description: HTML stripped
    assert '<br' not in (item_ro.get('description') or ''), "HTML not stripped from description"
    assert 'BMW X6' in (item_ro.get('description') or ''), f"description content missing: {item_ro.get('description')}"
    assert item_ro['price'] == 52999, f"price: {item_ro['price']}"
    assert item_ro['currency'] == 'EUR', f"currency: {item_ro['currency']}"
    assert item_ro['priceNegotiable'] is False, f"priceNegotiable: {item_ro['priceNegotiable']}"
    assert item_ro['pricePrevious'] == 56000, f"pricePrevious: {item_ro['pricePrevious']}"
    assert item_ro['priceConverted'] == 263000, f"priceConverted: {item_ro['priceConverted']}"
    assert item_ro['priceCurrencyConverted'] == 'RON', f"priceCurrencyConverted: {item_ro['priceCurrencyConverted']}"
    assert item_ro['make'] == 'BMW', f"make: {item_ro['make']}"
    assert item_ro['model'] == 'X6', f"model: {item_ro['model']}"
    assert item_ro['year'] == 2021, f"year: {item_ro['year']}"
    assert item_ro['mileageKm'] == 45000, f"mileageKm: {item_ro['mileageKm']}"
    assert item_ro['fuelType'] == 'diesel', f"fuelType: {item_ro['fuelType']}"
    assert item_ro['transmission'] == 'automatic', f"transmission: {item_ro['transmission']}"
    assert item_ro['bodyType'] == 'suv', f"bodyType: {item_ro['bodyType']}"
    assert item_ro['condition'] == 'used', f"condition: {item_ro['condition']}"
    assert item_ro['engineCapacityCm3'] == 3000, f"engineCapacityCm3: {item_ro['engineCapacityCm3']}"
    assert item_ro['powerHp'] == 285, f"powerHp: {item_ro['powerHp']}"
    assert item_ro['color'] == 'black', f"color: {item_ro['color']}"
    assert item_ro['doorCount'] == 4, f"doorCount: {item_ro['doorCount']}"
    assert item_ro['steeringWheelSide'] == 'lhd', f"steeringWheelSide: {item_ro['steeringWheelSide']}"
    assert item_ro['registrationStatus'] == 'registered', f"registrationStatus: {item_ro['registrationStatus']}"
    # images: 2 photos, 800x600 substituted
    assert len(item_ro['images']) == 2, f"images count: {len(item_ro['images'])}"
    assert '800x600' in item_ro['images'][0], f"image URL not 800x600: {item_ro['images'][0]}"
    assert '{width}' not in item_ro['images'][0], f"template not substituted: {item_ro['images'][0]}"
    # features: empty for RO
    assert item_ro['features'] == [], f"features should be [] for RO: {item_ro['features']}"
    # paramsRaw: all params
    assert len(item_ro['paramsRaw']) == len(SAMPLE_OFFER_RO['params']), f"paramsRaw count mismatch"
    # promotionFlags
    assert item_ro['promotionFlags']['highlighted'] is True, "highlighted should be True"
    assert item_ro['promotionFlags']['topAd'] is True, "topAd should be True"
    assert item_ro['promotionFlags']['urgent'] is False, "urgent should be False"
    # seller
    assert item_ro['seller']['id'] == 12345678, f"seller.id: {item_ro['seller']['id']}"
    assert item_ro['seller']['type'] == 'private', f"seller.type: {item_ro['seller']['type']}"
    assert item_ro['seller']['hasPhone'] is True, f"seller.hasPhone: {item_ro['seller']['hasPhone']}"
    assert item_ro['seller']['hasChat'] is False, f"seller.hasChat: {item_ro['seller']['hasChat']}"
    # location
    assert item_ro['location']['city'] == 'București', f"location.city: {item_ro['location']['city']}"
    assert item_ro['location']['gpsObfuscated'] is True, "gpsObfuscated should be True (show_detailed=False)"
    assert item_ro['location']['latitude'] == 44.4268, f"latitude: {item_ro['location']['latitude']}"
    assert item_ro['location']['district'] is None, f"district should be None for RO: {item_ro['location']['district']}"
    # scrapedAt
    assert item_ro['scrapedAt'] == SCRAPED_AT, f"scrapedAt mismatch"

    print('  [PASS] All RO assertions passed.\n')

    # ---- Test 2: UA offer ----
    print('=== Test 2: UA offer (BMW X5) ===')
    item_ua = make_item(SAMPLE_OFFER_UA, 'ua', 'BMW', SCRAPED_AT)
    print(f'  mileageKm:         {item_ua.get("mileageKm")}  (150 thou = 150000)')
    print(f'  engineCapacityCm3: {item_ua.get("engineCapacityCm3")}  (3.0L = 3000)')
    print(f'  transmission:      {item_ua.get("transmission")}  (546 = automatic)')
    print(f'  color:             {item_ua.get("color")}  (1 = black)')
    print(f'  vin:               {item_ua.get("vin")}')
    print(f'  drivetrain:        {item_ua.get("drivetrain")}')
    print(f'  customsCleared:    {item_ua.get("customsCleared")}')
    print(f'  features:          {item_ua.get("features")}')
    print(f'  doorCount:         {item_ua.get("doorCount")}')
    print(f'  seatCount:         {item_ua.get("seatCount")}')
    print(f'  seller.type:       {item_ua.get("seller", {}).get("type")}')
    print(f'  seller.companyName:{item_ua.get("seller", {}).get("companyName")}')
    district_ua = (item_ua.get("location") or {}).get("district") or ''
    print(f'  location.district: {district_ua.encode("ascii", "replace").decode()}')
    print(f'  location.gpsObfuscated: {item_ua.get("location", {}).get("gpsObfuscated")}')

    assert item_ua['mileageKm'] == 150000, f"UA mileage*1000 failed: {item_ua['mileageKm']}"
    assert item_ua['engineCapacityCm3'] == 3000, f"UA engine litre*1000 failed: {item_ua['engineCapacityCm3']}"
    assert item_ua['transmission'] == 'automatic', f"UA numeric transmission 546: {item_ua['transmission']}"
    assert item_ua['color'] == 'black', f"UA numeric color 1: {item_ua['color']}"
    assert item_ua['vin'] == 'WBAFE81070CY12345', f"UA vin_number: {item_ua['vin']}"
    assert item_ua['drivetrain'] == '4x4', f"UA drive_type: {item_ua['drivetrain']}"
    assert item_ua['customsCleared'] == 'yes', f"UA cleared_customs: {item_ua['customsCleared']}"
    assert 'air_con' in item_ua['features'], f"UA features missing air_con: {item_ua['features']}"
    assert 'park_assist' in item_ua['features'], f"UA features missing park_assist: {item_ua['features']}"
    assert len(item_ua['features']) == 4, f"UA features count: {len(item_ua['features'])}"
    assert item_ua['doorCount'] == 5, f"UA doors_num: {item_ua['doorCount']}"
    assert item_ua['seatCount'] == 5, f"UA seats_num: {item_ua['seatCount']}"
    assert item_ua['seller']['type'] == 'dealer', f"UA seller type (business=True): {item_ua['seller']['type']}"
    assert item_ua['seller']['companyName'] == 'AutoDealer SRL', f"UA company_name: {item_ua['seller']['companyName']}"
    assert item_ua['location']['district'] == 'Шевченківський', f"UA district: {item_ua['location']['district']}"
    assert item_ua['location']['gpsObfuscated'] is False, "UA gpsObfuscated should be False (show_detailed=True)"
    # features must always be a list
    assert isinstance(item_ua['features'], list), "features must be list"
    # images must always be a list
    assert isinstance(item_ua['images'], list), "images must be list"
    assert len(item_ua['images']) == 1, f"UA image count: {len(item_ua['images'])}"
    assert '800x600' in item_ua['images'][0], f"UA image template not substituted: {item_ua['images'][0]}"

    print('  [PASS] All UA assertions passed.\n')

    # ---- Test 3: Check all MANDATORY fields always present ----
    # Nullable fields may be absent when the offer does not have a value for them.
    # What we check here: every field is declared in CarItem (accessible via .fields),
    # and mandatory non-nullable fields are always set.
    MANDATORY_FIELDS = {
        'offerId', 'url', 'country', 'title', 'scrapedAt',
        'features', 'images', 'paramsRaw',
    }
    print('=== Test 3: CarItem declares all dataset_schema.json fields ===')
    item_fields = set(CarItem.fields.keys())
    for field in EXPECTED_FIELDS:
        assert field in item_fields, f"Field {field!r} MISSING from CarItem.fields"
        print(f'  OK  {field}')
    extra_item_fields = item_fields - EXPECTED_FIELDS
    if extra_item_fields:
        print(f'  [WARN] Extra CarItem fields not in schema: {extra_item_fields}')
    print(f'\n  [PASS] All {len(EXPECTED_FIELDS)} fields declared in CarItem.\n')

    print('=== Test 3b: Mandatory fields always set in items ===')
    for field in MANDATORY_FIELDS:
        assert field in item_ro, f"Mandatory field {field!r} missing from RO item"
        assert field in item_ua, f"Mandatory field {field!r} missing from UA item"
        print(f'  OK  {field}')
    print(f'  [PASS] All {len(MANDATORY_FIELDS)} mandatory fields present.\n')

    # ---- Test 4: No extra fields ----
    print('=== Test 4: No extra fields (items.py == dataset_schema.json) ===')
    extra_ro = set(item_ro.keys()) - EXPECTED_FIELDS
    if extra_ro:
        print(f'  [WARN] Extra fields in RO item: {extra_ro}')
        failures.append(f'Extra fields: {extra_ro}')
    else:
        print('  [PASS] No extra fields.\n')

    # ---- Test 5: paramsRaw default (no params) ----
    print('=== Test 5: Empty offer — paramsRaw and features default to [] ===')
    empty_offer = {
        "id": 1,
        "url": "https://www.olx.ro/d/oferta/test-ID1.html",
        "title": "Test",
        "description": "",
        "business": False,
        "params": [],
        "photos": [],
        "user": {"id": 1, "uuid": "x", "name": "Test"},
        "contact": {"phone": False, "chat": False},
        "location": {
            "city": {"id": 1, "name": "Cluj", "normalized_name": "cluj"},
            "region": {"id": 1, "name": "Cluj", "normalized_name": "cluj"},
        },
        "map": {"lat": 46.77, "lon": 23.59, "show_detailed": None},
        "promotion": None,
    }
    item_empty = make_item(empty_offer, 'ro', None, SCRAPED_AT)
    assert item_empty.get('features') == [], f"features must default to []: {item_empty.get('features')}"
    assert item_empty.get('paramsRaw') == [], f"paramsRaw must default to []: {item_empty.get('paramsRaw')}"
    assert item_empty.get('images') == [], f"images must default to []: {item_empty.get('images')}"
    assert item_empty.get('make') is None, f"make should be None when not provided: {item_empty.get('make')}"
    print('  [PASS] Empty offer defaults correct.\n')

    if failures:
        print(f'FAILURES: {failures}')
        sys.exit(1)
    else:
        print('=== ALL TESTS PASSED ===')


if __name__ == '__main__':
    run_tests()
