# OLX Car Listings Scraper - 6 Countries, JSON Output

The OLX Car Listings Scraper extracts vehicle classifieds from six OLX country sites -- Romania (olx.ro), Poland (olx.pl), Bulgaria (olx.bg), Portugal (olx.pt), Ukraine (olx.ua), and Kazakhstan (olx.kz) -- through a single unified JSON output. Filter by brand, year, price range, and currency, or pass pre-filtered OLX search URLs directly. No proxy subscription is required: the actor calls OLX's public `/api/v1/offers/` endpoint with conservative per-domain concurrency.

## Open in AI Assistants

Use this actor in your AI workflow -- paste the actor URL and ask for help:

[![Open in ChatGPT](https://img.shields.io/badge/ChatGPT-Open-74aa9c?logo=openai&logoColor=white)](https://chat.openai.com/?prompt=Scrape%20car%20listings%20from%20OLX%20across%20Romania%2C%20Poland%2C%20Bulgaria%2C%20Portugal%2C%20Ukraine%2C%20and%20Kazakhstan%20using%20the%20extractify-labs%2Folx-cars%20Apify%20actor.%20Show%20me%20how%20to%20call%20it%20and%20parse%20the%20output.)
[![Open in Claude](https://img.shields.io/badge/Claude-Open-d4a853?logo=anthropic&logoColor=white)](https://claude.ai/new?q=Scrape%20car%20listings%20from%20OLX%20across%20Romania%2C%20Poland%2C%20Bulgaria%2C%20Portugal%2C%20Ukraine%2C%20and%20Kazakhstan%20using%20the%20extractify-labs%2Folx-cars%20Apify%20actor.%20Show%20me%20how%20to%20call%20it%20and%20parse%20the%20output.)
[![Open in Perplexity](https://img.shields.io/badge/Perplexity-Open-20808d?logo=perplexity&logoColor=white)](https://www.perplexity.ai/?q=Scrape%20car%20listings%20from%20OLX%20across%20Romania%2C%20Poland%2C%20Bulgaria%2C%20Portugal%2C%20Ukraine%2C%20and%20Kazakhstan%20using%20the%20extractify-labs%2Folx-cars%20Apify%20actor.%20Show%20me%20how%20to%20call%20it%20and%20parse%20the%20output.)
[![Open in Copilot](https://img.shields.io/badge/Copilot-Open-0078d4?logo=microsoft&logoColor=white)](https://copilot.microsoft.com/?q=Scrape%20car%20listings%20from%20OLX%20across%20Romania%2C%20Poland%2C%20Bulgaria%2C%20Portugal%2C%20Ukraine%2C%20and%20Kazakhstan%20using%20the%20extractify-labs%2Folx-cars%20Apify%20actor.%20Show%20me%20how%20to%20call%20it%20and%20parse%20the%20output.)

## Quickstart: Paste a Search URL

The fastest way to start is to paste any OLX cars search URL you already have:

1. Go to the OLX site for your country (e.g. [olx.ro/auto-masini-moto-ambarcatiuni/autoturisme/](https://www.olx.ro/auto-masini-moto-ambarcatiuni/autoturisme/)) and apply filters in the browser (brand, year, price, fuel type, etc.).
2. Copy the URL from the address bar -- for example: `https://www.olx.ro/auto-masini-moto-ambarcatiuni/autoturisme/?search%5Bfilter_float_price%3Afrom%5D=5000&search%5Bfilter_float_price%3Ato%5D=15000`
3. Paste it into the actor's `startUrls` input as a `{ "url": "..." }` object:

```json
{
  "startUrls": [
    { "url": "https://www.olx.ro/auto-masini-moto-ambarcatiuni/autoturisme/?search%5Bfilter_float_price%3Afrom%5D=5000&search%5Bfilter_float_price%3Ato%5D=15000" }
  ],
  "maxItems": 200
}
```

The actor auto-detects the country from the hostname (`olx.ro` → Romania, `olx.pl` → Poland, etc.) and paginates through all results matching your filters up to `maxItems`. No other configuration is needed.

## Quick Facts

- **What it does:** Scrapes car and vehicle listings from OLX classifieds in six countries.
- **Countries supported:** Romania (olx.ro), Poland (olx.pl), Bulgaria (olx.bg), Portugal (olx.pt), Ukraine (olx.ua), Kazakhstan (olx.kz).
- **Not yet supported:** Brazil (olx.com.br) -- runs on a different stack with Cloudflare protection; a separate actor is on the roadmap.
- **Data source:** OLX's public `/api/v1/offers/` JSON endpoint.
- **Proxy required:** No.
- **Output:** JSON -- 43 always-on top-level fields per listing (price, make, model, year, mileage, fuel, transmission, body type, seller info, location, photo URLs) plus 5 incremental-mode-only fields when `incrementalMode: true`, plus `extraAttributes`, `priceVsMedianPct`, and `priceRating` when applicable.
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
- **Seller type filtering** -- narrow results to private sellers (`sellerType: "private"`) or dealers (`sellerType: "business"`); universal across all six countries.
- **Within-run fair-price rating** -- `priceVsMedianPct` and `priceRating` computed from the listings in each run; useful when running broad queries where enough comparable listings form a bucket.
- **Country-specific attributes pass-through** -- `extraAttributes` exposes all OLX `params[]` fields not already in top-level output, including door count, engine power, body sub-type, and other locale-specific values.
- **43 always-on top-level fields per listing** -- identification, pricing, technical specs, seller info, location with GPS (obfuscation flagged), photo URLs, raw params pass-through. Three additional conditionally-present fields (`extraAttributes`, `priceVsMedianPct`, `priceRating`) are included when applicable.
- **No proxy required** -- direct datacenter access to OLX's public API.
- **Incremental monitoring mode** -- opt-in change tracking across runs; emit only new, updated, or missing listings instead of the full dataset every time.

## How This Compares

The table below compares this actor against alternative options for scraping OLX and similar classified-car sites. Values are based on information publicly available on each actor's Apify Store page at the time of writing; check each actor page for current details.

| Feature | olx-cars (this actor) | OLX product search | Mobile.de | Otomoto | AutoScout24 |
|---|---|---|---|---|---|
| Countries | 6 OLX domains (RO, PL, BG, PT, UA, KZ) | — | Germany only | Poland only | — |
| Proxy required | No | — | — | — | — |
| Output fields | 43 always-on + 5 incremental | — | — | — | — |
| Incremental / change-tracking mode | Yes | — | — | — | — |
| Price history per listing | Yes | — | — | — | — |
| No authentication required | Yes | — | — | — | — |

> **Note:** Cells marked `—` could not be verified at time of writing. See each actor's store page for current details.

## Supported Countries

| Country | Domain | Typical currency | Brands mapped |
|---------|--------|-----------------|---------------|
| Romania | olx.ro | EUR, RON | 44 |
| Poland | olx.pl | PLN | 54 |
| Bulgaria | olx.bg | BGN | 74 |
| Portugal | olx.pt | EUR | 52 |
| Ukraine | olx.ua | USD, UAH | 51 |
| Kazakhstan | olx.kz | KZT | 41 |

**Brand map note:** The actor ships with a bundled `brand_categories.json` file that resolves brand names to per-country OLX category IDs across all six countries (316 brand-leaves total). Each country is discovered independently — OLX taxonomy diverges between domains beyond a small legacy range (for example, Dacia is category `742` on olx.ro but `1347` on olx.pl), so the maps are not shared. Maps are refreshed quarterly via a listing-discovery script; rare brand-leaves that rotate in or out of the listing sample are preserved across refreshes. If you supply a brand name that is not in the map for your selected country, the actor logs a warning listing the recognised brands and falls back to the parent cars category — brand filtering does not apply in that case, but the rest of the scrape proceeds normally.

### Country notes

**Romania (olx.ro)** -- The highest-volume OLX car market in CEE with approximately 128,000 active listings. Listings commonly carry both EUR and RON prices. The `registrationStatus` field (registered / unregistered) and `steeringWheelSide` are Romania-specific fields.

**Poland (olx.pl)** -- Large market with PLN pricing. Provides `vin`, `drivetrain`, and `steeringWheelSide` fields not available in all countries. VIN disclosure rate is higher in PL than other markets.

**Bulgaria (olx.bg)** -- Returns comprehensive feature checklists (comfort, multimedia, safety) merged into the `features` array. See the Limitations section for a note on body type availability in BG.

**Portugal (olx.pt)** -- Provides `co2Emissions`, `seatCount`, and `countryOfOrigin` fields. Note: olx.pt hosts cross-listings from standvirtual.com (a sister site). Listings where the offer links out to standvirtual.com are silently skipped; the actor logs a count of skipped offers at run end.

**Ukraine (olx.ua)** -- Mileage is reported by sellers in thousands of km; the actor normalises this to km automatically (e.g. 139 thou = 139,000 km). Engine capacity is reported in litres and normalised to cm3 (e.g. 1.4 L = 1,400 cm3). Provides `drivetrain`, `doorCount`, `seatCount`, `customsCleared` fields.

**Kazakhstan (olx.kz)** -- Provides `ownersCount`. Engine size data quality is inconsistent: some sellers enter the value in litres (e.g. `2`), others in cm3 (e.g. `2300`). The actor returns the value exactly as OLX provides it -- see the Limitations section for details and a worked example.

## Brazil (olx.com.br) -- Not Available in v1

Brazil is explicitly excluded from this actor. The olx.com.br platform requires Playwright rendering and residential proxy access due to Cloudflare TLS-fingerprint blocking on datacenter IPs. The cost per run would be approximately $800 -- not viable at typical per-result pricing. A dedicated actor using Playwright and residential proxy is on the roadmap as a separate product. Do not set `country` to `"br"` -- it is not in the input enum and the actor will reject the input.

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

### Filter by private sellers only

```json
{
  "country": "ro",
  "brands": ["BMW"],
  "sellerType": "private",
  "maxItems": 100
}
```

Set `sellerType` to `"business"` to see only dealer listings instead.

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
| `sellerType` | enum | NO | `"any"` | Filter listings by seller type: `"any"` (default, no filter), `"private"` (private sellers only), `"business"` (dealers/businesses only). Applies in both structured-filter and `startUrls` modes. In `startUrls` mode, an existing `filter_enum_business` value in the URL takes precedence and `sellerType` has no effect. |
| `sortBy` | enum | NO | `"created_at:desc"` | `created_at:desc, filter_float_price:asc, filter_float_price:desc, relevance` |
| `maxItems` | integer | NO | `1000` | Hard ceiling. OLX caps single queries at 1,000; `> 1000` triggers auto brand x year x price slicing |
| `incrementalMode` | boolean | NO | `false` | Enable change tracking across runs. See Incremental Monitoring section. |
| `stateKey` | string | NO | `"olx-cars-state"` | KV store key for the snapshot. Use a unique key per monitoring job. |
| `emitUnchanged` | boolean | NO | `false` | Also emit listings with no tracked-field changes (`changeType: UNCHANGED`). |
| `emitMissing` | boolean | NO | `false` | Emit listings absent from current results (`changeType: MISSING`). Auto-suppressed when `maxItems` truncates the run. |

**Input mode precedence:** `startUrls` wins when provided. All structured filters (`country`, `brands`, `query`, `yearFrom`, `yearTo`, `priceFrom`, `priceTo`, `priceCurrency`) are ignored when `startUrls` is set. Only `maxItems` and `sortBy` apply alongside `startUrls`. A warning is logged if structured filters are set alongside `startUrls`.

**Currency note:** `priceCurrency` must match the listing currency on OLX for the price filter to be effective. EUR is the most interoperable choice across all supported countries. Polish listings are denominated in PLN; Ukrainian listings are typically in USD or UAH; Kazakhstani listings are in KZT.

## Output Data

Every output item is a JSON object. Most fields are always present -- fields with no value are `null` (or `[]` for array fields). Fields that are conditional (incremental-mode fields and the three fair-price / extra-attributes fields) are absent from the item entirely rather than null when they do not apply; see individual field notes.

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
  "extraAttributes": {
    "car_body": "SUV",
    "color": "Negru",
    "door_count": "4",
    "engine_power": "190 CP",
    "gearbox": "Automat"
  },
  "priceVsMedianPct": -12.5,
  "priceRating": "good",
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
| `bodyType` | string | YES | Normalised: `sedan`, `suv`, `hatchback`, `estate`, `coupe`, `convertible`, `pickup`, `mpv`, `other`. Effectively always `"other"` for BG -- see Limitations. |
| `condition` | string | YES | Normalised: `used`, `new`, `damaged` |
| `engineCapacityCm3` | integer | YES | Engine displacement in cm3 (UA normalised from litres; KZ data quality warning -- see Limitations) |
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
| `changeType` | string | YES | Change lifecycle status. Only present when `incrementalMode: true`. Values: `NEW`, `UPDATED`, `UNCHANGED`, `REAPPEARED`, `MISSING`. |
| `firstSeenAt` | string | YES | ISO 8601 UTC. Set once on first observation; immutable. Only present when `incrementalMode: true`. |
| `lastSeenAt` | string | YES | ISO 8601 UTC. Updated each run the listing is present. Not updated for MISSING items. Only present when `incrementalMode: true`. |
| `priceHistory` | array[object] | YES | Per-listing price observations across runs. Only present when `incrementalMode: true`. See Price history section below. |
| `isRepost` | boolean | NO | `true` when `changeType` is `REAPPEARED` (the listing was absent in the prior run and has returned); `false` for all other change types. Only present when `incrementalMode: true`. |
| `extraAttributes` | object | YES | Flat `{key: label}` dict of all OLX `params[]` entries for this listing. Covers country-specific attributes not surfaced as dedicated top-level fields. Keys are OLX param keys; values are the localised label strings as provided by OLX (Romanian on RO, Polish on PL, Bulgarian Cyrillic on BG, etc.). Some keys duplicate top-level fields (e.g. `fuel_type` appears here as a localised label alongside the normalised `fuelType` enum). Absent when `params[]` is empty. |
| `priceVsMedianPct` | number | YES | Percentage deviation of this listing's price from the within-run bucket median. Bucket key: same `make`, `model`, 5-year year-band, 50,000 km mileage-band, and currency. Requires at least 5 listings in the bucket; absent otherwise, or when price is undisclosed, or for `MISSING` incremental items (stale prices excluded). This is a within-run comparison, not a historical market median. Typical single-country single-brand runs rate ~40 % of items; very narrow runs or rare brands may still yield few rated items. |
| `priceRating` | string | YES | Qualitative price rating derived from `priceVsMedianPct`. Values: `very_good` (≤ −15 %), `good` (−15 % to −5 %), `fair` (±5 %), `high` (5 % to 15 %), `very_high` (≥ 15 %). Absent when `priceVsMedianPct` is absent. |

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

Use the JSON dataset directly as a training or RAG source for automotive chatbots and pricing models. Every output item is a flat JSON object with well-typed fields (no nested HTML strings; description is plain text with HTML stripped). The actor's dataset can be exported as JSON, CSV, Excel, or pulled via the Apify API for incremental ingestion.

## Pricing

The actor uses a **pay-per-result** model: **$0.001 per listing** (approximately $1 per 1,000 items). You pay only for Apify compute -- no proxy subscription is required. A typical run retrieving 1,000 listings costs approximately $1.00 in compute; a full enumeration run (multiple brand x year slices, 5,000+ listings) costs proportionally more depending on the number of slices required.

For current Apify compute pricing, see [Apify Pricing](https://apify.com/pricing).

## Incremental Monitoring

Incremental monitoring is an opt-in feature that tracks listing changes across runs. Instead of emitting the full dataset on every run, the actor compares each scraped listing against a persisted snapshot from the previous run and attaches a `changeType` label. Only new, changed, and (optionally) missing listings are emitted by default, which substantially reduces output volume for ongoing monitoring jobs.

### How to enable

1. Set `incrementalMode: true` in your input.
2. Optionally set `stateKey` to a name that identifies your monitoring job (recommended -- see State Key Guidance below).

Minimal example:

```json
{
  "country": "ro",
  "brands": ["BMW"],
  "incrementalMode": true,
  "stateKey": "olx-cars-ro-bmw"
}
```

All other input parameters (`brands`, `yearFrom`, `priceFrom`, etc.) work alongside `incrementalMode` as normal.

### changeType values

| Value | Emitted when | Emitted by default? |
|-------|-------------|---------------------|
| `NEW` | `offerId` not present in previous snapshot | Yes |
| `UPDATED` | In snapshot; at least one of 5 tracked fields changed | Yes |
| `UNCHANGED` | In snapshot; all tracked fields identical | No -- requires `emitUnchanged: true` |
| `REAPPEARED` | Was MISSING in the prior run; back in results now | Yes |
| `MISSING` | In previous snapshot; absent from current results | No -- requires `emitMissing: true` |

When `incrementalMode: false` (the default), `changeType`, `firstSeenAt`, and `lastSeenAt` are absent from output entirely -- not null, simply not present.

### Tracked fields

A listing's `changeType` is set to `UPDATED` when any of the following five fields differ from the stored snapshot value:

- `price` -- the primary monitoring signal
- `currency` -- price comparison is meaningless if the currency changes
- `condition` -- a condition change (e.g. `used` to `damaged`) is a high-value signal
- `mileageKm` -- sellers do update odometer readings when they refresh listings
- `title` -- a title change with an otherwise-identical listing can indicate a relist or rebrand tactic

`images` is explicitly excluded from change tracking: OLX CDN URLs contain rotating tokens and size parameters that change across API responses even when the underlying photos are unchanged. Tracking image URLs would generate constant false-positive UPDATED records.

These five fields are hardcoded in v1. A configurable `trackedFields` parameter is planned for a future release.

### First run behaviour

> **The first run with `incrementalMode: true` emits 0 items.** This is correct and expected. The actor uses that run to build the baseline snapshot (scraping and storing all matching listings in the Apify key-value store). Subsequent runs compare against this baseline and emit only changes. If your first run shows 0 items in the dataset, check the run log for the message "Incremental mode: baseline built -- N listings stored". That confirms everything worked.

Do not set `incrementalMode: true` in the actor's `exampleRunInput` -- Apify's automated QA will flag 0-item runs as failures. Use `incrementalMode: false` (the default) for the example run input.

### State key guidance

The `stateKey` parameter names the entry inside a persistent Apify key-value store (named `olx-cars-incremental-state`) where the snapshot is held between runs. The default key is `"olx-cars-state"`.

**One key per monitoring job.** A monitoring job is a specific combination of country, brand/query, and any other filters that you run on a schedule. If you track Romanian BMWs separately from Portuguese Volkswagens, use two different keys -- they must not share a snapshot.

**Recommended naming convention:** `olx-cars-{country}-{brand}` -- for example:
- `olx-cars-ro-bmw` for Romanian BMWs
- `olx-cars-pt-all` for all Portuguese listings
- `olx-cars-pl-toyota` for Polish Toyotas

Keep names short and readable -- you will see them in the Apify key-value store UI.

**Resetting the baseline.** To discard the existing snapshot and start fresh, change `stateKey` to a new name (e.g. append `-v2`). The next run treats the new key as a cold start and builds a fresh baseline. The old key remains in the KV store and can be deleted manually if no longer needed.

**Do not share keys across unrelated actor runs.** All keys for this actor live in the same named key-value store (`olx-cars-incremental-state`). Reusing a key across runs with different filter parameters (e.g. different `country` or `brands`) will corrupt the baseline and produce misleading change signals.

### Price history

Track price changes over time per listing for arbitrage, dealer-monitoring, and price-watch workflows. When `incrementalMode: true`, each output item includes a `priceHistory` array recording the raw seller price at each change event across runs.

**Element shape:**

| Sub-field | Type | Description |
|-----------|------|-------------|
| `seenAt` | string (ISO 8601) | UTC timestamp when this price was observed (whole-run timestamp, matching `lastSeenAt` precision) |
| `price` | integer | Seller-listed price amount; omitted if undisclosed |
| `currency` | string | ISO 4217 currency code |

**Example:**

```json
"priceHistory": [
  {"seenAt": "2026-05-01T08:00:00+00:00", "price": 12500, "currency": "EUR"},
  {"seenAt": "2026-05-10T08:00:00+00:00", "price": 12000, "currency": "EUR"}
]
```

**Append rule:** a new entry is appended only when `price` or `currency` changes compared to the previous entry. The `priceNegotiable` flag does not trigger an append -- it is seller intent metadata, not a price event. When price is unchanged between runs, no duplicate entry is added.

**Raw price only:** `priceHistory` stores the seller's listed `price` and `currency`, never `priceConverted` or `priceCurrencyConverted`. FX rate fluctuations would otherwise create apparent price-change events on every run even when the seller's ask is unchanged.

**Cap:** the array is capped at 50 entries. When the 51st entry would be added, the oldest entry is evicted (FIFO).

**Behaviour by changeType:**

| `changeType` | `priceHistory` behaviour |
|--------------|--------------------------|
| `NEW` | Single entry seeded at first observation. Item is suppressed on the first (cold-start) run, but the snapshot is seeded so day-2 runs show full history. |
| `UPDATED` | New entry appended (price or currency changed). Full history emitted. |
| `UNCHANGED` | No new entry appended. Full history emitted as-is (only visible when `emitUnchanged: true`). |
| `REAPPEARED` | New entry appended if price/currency differs from the prior snapshot. Full history emitted. |
| `MISSING` | No new entry appended. Full history from snapshot emitted (only visible when `emitMissing: true`). |

**Cold-start and legacy snapshots:** on the first run with a given `stateKey`, `priceHistory` is seeded in the snapshot but the item is suppressed (standard incremental cold-start behaviour). For snapshots created before this feature was deployed, the first post-deploy run seeds a single history entry from the stored price and timestamp -- no data wipe required.

**Practical scale guidance:** each history entry is approximately 60 bytes. At 50 entries per offer and 1,000 tracked offers, the snapshot grows by approximately 3 MB. The Apify key-value store supports up to 9 MB per key. For stateKeys tracking up to about 3,000 offers, the 50-entry cap keeps the snapshot within limits. If you are monitoring a larger query, split it across multiple `stateKey` values. A toggle to disable price history for large-scale use cases is on the v2 roadmap.

### Repost detection

When `incrementalMode: true`, each output item includes an `isRepost` boolean field indicating whether the offer reappeared after a period of absence.

**What it flags:** a seller who removes a listing and reposts the same physical car under the same OLX offer ID (without the offer ID changing) will produce a `changeType: REAPPEARED` event when the offer comes back. `isRepost: true` is set on that item. This is the most common pattern for private sellers gaming OLX's freshness sort by deleting and re-listing.

**Use cases:**

- Filter out artificially fresh listings when building time-on-market studies (exclude `isRepost: true` from "days to sell" calculations).
- Dealer-competitive analysis: track which competitor listings are genuine new stock vs. recycled inventory.

**Behavior by changeType:**

| `changeType` | `isRepost` |
|--------------|-----------|
| `NEW` | `false` |
| `UPDATED` | `false` |
| `UNCHANGED` | `false` |
| `REAPPEARED` | `true` |
| `MISSING` | `false` |

When `incrementalMode: false`, `isRepost` is absent from output entirely -- not null, simply not present.

**v1 limitation:** if a listing is absent for 3 consecutive runs, its entry is purged from the snapshot (see MISSING purge policy under Limitations below). If the same offer ID then returns after purge, it is classified as `NEW` with `isRepost: false` -- the actor has no record to detect the reappearance. In practice this edge case is rare: genuine relists on OLX almost always receive a new offer ID from OLX's platform, so the original offer ID returning after a purge is uncommon. Cross-offerId content matching (detecting relists by vehicle attributes rather than offer ID) is planned for v2.

### Cost savings

With incremental mode, output is limited to listings that are genuinely new or changed since the last run. On OLX car markets, daily listing churn is typically 30-50% (new listings posted, old ones sold or expired). In practice, incremental mode reduces output by 60-90% compared to a full re-scrape, depending on how active the market segment is and how frequently you run. Slower-changing queries (niche brands, narrow year ranges) see higher savings.

Note: the actor currently runs on Apify's standard compute rental tier. Per-result pricing savings translate to reduced dataset size but not yet to per-event billing. This may change in a future release.

### Limitations

- **Snapshot size.** Each entry in the state snapshot is approximately 250 bytes. At 10,000 tracked listings the snapshot is ~2.5 MB; at 30,000 entries it approaches the Apify key-value store's 9 MB per-item limit. If you are monitoring a very large query over many months, split it into multiple monitoring jobs with separate `stateKey` values.

- **MISSING purge policy.** A listing that vanishes from results has its internal `_missingCount` incremented on each subsequent run. After 3 consecutive absences, the entry is purged from the snapshot entirely. This prevents indefinite accumulation of gone listings in the snapshot. A listing that reappears before the purge threshold is marked `REAPPEARED` and its counter is reset.

- **Reposted listings appear as NEW.** When a seller removes a listing and reposts the same car with a new OLX offer ID, the actor has no way to detect the link -- the old offer ID goes MISSING and the new one appears as NEW. Cross-run repost detection (matching by vehicle attributes rather than offer ID) is tracked in [issue #21](https://github.com/web-crawling/apify-olx-cars/issues/21).

- **MISSING detection is suppressed when `maxItems` truncates the run.** If the number of results reaches the `maxItems` ceiling during a run, the actor cannot distinguish "listing absent" from "listing not reached due to the cap". In this case, MISSING emission is suppressed for the entire run and a warning is logged. Increase `maxItems` or narrow your filters to avoid truncation if MISSING detection is important to your use case.

### Examples

**Monitor Romanian BMWs and emit price changes only (default behaviour):**

```json
{
  "country": "ro",
  "brands": ["BMW"],
  "incrementalMode": true,
  "stateKey": "olx-cars-ro-bmw"
}
```

This emits `NEW`, `UPDATED`, and `REAPPEARED` items only. A listing with a changed `price`, `currency`, `condition`, `mileageKm`, or `title` will appear as `UPDATED`.

**Monitor sales -- detect when listings are sold or removed:**

```json
{
  "country": "ro",
  "brands": ["BMW"],
  "incrementalMode": true,
  "stateKey": "olx-cars-ro-bmw",
  "emitMissing": true
}
```

Adding `emitMissing: true` causes the actor to also emit items with `changeType: MISSING` for listings that were in the previous snapshot but absent from the current results. On an active market like OLX Romania, expect 30-50% of tracked listings to appear as MISSING per day.

## Limitations and Known Issues

**OLX API caps a single unfiltered query at 1,000 results.** One country-wide structured-filter run retrieves at most 1,000 of the approximately 128,000 listings available. The actor logs an INFO message when the cap is hit, explaining how to enumerate more. When `maxItems > 1000`, the actor automatically fans out over brand and year sub-slices to retrieve more data -- this significantly increases run time and compute cost.

**Brazil (olx.com.br) is not supported in v1.** See the Brazil section above. Do not attempt to pass `www.olx.com.br` URLs in `startUrls` -- the domain will not be recognised.

**Phone number is not extracted.** The `seller.hasPhone` field is a boolean indicating whether the seller accepts phone contact. The actual phone number is not returned; it requires a separate authenticated API call. This is tracked for a potential v2 feature.

**PT standvirtual cross-listings are skipped.** Some olx.pt listings link out to standvirtual.com (a sister site in the same OLX group). These offers are silently skipped and a count is logged at run end (e.g. "Skipped 3 offers on olx.pt that link to standvirtual.com"). Genuine olx.pt-native listings are unaffected.

**Unmapped brand names fall back to the parent category.** Every country ships with a brand map (41–74 brands per country), but the OLX brand taxonomy is long-tailed — rare model lines, kit cars, and short-lived marques may not be in the bundled map. When a brand name is not found, the actor logs a warning with the list of recognised brands for that country and falls back to scraping the parent cars category. Brand filtering does not apply for the fallback path, but the rest of the scrape proceeds normally. Brand maps are refreshed quarterly.

**KZ engine size data quality.** Kazakhstan sellers are inconsistent about whether they enter engine displacement in litres or cm3 in the OLX platform. The actor returns the value as provided by OLX without conversion.

A worked example: a listing where the seller typed `2` into the engine-size field will appear in the output as `"engineCapacityCm3": 2` and the raw `paramsRaw` entry will carry the label `"2 см³"`. The seller almost certainly meant 2.0 litres (= 2,000 cm³), not a literal 2 cm³.

Practical guidance for KZ engine-size data:

- **Filter by `engineCapacityCm3 < 50`** to identify rows where the seller entered litres. Reinterpret those values as litres (multiply by 1,000 to get cm³) in your downstream processing.
- **Read `paramsRaw`** and look for the entry whose label contains `"см³"` (Cyrillic for cm³) -- the numeric part of that label is the seller's raw input, which you can parse independently of the normalised field.

**BG body type unavailable.** On `olx.bg`, the `type` parameter used by the OLX API returns condition-state flags (`technically-upright`, `service-book`, `with-mileage`, `with-improvements`) rather than body-shape values. This is a platform-level constraint on olx.bg, not a spider bug. The `BODY_NORMALIZATION` map intentionally has no entry for any of these BG-specific flags, so the normalisation step emits the default value `"other"` for every Bulgarian listing. Treat `bodyType: "other"` on `country: "bg"` as "unknown", not as a literal body-shape classification.

If you need a heuristic body-type classification for BG listings, read the `paramsRaw` field and inspect any entry with `key: "type"`. The condition flags present there can sometimes serve as weak signals (e.g. `"technically-upright"` is more common among sedans and SUVs), but there is no reliable automated mapping. Body type is available and accurate for all other supported countries.

**`make` field is null in startUrls / parent-category mode.** The `make` field is populated from OLX's category metadata (`cat_l2_name`), which is only present in brand-leaf category responses. When using `startUrls` pointing to a parent category URL (not a brand-specific sub-category), or when a brand is not found in the brand map, `make` will be null. `model` and other fields extracted from per-listing `params` are unaffected.

**Fair-price rating coverage depends on listing density.** The `priceVsMedianPct` and `priceRating` fields are computed within each run by bucketing listings on make, model, 5-year year-band, 50,000 km mileage-band, and currency. A bucket must contain at least 5 listings before any item in it receives a rating. In typical single-country single-brand runs, ~40 % of items receive a rating; broader runs (parent cars category, multi-brand) push this higher. Niche models, rare brands on small markets, or runs with fewer than ~20–30 total items may still return few or no rated items. The rating reflects current within-run prices only, not a historical OLX market median.

**`MISSING` incremental items do not receive fair-price fields.** When `emitMissing: true`, items emitted with `changeType: MISSING` come from the prior-run snapshot and may have stale prices. `priceVsMedianPct` and `priceRating` are intentionally absent for MISSING items to avoid comparing stale snapshot prices against the current run's median.

**`extraAttributes` values are in the listing language.** The `extraAttributes` dict passes through OLX param labels as-is: Romanian on olx.ro, Polish on olx.pl, Bulgarian Cyrillic on olx.bg, etc. These are not normalised to English. For the normalised versions of fuel type, transmission, and body type, use the top-level `fuelType`, `transmission`, and `bodyType` fields instead.

**GPS coordinates may be obfuscated.** Some sellers hide their exact location. When `location.gpsObfuscated` is `true`, the `latitude` and `longitude` coordinates represent a neighbourhood centroid rather than the exact address.

## Frequently Asked Questions

**What is the OLX Car Listings Scraper?**
The OLX Car Listings Scraper is an Apify actor that extracts car and vehicle listings from OLX classifieds sites in Romania, Poland, Bulgaria, Portugal, Ukraine, and Kazakhstan. It returns structured JSON with 43 always-on fields per listing including price, make, model, year, mileage, fuel type, seller info, and location. An additional 5 fields are added when `incrementalMode: true`.

**Which OLX country sites does this actor support?**
Romania (olx.ro), Poland (olx.pl), Bulgaria (olx.bg), Portugal (olx.pt), Ukraine (olx.ua), and Kazakhstan (olx.kz). Pass the `country` parameter to select a country, or use `startUrls` to provide a direct OLX URL -- the country is inferred from the domain automatically.

**Does this actor work with OLX Brazil (olx.com.br)?**
No. Brazil is not in v1. The olx.com.br platform uses a different technical stack with Cloudflare TLS-fingerprint blocking that requires Playwright and residential proxy -- a dedicated actor is planned for the roadmap.

**What car data does the actor extract?**
The actor returns 43 always-on fields grouped into: identification (offerId, url, title, description), pricing (price, currency, priceNegotiable, pricePrevious, priceConverted), vehicle specs (make, model, year, mileageKm, fuelType, transmission, bodyType, condition, engineCapacityCm3, powerHp, color, vin, features), country-specific fields (drivetrain, steeringWheelSide, doorCount, seatCount, registrationStatus, co2Emissions, etc.), seller info, location with GPS, photos, timestamps, and a `paramsRaw` pass-through of all raw API parameters.

**Does this actor return seller phone numbers?**
No. The actor returns `seller.hasPhone` as a boolean only -- `true` means the seller accepts phone contact, but the phone number itself is not extracted in v1. Retrieving the phone number requires a separate authenticated API call.

**Do I need a proxy subscription to run this actor?**
No. The actor calls OLX's public `/api/v1/offers/` endpoint using direct datacenter IP access. No residential or datacenter proxy subscription is required.

**How does the 1,000-result OLX API cap work, and how does this actor handle it?**
OLX's API rejects pagination requests beyond offset 1,000 with HTTP 400. A single unfiltered country-wide query therefore returns at most 1,000 listings. When `maxItems <= 1000`, the actor uses a single paginated query (fast and inexpensive). When `maxItems > 1000`, the actor automatically splits the request into brand-level sub-queries and, where needed, further into year-band and price-band sub-queries. Each sub-slice is paginated independently. This increases run time and cost proportionally but allows retrieval of far more than 1,000 listings.

**Can I filter by car brand, year, and price?**
Yes. Set `brands` to an array of brand names (e.g. `["BMW", "Toyota"]`), `yearFrom`/`yearTo` for year range, and `priceFrom`/`priceTo`/`priceCurrency` for price range. All filters can be combined. Filters are ignored when `startUrls` is provided.

**How do I scrape a pre-filtered OLX search URL?**
Go to the OLX website for your country, apply the filters you want (brand, year, price, etc.) using the site's own interface, then copy the resulting search URL. Paste it as a `{ "url": "..." }` object in the `startUrls` array. The actor will paginate through all results from that pre-filtered URL up to `maxItems`. The country is auto-detected from the hostname -- no additional configuration needed.

**What output formats are supported?**
The actor outputs structured JSON to Apify's dataset. From the Apify console or via the API, you can export as JSON, CSV, Excel (XLSX), or XML. The dataset also integrates with Google Sheets via the Apify Google Sheets integration and any HTTP-based integration via the Apify API.

**Why do fuelType values differ in my results?**
OLX uses country-specific vocabulary for technical attributes (e.g. "benzina" in RO, "benzyna" in PL, "benzinov" in BG, numeric ID 542 in UA). The actor normalises all these to consistent English enums (`petrol`, `diesel`, `electric`, `hybrid`, `lpg`, `other`). If you need the original country-specific value, check the `paramsRaw` field on each listing.

**Is scraping OLX legal?**
The actor scrapes only publicly accessible listing data -- the same data visible to any browser visitor without logging in. Scraping publicly available web data has legal precedent. Review OLX's current Terms of Service for the relevant country domain and ensure your use case complies with applicable data protection laws, including GDPR for EU-based domains (Romania, Poland, Bulgaria, Portugal).

**How fast is the scraper?**
The actor returns 40-65 listings per API call. Concurrency per domain ranges from 4 concurrent requests (Bulgaria, with a 0.25s delay) to 8 concurrent requests (all other countries, with a 0.10s delay). A standard 1,000-listing run typically completes in under 2 minutes. Full-enumeration runs (`maxItems > 1000`) take longer due to the additional sub-query slices.

**Why was Romania chosen as the default country?**
Romania has the highest car-listing volume among the supported countries (approximately 128,000 active listings) and EUR pricing is common in RO, which makes it easy to compare prices across European markets without currency conversion. `"ro"` as the default also means the quickest path to a working first run for most users.

**Why are `priceVsMedianPct` and `priceRating` absent from my output?**
These fields require at least 5 listings in the same bucket (same make, model, 5-year year-band, 50,000 km mileage-band, and currency) within a single run. As of v0.6.0, typical single-country single-brand runs (e.g. BMW in Romania or Poland) rate roughly 40 % of items; broader runs (omit the `brands` filter or include multiple brands) push this higher. Very narrow queries -- a single niche model, a rare brand on a small market, or runs with fewer than ~20–30 total items -- may still return few or no rated items. The fields are also absent for `MISSING` incremental items and for listings where price is undisclosed.

**Why does my first run with incremental mode show 0 items?**
This is expected. The first run with `incrementalMode: true` builds the baseline snapshot and emits nothing to the dataset. Run the actor a second time with the same `stateKey` and it will emit only listings that are new or changed since the first run. See the Incremental Monitoring section for details.

## Related Actors

- [eMAG Product Scraper](https://apify.com/extractify-labs/emag-scraper) -- Scrapes product listings from eMAG (Romania, Bulgaria, Hungary), the leading e-commerce marketplace in Eastern Europe

## Changelog

See [.actor/CHANGELOG.md](https://github.com/web-crawling/apify-olx-cars/blob/main/.actor/CHANGELOG.md) for the full release history.

## Support

Report bugs and request features via the [GitHub issue tracker](https://github.com/web-crawling/apify-olx-cars/issues).
