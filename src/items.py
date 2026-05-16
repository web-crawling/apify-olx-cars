"""Scrapy items module for OLX Cars actor.

Defines CarItem with all 43 top-level output fields.
Every field declared here must also appear in .actor/dataset_schema.json
(and vice-versa) — config-implementer owns that contract.

Field naming follows dataset_schema.json exactly (camelCase).
Nested objects (seller, location) are stored as plain Python dicts
and populated by CarItemLoader with TakeFirst() output processor.
Array fields (images, features, paramsRaw) use Identity() output processor
in CarItemLoader so the full list is preserved.
"""

import scrapy


class CarItem(scrapy.Item):
    # --- Identity fields -------------------------------------------------------
    offerId = scrapy.Field()               # int: OLX internal numeric offer ID
    url = scrapy.Field()                   # str: canonical listing URL
    country = scrapy.Field()               # str: source country code (ro/pl/bg/pt/ua/kz)
    title = scrapy.Field()                 # str: raw seller title

    # --- Description -----------------------------------------------------------
    description = scrapy.Field()           # str: plain-text (HTML stripped by loader)

    # --- Price fields ----------------------------------------------------------
    price = scrapy.Field()                 # int|None: seller-listed price amount
    currency = scrapy.Field()              # str|None: ISO 4217 currency of price
    priceNegotiable = scrapy.Field()       # bool|None: negotiable flag
    pricePrevious = scrapy.Field()         # int|None: previous price before reduction
    priceConverted = scrapy.Field()        # int|None: price in local currency
    priceCurrencyConverted = scrapy.Field()# str|None: currency of priceConverted

    # --- Vehicle identity ------------------------------------------------------
    make = scrapy.Field()                  # str|None: brand from cat_l2_name
    model = scrapy.Field()                 # str|None: model from params
    year = scrapy.Field()                  # int|None: manufacture year

    # --- Mechanical specs ------------------------------------------------------
    mileageKm = scrapy.Field()             # int|None: odometer in km (normalised)
    fuelType = scrapy.Field()              # str|None: normalised enum
    transmission = scrapy.Field()          # str|None: normalised enum
    bodyType = scrapy.Field()              # str|None: normalised enum
    condition = scrapy.Field()             # str|None: normalised enum
    engineCapacityCm3 = scrapy.Field()     # int|None: engine displacement in cm³
    powerHp = scrapy.Field()               # int|None: engine power in HP

    # --- Additional specs (country-specific) -----------------------------------
    color = scrapy.Field()                 # str|None: English slug or None
    vin = scrapy.Field()                   # str|None: VIN (PL/UA/BG only)
    licensePlate = scrapy.Field()          # str|None: partially masked (PT/UA only)
    drivetrain = scrapy.Field()            # str|None: drive type (PL/UA only)
    steeringWheelSide = scrapy.Field()     # str|None: lhd/rhd (RO/PL only)
    doorCount = scrapy.Field()             # int|None: door count (RO/BG/UA only)
    seatCount = scrapy.Field()             # int|None: seat count (PT/BG/UA only)
    registrationStatus = scrapy.Field()    # str|None: registered/unregistered (RO only)
    countryOfOrigin = scrapy.Field()       # str|None: origin country (PL/PT/BG only)
    customsCleared = scrapy.Field()        # str|None: yes/no (UA only)
    ownersCount = scrapy.Field()           # int|None: number of owners (KZ only)
    co2Emissions = scrapy.Field()          # int|None: g/km (PT only)

    # --- Array fields (Identity() output processor in loader) ------------------
    features = scrapy.Field()              # list[str]: equipment keys; always [] if absent
    images = scrapy.Field()                # list[str]: 800x600 CDN URLs; always []
    paramsRaw = scrapy.Field()             # list[dict]: full params passthrough; always []

    # --- Promotion / metadata --------------------------------------------------
    promotionFlags = scrapy.Field()        # dict|None: {highlighted, topAd, urgent}

    # --- Timestamps ------------------------------------------------------------
    postedAt = scrapy.Field()              # str|None: ISO 8601 first-posted timestamp
    refreshedAt = scrapy.Field()           # str|None: ISO 8601 last-bump timestamp
    validTo = scrapy.Field()               # str|None: ISO 8601 expiry timestamp
    scrapedAt = scrapy.Field()             # str: ISO 8601 UTC scrape timestamp

    # --- Nested objects (TakeFirst() of a dict) --------------------------------
    seller = scrapy.Field()                # dict: seller profile sub-object
    location = scrapy.Field()              # dict: geographic location sub-object

    # --- Incremental change tracking (incrementalMode only) -------------------
    changeType = scrapy.Field()    # str|None: NEW/UPDATED/UNCHANGED/REAPPEARED/MISSING
    firstSeenAt = scrapy.Field()   # str|None: ISO 8601 UTC — when listing first entered state
    lastSeenAt = scrapy.Field()    # str|None: ISO 8601 UTC — when listing last seen in results
    priceHistory = scrapy.Field()  # list[dict]|None: price history entries; incrementalMode only
