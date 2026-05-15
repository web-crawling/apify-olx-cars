# OLX Car Listings Scraper - 6 Countries, JSON Output

The OLX Car Listings Scraper extracts vehicle classifieds from six OLX country sites -- Romania (olx.ro), Poland (olx.pl), Bulgaria (olx.bg), Portugal (olx.pt), Ukraine (olx.ua), and Kazakhstan (olx.kz) -- through a single unified JSON output. Filter by brand, year, price range, and currency, or pass pre-filtered OLX search URLs directly. No proxy subscription is required: the actor calls OLX's public `/api/v1/offers/` endpoint with conservative per-domain concurrency.

## Quick Facts

- **What it does:** Scrapes car and vehicle listings from OLX classifieds in six countries.
- **Countries supported:** Romania (olx.ro), Poland (olx.pl), Bulgaria (olx.bg), Portugal (olx.pt), Ukraine (olx.ua), Kazakhstan (olx.kz).
- **Not yet supported:** Brazil (olx.com.br) -- runs on a different stack with Cloudflare protection; a separate actor `apify-olx-cars-br` is on the roadmap.
- **Data source:** OLX's public `/api/v1/offers/` JSON endpoint.
- **Proxy required:** No.
- **Output:** JSON, 50 fields per listing including price, make, model, year, mileage, fuel, transmission, body type, seller info, location, and photo URLs.
- **Throughput:** 40-65 listings per API call; one country's full structured-filter run typically returns up to 1,000 listings before the OLX cap.
- **Coverage past 1,000 results:** automatic brand-level and year-band slicing when `maxItems > 1000`.
- **Authentication:** none required -- runs against public listing endpoints.

## Key Features

- **Multi-country OLX support** -- one actor covers Romania, Poland, Bulgaria, Portugal, Ukraine, and Kazakhstan.
- **Brand and year filtering** -- filter by one or more brands (e.g. `["BMW", "Volkswagen"]`) and year range; brand names are resolved to per-country category IDs automatically.
- **Direct URL input mode** -- pass any pre-filtered OLX search result URL and the actor paginates from there; no need to configure structured filters.
- **Price range filtering** -- filter by `priceFrom`/`priceTo` in any of seven supported currencies.
- **Automatic slicing past the 1,000-result API cap** -- when `maxItems > 1000`, the actor fans out over brand-level and year-band sub-queries to maximise coverage.
- **Normalised vehicle specs** -- `fuelType`, `transmission`, `bodyType`, and `condition` are mapped to consistent English enums across all six countries despite regional API vocabulary differences.
- **50 output fields per listing** -- identification, pricing, technical specs, seller info, location with GPS (obfuscation flagged), photo URLs, raw params pass-through.
- **No proxy required** -- direct datacenter access to OLX's public API.

## Supported Countries

| Country | Domain | Typical currency | Brand map status |
|---------|--------|-----------------|-----------------|
| Romania | olx.ro | EUR, RON | Partial (initial brands; grows quarterly) |
| Poland | olx.pl | PLN | Partial (initial brands; grows quarterly) |
| Bulgaria | olx.bg | BGN | Partial (initial brands; grows quarterly) |
| Portugal | olx.pt | EUR | Not yet built -- brand filter falls back to all cars |
| Ukraine | olx.ua | USD, UAH | Not yet built -- brand filter falls back to all cars |
| Kazakhstan | olx.kz | KZT | Not yet built -- brand filter falls back to all cars |

**Brand map note:** The actor uses a bundled `brand_categories.json` file to resolve brand names to per-country OLX category IDs. RO, PL, and BG have partial maps covering the most common brands. PT, UA, and KZ maps are not yet fully populated -- if you supply a `brands` filter for these countries and the brand is not in the map, the actor logs a warning and falls back to scraping the parent cars category (which is still useful but not brand-filtered). The brand map will be expanded in each quarterly release.

### Country notes

**Romania (olx.ro)** -- The highest-volume OLX car market in CEE with approximately 128,000 active listings. Listings commonly carry both EUR and RON prices. The `registrationStatus` field (registered / unregistered) and `steeringWheelSide` are Romania-specific fields.

**Poland (olx.pl)** -- Large market with PLN pricing. Provides `vin`, `drivetrain`, and `steeringWheelSide` fields not available in all countries. VIN disclosure rate is higher in PL than other markets.

**Bulgaria (olx.bg)** -- Returns comprehensive feature checklists (comfort, multimedia, safety) merged into the `features` array. BG body type data quality is lower than other markets -- body type returns `"other"` for some listings where OLX BG uses the body-type param field for condition flags rather than body shape.

**Portugal (olx.pt)** -- Provides `co2Emissions`, `seatCount`, and `countryOfOrigin` fields. Note: olx.pt hosts cross-listings from standvirtual.com (a sister site). Listings where the offer links out to standvirtual.com are silently skipped; the actor logs a count of skipped offers at run end.

**Ukraine (olx.ua)** -- Mileage is reported by sellers in thousands of km; the actor normalises this to km automatically (e.g. 139 thou = 139,000 km). Engine capacity is reported in litres and normalised to cm3 (e.g. 1.4 L = 1,400 cm3). Provides `drivetrain`, `doorCount`, `seatCount`, `customsCleared` fields.

**Kazakhstan (olx.kz)** -- Provides `ownersCount`. Engine size data quality is inconsistent: some sellers enter the value in litres (e.g. `2`), others in cm3 (e.g. `2300`). The actor returns the value exactly as OLX provides it -- see the Limitations section for details.

## Brazil (olx.com.br) -- Not Available in v1

Brazil is explicitly excluded from this actor. The olx.com.br platform requires Playwright rendering and residential proxy access due to Cloudflare TLS-fingerprint blocking on datacenter IPs. The cost per run would be approximately $800 -- not viable at typical per-result pricing. A dedicated actor (`apify-olx-cars-br`) using Playwright and residential proxy is on the roadmap as a separate product. Do not set `country` to `"br"` -- it is not in the input enum and the actor will reject the input.

## Quick Start

### Scrape BMW listings from Romania

```json
{
  "country": "ro",
  "brands": ["BMW"],
  "maxItems": 50
}
```

### Scrape multiple brands with year and price filters

```json
{
  "country": "pl",
  "brands": ["Toyota", "Honda"],
  "yearFrom": 2018,
  "yearTo": 2023,
  "priceFrom": 5000,
  "priceTo": 20000,
  "priceCurrency": "PLN",
  "maxItems": 200
}
```

### Pass a pre-filtered OLX search URL directly

```json
{
  "startUrls": [
    { "url": "https://www.olx.ro/auto-masini-moto-ambarcatiuni/autoturisme/" }
  ],
  "maxItems": 100
}
```

### Enumerate more than 1,000 listings

```json
{
  "country": "ro",
  "brands": ["Volkswagen"],
  "maxItems": 3000,
  "sortBy": "created_at:desc"
}
```

When `maxItems > 1000`, the actor automatically slices by brand and year band to retrieve more data. Each slice issues separate API requests; run time and compute cost scale proportionally.

## Input Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `startUrls` | array | NO | -- | OLX listing/search URLs. When set, structured filters are ignored (except `maxItems`, `sortBy`). Country auto-inferred from URL. Prefill: `[{"url": "https://www.olx.ro/auto-masini-moto-ambarcatiuni/autoturisme/"}]` (object form, NOT plain string) |
| `country` | enum | NO | `"ro"` | One of `ro, pl, bg, pt, ua, kz`. **No `br`** in v1 |
| `brands` | array | NO | `[]` (all) | Free-text brand names. Resolved at runtime via bundled `brand_categories.json` per country |
| `query` | string | NO | -- | Free-text keyword search |
| `yearFrom` / `yearTo` | integer | NO | -- | Manufacture year range (1900-2099) |
| `priceFrom` / `priceTo` | integer | NO | -- | Price range in `priceCurrency` |
| `priceCurrency` | enum | NO | `"EUR"` | `EUR, RON, PLN, UAH, USD, BGN, KZT` |
| `sortBy` | enum | NO | `"created_at:desc"` | `created_at:desc, filter_float_price:asc, filter_float_price:desc, relevance` |
| `maxItems` | integer | NO | `1000` | Hard ceiling. OLX caps single queries at 1,000; `> 1000` triggers auto brand x year x price slicing |

**Input mode precedence:** `startUrls` wins when provided. All structured filters (`country`, `brands`, `query`, `yearFrom`, `yearTo`, `priceFrom`, `priceTo`, `priceCurrency`) are ignored when `startUrls` is set. Only `maxItems` and `sortBy` apply alongside `startUrls`. A warning is logged if structured filters are set alongside `startUrls`.

**Currency note:** `priceCurrency` must match the listing currency on OLX for the price filter to be effective. EUR is the most interoperable choice across all supported countries. Polish listings are denominated in PLN; Ukrainian listings are typically in USD or UAH; Kazakhstani listings are in KZT.

## Output Data

Every output item is a JSON object. All fields are always present -- fields with no value are `null` (or `[]` for array fields).

### Sample output item

```json
{
  "offerId": 303514047,
  "url": "https://www.olx.ro/d/oferta/bmw-x4-IDkxwRR.html",
  "country": "ro",
  "title": "BMW X4 xDrive20d",
  "description": "BMW X4 in stare foarte buna, full options, service la zi.",
  "price": 19500,
  "currency": "EUR",
  "priceNegotiable": false,
  "pricePrevious": null,
  "priceConverted": null,
  "priceCurrencyConverted": null,
  "make": "BMW",
  "model": "X4",
  "year": 2019,
  "mileageKm": 45000,
  "fuelType": "diesel",
  "transmission": "automatic",
  "bodyType": "suv",
  "condition": "used",
  "engineCapacityCm3": 1998,
  "powerHp": 190,
  "color": "black",
  "vin": null,
  "licensePlate": null,
  "drivetrain": null,
  "steeringWheelSide": "lhd",
  "doorCount": 4,
  "seatCount": null,
  "registrationStatus": "registered",
  "countryOfOrigin": null,
  "customsCleared": null,
  "ownersCount": null,
  "co2Emissions": null,
  "features": [],
  "images": [
    "https://frankfurt.apollo.olxcdn.com/v1/files/abc123/image;s=800x600"
  ],
  "promotionFlags": {
    "highlighted": false,
    "topAd": false,
    "urgent": false
  },
  "postedAt": "2026-05-06T14:31:07+03:00",
  "refreshedAt": "2026-05-15T14:39:20+03:00",
  "validTo": "2026-06-05T14:39:19+03:00",
  "scrapedAt": "2026-05-15T12:00:00Z",
  "paramsRaw": [
    {"key": "petrol", "value": {"key": "diesel", "label": "Diesel"}},
    {"key": "gearbox", "value": {"key": "automatic", "label": "Automat"}}
  ],
  "seller": {
    "id": 12345678,
    "uuid": "abc123-...",
    "name": "Ion P.",
    "companyName": null,
    "type": "private",
    "memberSince": "2019-03-15T10:00:00+02:00",
    "hasPhone": true,
    "hasChat": false
  },
  "location": {
    "city": "Bucuresti",
    "region": "Ilfov",
    "district": null,
    "latitude": 44.4268,
    "longitude": 26.1025,
    "gpsObfuscated": true
  }
}
```

### Output fields reference

| Field | Type | Nullable | Notes |
|-------|------|----------|-------|
| `offerId` | integer | NO | OLX internal numeric offer ID |
| `url` | string | NO | Canonical detail URL |
| `country` | string | NO | Source country code (`ro`, `pl`, `bg`, `pt`, `ua`, `kz`) |
| `title` | string | NO | Raw listing title |
| `description` | string | YES | Plain text; HTML tags stripped |
| `price` | integer | YES | Seller-listed price amount |
| `currency` | string | YES | ISO 4217 currency of `price` |
| `priceNegotiable` | boolean | YES | `true` when seller marks price as negotiable |
| `pricePrevious` | integer | YES | Previous price when seller reduced it |
| `priceConverted` | integer | YES | Price converted to local currency when listed in foreign currency |
| `priceCurrencyConverted` | string | YES | Currency of `priceConverted` |
| `make` | string | YES | Brand name (from category metadata; null in startUrls/parent-cat mode) |
| `model` | string | YES | Model name |
| `year` | integer | YES | Manufacture year |
| `mileageKm` | integer | YES | Mileage in km (UA normalised from thousands) |
| `fuelType` | string | YES | Normalised: `petrol`, `diesel`, `electric`, `hybrid`, `lpg`, `other` |
| `transmission` | string | YES | Normalised: `manual`, `automatic`, `semi-automatic`, `other` |
| `bodyType` | string | YES | Normalised: `sedan`, `suv`, `hatchback`, `estate`, `coupe`, `convertible`, `pickup`, `mpv`, `other` |
| `condition` | string | YES | Normalised: `used`, `new`, `damaged` |
| `engineCapacityCm3` | integer | YES | Engine displacement in cm3 (UA normalised from litres) |
| `powerHp` | integer | YES | Engine power in HP |
| `color` | string | YES | English color slug |
| `vin` | string | YES | VIN number (PL, UA, BG only; when disclosed) |
| `licensePlate` | string | YES | Partially masked plate (PT, UA only) |
| `drivetrain` | string | YES | Drive type raw value (PL, UA only) |
| `steeringWheelSide` | string | YES | `lhd` or `rhd` (RO, PL only) |
| `doorCount` | integer | YES | Number of doors (RO, BG, UA only) |
| `seatCount` | integer | YES | Number of seats (PT, BG, UA only) |
| `registrationStatus` | string | YES | `registered` / `unregistered` (RO only) |
| `countryOfOrigin` | string | YES | Country the car was originally sold in (PL, PT, BG only) |
| `customsCleared` | string | YES | `yes` / `no` (UA only) |
| `ownersCount` | integer | YES | Number of previous owners (KZ only) |
| `co2Emissions` | integer | YES | g/km (PT only) |
| `features` | array[string] | NO | Equipment features; empty array when country doesn't expose checklist |
| `images` | array[string] | NO | Photo URLs at 800x600 resolution |
| `promotionFlags` | object | YES | `{highlighted, topAd, urgent}` paid promotion status |
| `postedAt` | string | YES | ISO 8601 first posting timestamp |
| `refreshedAt` | string | YES | ISO 8601 last bump timestamp |
| `validTo` | string | YES | ISO 8601 ad expiry timestamp |
| `scrapedAt` | string | NO | ISO 8601 UTC scrape timestamp |
| `paramsRaw` | array[object] | NO | Full raw `params[]` from OLX API; empty array when absent |
| `seller.id` | integer | NO | OLX internal user ID |
| `seller.uuid` | string | YES | Opaque seller UUID |
| `seller.name` | string | YES | Display name |
| `seller.companyName` | string | YES | Dealer company name; null for private sellers |
| `seller.type` | string | NO | `private` or `dealer` |
| `seller.memberSince` | string | YES | ISO 8601 account creation date |
| `seller.hasPhone` | boolean | NO | Whether seller accepts phone contact |
| `seller.hasChat` | boolean | NO | Whether OLX in-app chat is enabled |
| `location.city` | string | YES | City name |
| `location.region` | string | YES | Region / county / voivodeship name |
| `location.district` | string | YES | District (PL, UA only) |
| `location.latitude` | float | YES | Approximate GPS latitude |
| `location.longitude` | float | YES | Approximate GPS longitude |
| `location.gpsObfuscated` | boolean | NO | `true` when coordinates are neighbourhood centroid, not exact |

## Use Cases

### Used Car Price Monitoring Across CEE Markets

Track used-car asking prices across Romania, Poland, Bulgaria, and the Balkans on a daily schedule. Configure the actor with `country`, `brands`, and a price band, then run it via [Apify Scheduler](https://docs.apify.com/platform/schedules). Compare each run's `price`, `priceCurrency`, and `pricePrevious` fields to detect price drops and re-listings. The `refreshedAt` timestamp lets you identify bumped listings (sellers re-posting unchanged ads) and exclude them from genuine price-movement analysis.

### Dealer Lead Generation

Identify active car dealers across six OLX markets for B2B outreach. Filter the output stream on `seller.type == "dealer"` and `seller.companyName` to build a deduplicated list of dealership names and locations. Combine with `seller.memberSince` to distinguish established dealers from new entrants. The actor returns `seller.hasPhone` and `seller.hasChat` flags (boolean; phone numbers themselves are not extracted) so you know which dealers accept direct contact.

### Cross-Border Automotive Arbitrage Research

Compare like-for-like vehicle listings between lower-cost markets (Romania, Bulgaria, Ukraine, Kazakhstan) and higher-price markets (Poland, Portugal) to spot import opportunities. Run the actor across multiple countries with the same `brands`, `yearFrom`, `yearTo`, `priceCurrency: "EUR"` configuration. The normalised `make`, `model`, `mileageKm`, `fuelType`, and `bodyType` fields make cross-country joins straightforward; the `priceConverted` / `priceCurrencyConverted` fields handle sellers who already advertise in a foreign currency.

### Vehicle Catalogue and Market-Sizing Studies

Build a catalogue of the active used-car inventory for a brand, segment, or year range. Set `brands` to your target list (e.g. `["BMW", "Audi", "Mercedes-Benz"]`) and `maxItems` to a higher value to trigger the actor's automatic brand-level enumeration -- useful for market-size studies that need broad coverage rather than the 1,000-result single-query cap. The `features` array, `bodyType`, `fuelType`, and `transmission` normalised enums support segmentation without per-country post-processing.

### Resale-Time and Listing-Quality Analysis

Analyse how listing attributes correlate with time-on-market or perceived listing quality. The actor exposes `postedAt`, `refreshedAt`, `validTo`, `promotionFlags` (highlighted, topAd, urgent), `images` (count and CDN URLs), and `description` length -- together a rich feature set for "what makes a car listing sell faster" or "are promoted listings overpriced" studies.

### Feeding LLM and ML Pipelines with Structured Vehicle Data

Use the JSON dataset directly as a training or RAG source for automotive chatbots and pricing models. Every output item is a flat JSON object with 50 well-typed fields (no nested HTML strings; description is plain text with HTML stripped). The actor's dataset can be exported as JSON, CSV, Excel, or pulled via the Apify API for incremental ingestion.

## Pricing

The actor uses a **pay-per-result** model: **$0.001 per listing** (approximately $1 per 1,000 items). You pay only for Apify compute -- no proxy subscription is required. A typical run retrieving 1,000 listings costs approximately $1.00 in compute; a full enumeration run (multiple brand x year slices, 5,000+ listings) costs proportionally more depending on the number of slices required.

For current Apify compute pricing, see [Apify Pricing](https://apify.com/pricing).

## Limitations and Known Issues

**OLX API caps a single unfiltered query at 1,000 results.** One country-wide structured-filter run retrieves at most 1,000 of the approximately 128,000 listings available. The actor logs an INFO message when the cap is hit, explaining how to enumerate more. When `maxItems > 1000`, the actor automatically fans out over brand and year sub-slices to retrieve more data -- this significantly increases run time and compute cost.

**Brazil (olx.com.br) is not supported in v1.** See the Brazil section above. Do not attempt to pass `www.olx.com.br` URLs in `startUrls` -- the domain will not be recognised.

**Phone number is not extracted.** The `seller.hasPhone` field is a boolean indicating whether the seller accepts phone contact. The actual phone number is not returned; it requires a separate authenticated API call. This is tracked for a potential v2 feature.

**PT standvirtual cross-listings are skipped.** Some olx.pt listings link out to standvirtual.com (a sister site in the same OLX group). These offers are silently skipped and a count is logged at run end (e.g. "Skipped 3 offers on olx.pt that link to standvirtual.com"). Genuine olx.pt-native listings are unaffected.

**Brand map is partial for PT, UA, and KZ.** The bundled brand map used to resolve brand names to per-country category IDs is not yet fully populated for Portugal, Ukraine, and Kazakhstan. When a brand is not found in the map for the selected country, the actor logs a warning and falls back to the parent cars category. Brand filtering still works -- it just doesn't restrict to brand-specific sub-category IDs. Full brand maps will be populated before the next major release.

**KZ engine size data quality.** Kazakhstan sellers are inconsistent about whether they enter engine displacement in litres or cm3 in the OLX platform. The actor returns the value as provided by OLX. A listing showing `engineCapacityCm3: 2` likely means the seller entered `2` (intended as 2 litres = 2,000 cm3) rather than a literal 2 cm3. Use `paramsRaw` to inspect the raw value and label from OLX directly.

**`make` field is null in startUrls / parent-category mode.** The `make` field is populated from OLX's category metadata (`cat_l2_name`), which is only present in brand-leaf category responses. When using `startUrls` pointing to a parent category URL (not a brand-specific sub-category), or when a brand is not found in the brand map, `make` will be null. `model` and other fields extracted from per-listing `params` are unaffected.

**GPS coordinates may be obfuscated.** Some sellers hide their exact location. When `location.gpsObfuscated` is `true`, the `latitude` and `longitude` coordinates represent a neighbourhood centroid rather than the exact address.

## Frequently Asked Questions

**What is the OLX Car Listings Scraper?**
The OLX Car Listings Scraper is an Apify actor that extracts car and vehicle listings from OLX classifieds sites in Romania, Poland, Bulgaria, Portugal, Ukraine, and Kazakhstan. It returns structured JSON with 50 fields per listing including price, make, model, year, mileage, fuel type, seller info, and location.

**Which OLX country sites does this actor support?**
Romania (olx.ro), Poland (olx.pl), Bulgaria (olx.bg), Portugal (olx.pt), Ukraine (olx.ua), and Kazakhstan (olx.kz). Pass the `country` parameter to select a country, or use `startUrls` to provide a direct OLX URL -- the country is inferred from the domain automatically.

**Does this actor work with OLX Brazil (olx.com.br)?**
No. Brazil is not in v1. The olx.com.br platform uses a different technical stack with Cloudflare TLS-fingerprint blocking that requires Playwright and residential proxy -- a dedicated `apify-olx-cars-br` actor is planned for the roadmap.

**What car data does the actor extract?**
The actor returns 50 fields grouped into: identification (offerId, url, title, description), pricing (price, currency, priceNegotiable, pricePrevious, priceConverted), vehicle specs (make, model, year, mileageKm, fuelType, transmission, bodyType, condition, engineCapacityCm3, powerHp, color, vin, features), country-specific fields (drivetrain, steeringWheelSide, doorCount, seatCount, registrationStatus, co2Emissions, etc.), seller info, location with GPS, photos, timestamps, and a `paramsRaw` pass-through of all raw API parameters.

**Does this actor return seller phone numbers?**
No. The actor returns `seller.hasPhone` as a boolean only -- `true` means the seller accepts phone contact, but the phone number itself is not extracted in v1. Retrieving the phone number requires a separate authenticated API call.

**Do I need a proxy subscription to run this actor?**
No. The actor calls OLX's public `/api/v1/offers/` endpoint using direct datacenter IP access. No residential or datacenter proxy subscription is required.

**How does the 1,000-result OLX API cap work, and how does this actor handle it?**
OLX's API rejects pagination requests beyond offset 1,000 with HTTP 400. A single unfiltered country-wide query therefore returns at most 1,000 listings. When `maxItems <= 1000`, the actor uses a single paginated query (fast and inexpensive). When `maxItems > 1000`, the actor automatically splits the request into brand-level sub-queries and, where needed, further into year-band and price-band sub-queries. Each sub-slice is paginated independently. This increases run time and cost proportionally but allows retrieval of far more than 1,000 listings.

**Can I filter by car brand, year, and price?**
Yes. Set `brands` to an array of brand names (e.g. `["BMW", "Toyota"]`), `yearFrom`/`yearTo` for year range, and `priceFrom`/`priceTo`/`priceCurrency` for price range. All filters can be combined. Filters are ignored when `startUrls` is provided.

**How do I scrape a pre-filtered OLX search URL?**
Go to the OLX website for your country, apply the filters you want (brand, year, price, etc.) using the site's own interface, then copy the resulting search URL. Paste it as a `{ "url": "..." }` object in the `startUrls` array. The actor will paginate through all results from that pre-filtered URL up to `maxItems`.

**What output formats are supported?**
The actor outputs structured JSON to Apify's dataset. From the Apify console or via the API, you can export as JSON, CSV, Excel (XLSX), or XML. The dataset also integrates with Google Sheets via the Apify Google Sheets integration and any HTTP-based integration via the Apify API.

**Why do fuelType values differ in my results?**
OLX uses country-specific vocabulary for technical attributes (e.g. "benzina" in RO, "benzyna" in PL, "benzinov" in BG, numeric ID 542 in UA). The actor normalises all these to consistent English enums (`petrol`, `diesel`, `electric`, `hybrid`, `lpg`, `other`). If you need the original country-specific value, check the `paramsRaw` field on each listing.

**Is scraping OLX legal?**
The actor scrapes only publicly accessible listing data -- the same data visible to any browser visitor without logging in. Scraping publicly available web data has legal precedent. Review OLX's current Terms of Service for the relevant country domain and ensure your use case complies with applicable data protection laws, including GDPR for EU-based domains (Romania, Poland, Bulgaria, Portugal).

**How fast is the scraper?**
The actor returns 40-65 listings per API call. Concurrency per domain ranges from 4 concurrent requests (Bulgaria, with a 0.25s delay) to 8 concurrent requests (all other countries, with a 0.10s delay). A standard 1,000-listing run typically completes in under 2 minutes. Full-enumeration runs (`maxItems > 1000`) take longer due to the additional sub-query slices.

**Why was Romania chosen as the default country?**
Romania has the highest car-listing volume among the supported countries and the broadest brand coverage in the initial brand map. EUR pricing is common in RO, making it easy to compare prices across European markets without currency conversion. `"ro"` as the default also means the quickest path to a working first run for most users.

## Related Actors

- [eMAG Product Scraper](https://apify.com/extractify-labs/emag-scraper) -- Scrapes product listings from eMAG (Romania, Bulgaria, Hungary), the leading e-commerce marketplace in Eastern Europe

## Changelog

See [.actor/CHANGELOG.md](https://github.com/web-crawling/apify-olx-cars/blob/main/.actor/CHANGELOG.md) for the full release history.

## Support

Report bugs and request features via the [GitHub issue tracker](https://github.com/web-crawling/apify-olx-cars/issues).
