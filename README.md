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
- **Output:** JSON -- 44 always-on top-level fields per listing (price, make, model, year, mileage, fuel, transmission, body type, condition raw slug, seller info, location, photo URLs) plus 5 incremental-mode-only fields when `incrementalMode: true`, plus `extraAttributes`, `priceVsMedianPct`, `priceRating`, and `vinDecoded` when applicable. (`conditionRaw` is absent when the listing has no condition param, but is included when present.)
- **Compact output mode:** Set `outputMode: "compact"` to emit an 18-field subset optimised for LLM/RAG pipelines. See the Output mode section below.
- **Optional VIN enrichment:** Set `enrichVIN: true` to decode 17-character VINs via the free NHTSA vPIC API. Most useful for Poland (40-60% hit rate) and Ukraine (20-40%); other countries rarely disclose VINs.
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
- **History condition filters** -- `excludeDamaged` drops accident/damaged listings client-side; `firstOwnerOnly` keeps only first-owner listings; `serviceBookOnly` (BG-only) keeps only listings with a stamped service book. Each filter applies where OLX exposes the relevant flag (see the per-country support matrix in the Input Parameters section); unsupported countries are skipped silently.
- **Optional VIN decoding via NHTSA vPIC** -- set `enrichVIN: true` to decode 17-character VINs and add a `vinDecoded` sub-object (make, model, engine, body class, plant, trim) from the free NHTSA API. Results are cached cross-run so the same VIN is never decoded twice. Best on Polish and Ukrainian listings where sellers routinely disclose VINs.
- **Within-run fair-price rating** -- `priceVsMedianPct` and `priceRating` computed from the listings in each run; useful when running broad queries where enough comparable listings form a bucket.
- **Country-specific attributes pass-through** -- `extraAttributes` exposes all OLX `params[]` fields not already in top-level output, including door count, engine power, body sub-type, and other locale-specific values.
- **Compact output mode** -- set `outputMode: "compact"` to emit only 18 core fields; reduces output size by ~60% for LLM/RAG pipelines where per-token cost matters. Use `descriptionMaxLength` to truncate or drop the description field in either mode.
- **44 always-on top-level fields per listing** -- identification, pricing, technical specs, seller info, location with GPS (obfuscation flagged), photo URLs, raw params pass-through. Four additional conditionally-present fields (`extraAttributes`, `priceVsMedianPct`, `priceRating`, `conditionRaw`) are included when applicable.
- **No proxy required** -- direct datacenter access to OLX's public API.
- **Incremental monitoring mode** -- opt-in change tracking across runs; emit only new, updated, or missing listings instead of the full dataset every time.
- **Multi-channel notifications** -- opt-in digest of new listings and price drops at run end; delivered to a named Apify KV store (`olx-cars-notifications`) and/or POSTed to any webhook URL (Slack, Discord, Make, n8n, Zapier, or generic HTTP). Requires `incrementalMode: true`.

## How This Compares

The table below compares this actor against alternative options for scraping OLX and similar classified-car sites. Values are based on information publicly available on each actor's Apify Store page at the time of writing; check each actor page for current details.

| Feature | olx-cars (this actor) | OLX product search | Mobile.de | Otomoto | AutoScout24 |
|---|---|---|---|---|---|
| Countries | 6 OLX domains (RO, PL, BG, PT, UA, KZ) | -- | Germany only | Poland only | -- |
| Proxy required | No | -- | -- | -- | -- |
| Output fields | 44 always-on + 5 incremental | -- | -- | -- | -- |
| Compact output mode | Yes (18-field subset) | -- | -- | -- | -- |
| VIN decoding | Yes, via NHTSA vPIC (optional, `enrichVIN: true`) | -- | -- | -- | -- |
| Incremental / change-tracking mode | Yes | -- | -- | -- | -- |
| Price history per listing | Yes | -- | -- | -- | -- |
| Multi-channel notifications / alerts | Slack, Discord, Make, n8n, Zapier (Telegram via relay) | -- | -- | -- | Telegram |
| No authentication required | Yes | -- | -- | -- | -- |

> **Note:** Cells marked `--` could not be verified at time of writing. See each actor's store page for current details.

## Supported Countries

| Country | Domain | Typical currency | Brands mapped |
|---------|--------|-----------------|---------------|
| Romania | olx.ro | EUR, RON | 44 |
| Poland | olx.pl | PLN | 54 |
| Bulgaria | olx.bg | BGN | 74 |
| Portugal | olx.pt | EUR | 52 |
| Ukraine | olx.ua | USD, UAH | 51 |
| Kazakhstan | olx.kz | KZT | 41 |

**Brand map note:** The actor ships with a bundled `brand_categories.json` file that resolves brand names to per-country OLX category IDs across all six countries (316 brand-leaves total). Each country is discovered independently -- OLX taxonomy diverges between domains beyond a small legacy range (for example, Dacia is category `742` on olx.ro but `1347` on olx.pl), so the maps are not shared. Maps are refreshed quarterly via a listing-discovery script; rare brand-leaves that rotate in or out of the listing sample are preserved across refreshes. If you supply a brand name that is not in the map for your selected country, the actor logs a warning listing the recognised brands and falls back to the parent cars category -- brand filtering does not apply in that case, but the rest of the scrape proceeds normally.

### Country notes

**Romania (olx.ro)** -- The highest-volume OLX car market in CEE with approximately 128,000 active listings. Listings commonly carry both EUR and RON prices. The `registrationStatus` field (registered / unregistered) and `steeringWheelSide` are Romania-specific fields. VIN disclosure is rare -- most Romanian listings do not carry a VIN, so `enrichVIN: true` is effectively a no-op for RO.

**Poland (olx.pl)** -- Large market with PLN pricing. Provides `vin`, `drivetrain`, and `steeringWheelSide` fields not available in all countries. VIN disclosure rate is higher in PL than other markets. `enrichVIN: true` produces the richest results here (~40-60% of listings carry a VIN that can be decoded).

**Bulgaria (olx.bg)** -- Returns comprehensive feature checklists (comfort, multimedia, safety) merged into the `features` array. See the Limitations section for a note on body type availability in BG. VIN disclosure is sparse (around 5-10% of listings).

**Portugal (olx.pt)** -- Provides `co2Emissions`, `seatCount`, and `countryOfOrigin` fields. Note: olx.pt hosts cross-listings from standvirtual.com (a sister site). Listings where the offer links out to standvirtual.com are silently skipped; the actor logs a count of skipped offers at run end. VIN disclosure is rare.

**Ukraine (olx.ua)** -- Mileage is reported by sellers in thousands of km; the actor normalises this to km automatically (e.g. 139 thou = 139,000 km). Engine capacity is reported in litres and normalised to cm3 (e.g. 1.4 L = 1,400 cm3). Provides `drivetrain`, `doorCount`, `seatCount`, `customsCleared` fields. VIN is disclosed on around 20-40% of listings; `enrichVIN: true` produces meaningful results here.

**Kazakhstan (olx.kz)** -- Provides `ownersCount`. Engine size data quality is inconsistent: some sellers enter the value in litres (e.g. `2`), others in cm3 (e.g. `2300`). The actor returns the value exactly as OLX provides it -- see the Limitations section for details and a worked example. VIN disclosure is rare.

## VIN Enrichment (Optional)

Use the Apify actor `extractify-labs/olx-cars` with `enrichVIN: true`; for any OLX listing in Poland, Ukraine, Romania, Bulgaria, Portugal, or Kazakhstan where the seller discloses a 17-character VIN, it calls the free NHTSA vPIC API and returns a `vinDecoded` object with make, model, year, engine, body, and plant fields.

When `enrichVIN: true`, the actor validates each listing's `vin` field (17-character ISO 3779 format). For valid VINs, it requests decoded data from the [NHTSA vPIC API](https://vpic.nhtsa.dot.gov/api/) and attaches the result as a `vinDecoded` sub-object on the item. If no valid VIN is present, the item is emitted unchanged with no extra HTTP requests. vPIC results are cached in a persistent Apify KV store (`olx-cars-vin-cache`) across runs -- the same VIN is decoded at most once, regardless of how many runs it appears in.

### VIN disclosure rates by country

| Country | VIN available on OLX | Expected `vinDecoded` hit rate |
|---------|----------------------|-------------------------------|
| Poland (PL) | Yes -- `vin` param; sellers routinely disclose | ~40-60% of listings |
| Ukraine (UA) | Yes -- `vin_number` param; sellers sometimes disclose | ~20-40% of listings |
| Bulgaria (BG) | Sparse -- `vinnomer` param exists but rarely used | ~5-10% |
| Romania (RO) | Rare -- no dedicated VIN param | ~0-5% |
| Portugal (PT) | Rare -- no dedicated VIN param | ~0-5% |
| Kazakhstan (KZ) | Rare | ~0-5% |

For Romania, Portugal, and Kazakhstan, enabling `enrichVIN: true` has no practical effect: no extra HTTP requests are made, and `vinDecoded` will be absent on virtually all items.

### Example: input and output

Input:
```json
{
  "country": "pl",
  "brands": ["BMW"],
  "maxItems": 10,
  "enrichVIN": true
}
```

Output (one item with a decoded VIN, one without):
```json
[
  {
    "offerId": 800123456,
    "country": "pl",
    "make": "BMW",
    "model": "X5",
    "year": 2019,
    "vin": "WBAKV210X0L123456",
    "vinDecoded": {
      "make": "BMW",
      "model": "X5",
      "modelYear": "2019",
      "bodyClass": "Sport Utility Vehicle (SUV)",
      "vehicleType": "MULTIPURPOSE PASSENGER VEHICLE (MPV)",
      "engineCylinders": "6",
      "engineDisplacementCc": "2993",
      "engineHp": "265",
      "fuelTypePrimary": "Diesel",
      "transmissionStyle": "Automatic",
      "driveType": "AWD/All Wheel Drive",
      "plantCountry": "GERMANY",
      "plantCity": "DINGOLFING",
      "plantCompanyName": "BMW AG",
      "manufacturer": "BMW OF NORTH AMERICA, LLC"
    }
  },
  {
    "offerId": 800123457,
    "country": "pl",
    "make": "BMW",
    "model": "3 Series",
    "year": 2015,
    "vin": null
  }
]
```

Note: `series`, `trim`, and `doors` are part of the `vinDecoded` schema but are absent from the example above -- NHTSA does not always carry these fields for EU-market vehicles, and absent fields are dropped rather than set to null.

### Key properties of VIN enrichment

- **Free and requires no API key** -- powered by NHTSA's public vPIC endpoint. No registration or subscription needed.
- **VIN data is cached cross-run** -- once a VIN is decoded, the result is stored in the `olx-cars-vin-cache` KV store. On subsequent runs with the same vehicles, no new vPIC requests are made. First-run time overhead on a 1,000-item PL run with ~50% VIN rate is approximately 1-2 minutes; subsequent runs are faster due to caching.
- **Best-effort enrichment** -- if NHTSA has no record for a VIN (unusual for EU-market production vehicles), the `vinDecoded` field is simply absent on that item -- no error is raised and the OLX scrape completes normally. NHTSA outages are handled the same way (graceful degradation; item emitted without `vinDecoded`).

`vinDecoded` is excluded from `outputMode: compact` to keep LLM-friendly payloads lean. `vinDecoded` is also absent on incremental-mode `MISSING` items (which are derived from the prior-run snapshot, not from a live OLX fetch, so no VIN context is available).

---

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

### Filter out damaged listings

```json
{
  "country": "ro",
  "brands": ["BMW"],
  "excludeDamaged": true,
  "maxItems": 100
}
```

Sets `excludeDamaged: true` to drop listings where OLX flags the vehicle as damaged or accident-repaired. Works on RO, PL, PT, UA, and KZ. For BG, where OLX does not expose a damage flag, the filter is silently skipped. If you expect a significant share of damaged listings, increase `maxItems` to compensate -- see the Limitations section.

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

### Decode VINs on Polish listings

```json
{
  "country": "pl",
  "brands": ["BMW"],
  "maxItems": 100,
  "enrichVIN": true
}
```

Adds `vinDecoded` sub-objects to listings that carry a valid 17-character VIN. Poland has the highest VIN disclosure rate (~40-60%) among the supported countries.

## Input Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `startUrls` | array | NO | `[]` (empty) | Optional. OLX listing/search URLs to paginate directly. When set, structured filters (country, brands, query, year/price ranges, filterByCurrency) are ignored — only `maxItems`, `sortBy`, `sellerType`, `excludeDamaged`, `firstOwnerOnly`, `serviceBookOnly` still apply. Country auto-inferred from URL. Leave empty (the default) to use the structured filters. Entries must be objects of the form `{ "url": "..." }`, not plain strings. |
| `country` | enum | NO | `"ro"` | One of `ro, pl, bg, pt, ua, kz`. **No `br`** in v1 |
| `brands` | array | NO | `[]` (all) | Free-text brand names. Resolved at runtime via bundled `brand_categories.json` per country |
| `query` | string | NO | -- | Free-text keyword search |
| `yearFrom` / `yearTo` | integer | NO | -- | Manufacture year range (1900-2099) |
| `priceFrom` / `priceTo` | integer | NO | -- | Price range in `priceCurrency` |
| `priceCurrency` | enum | NO | `"EUR"` | `EUR, RON, PLN, UAH, USD, BGN, KZT`. When `filterByCurrency` is `true`, only listings in this currency are returned. |
| `filterByCurrency` | boolean | NO | `false` | When `true`, drops listings whose `currency` field does not match `priceCurrency`. Only effective in structured-filter mode -- ignored when `startUrls` is provided. Leave `false` (the default) to receive all listings regardless of listed currency -- the same behaviour as before this option was added. |
| `sellerType` | enum | NO | `"any"` | Filter listings by seller type: `"any"` (default, no filter), `"private"` (private sellers only), `"business"` (dealers/businesses only). Applies in both structured-filter and `startUrls` modes. In `startUrls` mode, an existing `owner_type` value in the URL takes precedence and `sellerType` has no effect. |
| `excludeDamaged` | boolean | NO | `false` | Drop listings flagged as damaged or needs-repairs. Applies on RO/PL/PT/UA/KZ; ignored on BG (no API signal). See the History filter support matrix below. |
| `firstOwnerOnly` | boolean | NO | `false` | Keep only listings flagged as first owner. Applies on BG/UA/KZ; ignored on RO/PL/PT (no API signal). See the History filter support matrix below. |
| `serviceBookOnly` | boolean | NO | `false` | Keep only listings with a stamped service book. Applies on BG; ignored on RO/PL/PT/UA/KZ (no API signal). See the History filter support matrix below. |
| `sortBy` | enum | NO | `"created_at:desc"` | `created_at:desc, filter_float_price:asc, filter_float_price:desc, relevance` |
| `maxItems` | integer | NO | `1000` | Hard ceiling. OLX caps single queries at 1,000; `> 1000` triggers auto brand x year x price slicing |
| `outputMode` | enum | NO | `"full"` | `"full"` returns all available fields (default). `"compact"` returns an 18-field subset optimised for LLM/RAG pipelines. See the Output mode section below. |
| `descriptionMaxLength` | integer | NO | unset | Truncate the `description` field to this many characters. `0` drops the field entirely. Unset = no truncation. Applies in both `full` and `compact` modes. |
| `enrichVIN` | boolean | NO | `false` | When `true`, each listing that carries a valid 17-character VIN is enriched with decoded vehicle data from the free NHTSA vPIC API (make, model, engine specs, plant info, and more). Results are cached cross-run in an Apify KV store (`olx-cars-vin-cache`) so the same VIN is never decoded twice. Most useful for Poland (PL) and Ukraine (UA) where OLX sellers routinely disclose VINs; other countries rarely include a VIN in their listings. vPIC lookup failures are non-fatal -- the listing is emitted without `vinDecoded`. Excluded from compact output mode. |
| `incrementalMode` | boolean | NO | `false` | Enable change tracking across runs. See Incremental Monitoring section. |
| `stateKey` | string | NO | `"olx-cars-state"` | KV store key for the snapshot. Use a unique key per monitoring job. |
| `emitUnchanged` | boolean | NO | `false` | Also emit listings with no tracked-field changes (`changeType: UNCHANGED`). |
| `emitMissing` | boolean | NO | `false` | Emit listings absent from current results (`changeType: MISSING`). Auto-suppressed when `maxItems` truncates the run. |
| `notifyOn` | enum | NO | `"none"` | Controls which events trigger a digest at run end. `"none"` = disabled (no digest built). `"new_listings"` = digest of new listings only. `"price_drops"` = digest of price drops only. `"both"` = new listings and price drops. Requires `incrementalMode: true` -- setting `notifyOn` to anything other than `"none"` while `incrementalMode: false` causes the actor to fail immediately with a clear error message. See the Notifications section. |
| `notifyMinPriceDropPct` | integer (1-99) | NO | `5` | Minimum price reduction percentage vs the prior snapshot price for a listing to qualify as a price-drop event in the digest. Only meaningful when `notifyOn` is `"price_drops"` or `"both"`. Values outside 1-99 are clamped with a WARNING. |
| `notifyTopN` | integer (1-200) | NO | `20` | Maximum number of items in each section (`newItems`, `priceDrops`) of the digest payload. Items are ranked by most-recent `firstSeenAt` (new listings) or highest `priceDropPct` (price drops). Values outside 1-200 are clamped with a WARNING. |
| `notifyWebhookUrl` | string | NO | `""` | Optional HTTPS URL to POST the digest JSON to at run end. Leave empty to disable outbound HTTP. When set, the actor performs a single `Content-Type: application/json` POST. Supports Slack incoming webhooks, Discord webhooks, and any generic HTTP endpoint. POST failure is non-fatal (WARNING only; scrape results are already saved). Keep this URL private -- it is stored in run input history. |
| `pageLimit` | integer (1-50) | NO | `50` | Number of listings to request per OLX API call. OLX's cars endpoint rejects values above 50 with HTTP 400. Lower values produce finer per-page progress logs at the cost of more requests. Default 50 is the maximum and matches prior versions. Only affects request volume -- not which listings are returned. |
| `sliceYearStep` | integer (1-50) | NO | `5` | Width of each year band (in years) used when auto-slicing by year for brand/query result sets that exceed 1,000 visible listings. Smaller values (e.g. 2) give narrower bands and better coverage for densely-listed years. Larger values (e.g. 10) give fewer API calls. Default 5 covers the 1900-2100 range in 40 bands. Only relevant when `maxItems > 1000`. |
| `slicePriceStep` | integer (1000-500000) | NO | `5000` | Width of each price band (in the same currency as `priceCurrency`) used when auto-slicing by price for year-band result sets that still exceed 1,000 visible listings. Smaller values give finer slices; larger values give fewer API calls. Default 5000 gives approximately 100 bands across the 0-500k range. Only relevant when `maxItems > 1000`. |

**Input mode precedence:** `startUrls` wins when provided. The structured filters `country`, `brands`, `query`, `yearFrom`, `yearTo`, `priceFrom`, `priceTo`, `priceCurrency`, and `filterByCurrency` are ignored when `startUrls` is set. `maxItems`, `sortBy`, `sellerType`, `excludeDamaged`, `firstOwnerOnly`, and `serviceBookOnly` apply in both modes. To use the structured filters, leave `startUrls` empty. If both are populated, the actor logs a `WARNING` at the start of the run listing exactly which structured fields were discarded.

**Currency note:** `priceCurrency` labels the currency used for `priceFrom`/`priceTo` values and controls the optional post-filter. OLX's API does not filter by currency server-side -- the numeric price range is applied regardless of denomination, so results may include listings in other currencies whose prices fall in the specified range. To receive only listings in a specific currency, set `filterByCurrency: true` alongside `priceCurrency`. EUR is the most interoperable choice across all supported countries. Polish listings are denominated in PLN; Ukrainian listings are typically in USD or UAH; Kazakhstani listings are in KZT.

### History filter support per country

|  | RO | PL | BG | PT | UA | KZ |
|---|---|---|---|---|---|---|
| `excludeDamaged` | ✅ | ✅ | ⚠️ no signal | ✅ | ✅ | ✅ |
| `firstOwnerOnly` | ❌ no signal | ❌ no signal | ✅ | ❌ no signal | ✅ | ✅ via `ownersCount` |
| `serviceBookOnly` | ❌ no signal | ❌ no signal | ✅ | ❌ no signal | ❌ no signal | ❌ no signal |

Cells marked ❌ or ⚠️ mean OLX does not expose the relevant flag on that country's API. When you set such a filter for an unsupported country, the actor logs an INFO line once per run and the filter is silently skipped -- no listings are dropped and no error is raised. Runs proceed normally.

**Intersection trap on BG:** Bulgarian listings carry exactly one `technical_condition` value per offer (e.g. `"service-book"`, `"first-owner"`, `"technically-upright"`, etc. -- never multiple at once). Combining `serviceBookOnly: true` with `firstOwnerOnly: true` on BG therefore demands both slugs on the same listing, which almost no offer satisfies -- the run will return near-zero items. If you want first-owner-OR-service-book coverage on BG, run the actor twice (once with each filter) and union the results.

## Output mode (compact / LLM-friendly)

Set `outputMode: "compact"` to emit a reduced 18-field subset per listing instead of the full schema. The primary use case is LLM and RAG pipelines where per-token cost scales with output size -- compact mode cuts output volume by roughly 60%.

### Compact fields

`offerId`, `url`, `country`, `title`, `price`, `currency`, `make`, `model`, `year`, `mileageKm`, `fuelType`, `transmission`, `bodyType`, `condition`, `description`, `engineCapacityCm3`, `powerHp`, `color`

These 18 fields cover core identification, pricing, and the vehicle attributes most relevant to car-search and pricing workflows. All other fields are dropped.

### Explicitly excluded from compact

The following field groups are not present in compact output:

- **VIN enrichment** -- `vinDecoded`. The compact slice is optimised for LLM/RAG token-cost reduction; the 18-field sub-object would undermine that goal. Use `outputMode: "full"` if you need `vinDecoded`.
- **FairPrice fields** -- `priceVsMedianPct`, `priceRating`. These require run-wide bucket statistics and are absent by design even when they would otherwise be computed.
- **Incremental tracking** -- `changeType`, `firstSeenAt`, `lastSeenAt`, `priceHistory`, `isRepost`.
- **Nested objects** -- `seller`, `location`.
- **Media and raw pass-through** -- `images`, `paramsRaw`, `extraAttributes`, `promotionFlags`, `conditionRaw`.
- **Country-specific fields** -- `vin`, `licensePlate`, `drivetrain`, `steeringWheelSide`, `doorCount`, `seatCount`, `registrationStatus`, `countryOfOrigin`, `customsCleared`, `ownersCount`, `co2Emissions`, `features`.
- **Timestamps** -- `postedAt`, `refreshedAt`, `validTo`, `scrapedAt`.
- **Pricing extras** -- `priceNegotiable`, `pricePrevious`, `priceConverted`, `priceCurrencyConverted`.

### `descriptionMaxLength`

Controls the maximum character length of the `description` field. Applies in both `full` and `compact` modes regardless of `outputMode`.

- **Positive integer** -- truncates the description to that many characters (character-safe; Python slicing operates on Unicode code points, never cuts mid-character).
- **`0`** -- drops the `description` field entirely from output.
- **Unset (default)** -- no truncation; descriptions are emitted at full length.

Example: `outputMode: "compact"` with `descriptionMaxLength: 300` returns the 18 compact fields with descriptions capped at 300 characters.

### Compact mode with incremental monitoring

When `outputMode: "compact"` is combined with `incrementalMode: true` and `emitMissing: true`, MISSING items emit only the fields that were stored in the snapshot at the time the listing was last seen. The snapshot stores a compact subset of fields for space efficiency; the fields available on MISSING items are typically: `offerId`, `title`, `price`, `currency`, `condition`, `mileageKm`, `firstSeenAt`, `lastSeenAt`, `priceHistory`, `changeType`. After compact filtering, only the intersection with the 18 compact fields remains: `offerId`, `title`, `price`, `currency`, `condition`, `mileageKm`. Fields such as `url`, `country`, `make`, and `model` are not stored in the snapshot and will be absent from compacted MISSING items.

This is a known trade-off of the snapshot design -- if your pipeline requires `url` on MISSING items, use `outputMode: "full"`.

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
  "conditionRaw": "first-owner",
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

The `vinDecoded` field is absent in the example above because `vin` is null. A Polish listing with a disclosed VIN and `enrichVIN: true` would carry an additional field:

```json
"vinDecoded": {
  "make": "BMW",
  "model": "X5",
  "modelYear": "2019",
  "bodyClass": "Sport Utility Vehicle (SUV)",
  "plantCountry": "GERMANY",
  "plantCity": "DINGOLFING",
  "plantCompanyName": "BMW AG",
  "manufacturer": "BMW OF NORTH AMERICA, LLC"
}
```

(Fields absent from the NHTSA response for EU-market VINs -- such as `series`, `trim`, `doors` -- are omitted rather than set to null.)

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
| `conditionRaw` | string | YES | Raw OLX condition slug before normalisation. Scalar on RO/PL/BG/PT/KZ (e.g. `"first-owner"`, `"service-book"`, `"damaged"`, `"used"`); on UA where OLX returns multiple slugs, they are joined with `;` (e.g. `"first-owner;after-accident"`). Absent when the listing has no condition param. Useful when the canonical `condition` field's normalisation (e.g. `first-owner` → `used`) loses information you need. |
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
| `priceRating` | string | YES | Qualitative price rating derived from `priceVsMedianPct`. Values: `very_good` (≤ -15 %), `good` (-15 % to -5 %), `fair` (±5 %), `high` (5 % to 15 %), `very_high` (≥ 15 %). Absent when `priceVsMedianPct` is absent. |
| `vinDecoded` | object | YES | Decoded vehicle data from the NHTSA vPIC API. Present only when `enrichVIN: true` AND the listing carries a valid 17-character VIN AND the vPIC lookup succeeded and returned at least one populated field. Absent otherwise (field omitted, not null). Excluded from `outputMode: compact`. Also absent on incremental `MISSING` items (snapshot-derived; no live VIN context). See the VIN enrichment sub-fields below. |
| `vinDecoded.make` | string | YES | Authoritative OEM make from NHTSA (e.g. `BMW`). May differ from the OLX-derived top-level `make` field -- useful as a cross-check. |
| `vinDecoded.model` | string | YES | Authoritative OEM model (e.g. `X5`). |
| `vinDecoded.modelYear` | string | YES | Model year as a string (e.g. `"2019"`). |
| `vinDecoded.bodyClass` | string | YES | NHTSA body class (e.g. `Sport Utility Vehicle (SUV)`). |
| `vinDecoded.vehicleType` | string | YES | NHTSA vehicle type (e.g. `PASSENGER CAR`, `MULTIPURPOSE PASSENGER VEHICLE (MPV)`). |
| `vinDecoded.engineCylinders` | string | YES | Number of engine cylinders as a string (e.g. `"6"`). |
| `vinDecoded.engineDisplacementCc` | string | YES | Engine displacement in CC as a string (e.g. `"2993"`). |
| `vinDecoded.engineHp` | string | YES | Rated engine power in HP as a string (e.g. `"265"`). |
| `vinDecoded.fuelTypePrimary` | string | YES | Primary fuel type in NHTSA vocabulary (e.g. `Gasoline`, `Diesel`, `Electric`). Note: vocabulary differs from the top-level normalised `fuelType` field. |
| `vinDecoded.transmissionStyle` | string | YES | Transmission style from NHTSA (e.g. `Automatic`, `Manual`). |
| `vinDecoded.driveType` | string | YES | Drive type from NHTSA (e.g. `AWD/All Wheel Drive`, `Front-Wheel Drive`). |
| `vinDecoded.plantCountry` | string | YES | Country where the vehicle was manufactured (e.g. `GERMANY`). |
| `vinDecoded.plantCity` | string | YES | City where the vehicle was manufactured (e.g. `MUNICH`). |
| `vinDecoded.plantCompanyName` | string | YES | Plant operator company name (e.g. `BMW AG`). |
| `vinDecoded.manufacturer` | string | YES | Registered NHTSA manufacturer name (e.g. `BMW OF NORTH AMERICA, LLC`). |
| `vinDecoded.series` | string | YES | Trim series identifier (e.g. `xDrive35i`). |
| `vinDecoded.trim` | string | YES | Variant trim level (e.g. `xLine`, `Sport`). |
| `vinDecoded.doors` | string | YES | Door count from VIN decode as a string (e.g. `"4"`). |

**Note on `vinDecoded` sub-field coverage:** All 18 fields are declared in the schema, but in practice EU-market VINs often populate only a subset. The NHTSA vPIC database is US-centric: plant country/city/company and manufacturer are reliably populated for European production vehicles; model-level fields (series, trim, doors) are less consistently available. Fields that NHTSA returns as empty or "Not Applicable" are omitted from the output rather than set to null. Expect 4-10 populated sub-fields on a typical EU-market VIN rather than all 18.

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

### VIN-Based Vehicle Data Enrichment

Combine OLX listing data with authoritative OEM specifications. Set `enrichVIN: true` and `country: "pl"` (or `"ua"`) to retrieve decoded NHTSA data -- make, model, engine specs, body class, and plant of manufacture -- for listings that disclose a VIN. Use the `vinDecoded.make` and `vinDecoded.model` fields as a cross-check against the OLX-derived `make` and `model` fields to detect data entry errors. Cross-reference `vinDecoded.plantCountry` and `vinDecoded.plantCompanyName` with the seller's asking price for provenance-based pricing studies.

### Feeding LLM and ML Pipelines with Structured Vehicle Data

Use the JSON dataset directly as a training or RAG source for automotive chatbots and pricing models. Every output item is a flat JSON object with well-typed fields (no nested HTML strings; description is plain text with HTML stripped). Set `outputMode: "compact"` and `descriptionMaxLength: 300` to cut output size by ~60% before ingestion -- useful when token cost or context-window size is a constraint. The actor's dataset can be exported as JSON, CSV, Excel, or pulled via the Apify API for incremental ingestion.

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

## Notifications

Notifications is an opt-in feature that builds a structured digest at the end of each run, summarising new listings and price drops detected since the previous run. The digest is written to a persistent Apify key-value store and, optionally, POSTed to a webhook URL of your choice. Use this to set up **car price alerts**, **new listing alerts for OLX**, or **price drop notifications** across Slack, Discord, Telegram (via relay), Make, n8n, Zapier, or any HTTP endpoint.

### Requirements

- **`incrementalMode: true` is required.** See the [Incremental Monitoring](#incremental-monitoring) section above for how to enable it (set `incrementalMode: true` and pick a unique `stateKey` per monitoring job). Setting `notifyOn` to anything other than `"none"` while `incrementalMode: false` causes the actor to exit immediately with the error message: `"notifyOn requires incrementalMode: true. Enable Incremental Mode or set notifyOn to 'none'."` This is a hard fail, not a silent no-op -- the scrape does not start.
- No proxy or authentication is required for the KV store path. The `notifyWebhookUrl` path requires you to supply your own webhook URL.

### Input parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `notifyOn` | `"none"` | Which events trigger a digest. One of: `none` (disabled), `new_listings`, `price_drops`, `both`. |
| `notifyMinPriceDropPct` | `5` | Minimum % price drop vs the prior snapshot for a listing to appear in the `priceDrops` digest array. Integer 1-99; values outside range are clamped. |
| `notifyTopN` | `20` | Maximum items in each digest section (`newItems` and `priceDrops`). Integer 1-200; values outside range are clamped. |
| `notifyWebhookUrl` | `""` | Optional HTTPS URL to POST the digest JSON to at run end. Empty = no outbound HTTP. |

### Digest payload

The digest is a single JSON object. Below is an abbreviated example:

```json
{
  "runId": "abc123",
  "actorId": "YEwcICSxWGYIr368r",
  "runStartedAt": "2026-05-18T10:00:00Z",
  "runFinishedAt": "2026-05-18T10:05:32Z",
  "notifyOn": "both",
  "country": "ro",
  "query": null,
  "brands": ["BMW", "Volkswagen"],
  "startUrlsCount": 0,
  "filters": {
    "yearFrom": 2015,
    "yearTo": 2023,
    "priceFrom": 5000,
    "priceTo": 15000,
    "priceCurrency": "EUR"
  },
  "counts": {
    "new": 12,
    "updated": 34,
    "unchanged": 210,
    "missing": 8,
    "reappeared": 2,
    "total": 256,
    "priceDropsQualified": 5
  },
  "newItems": [
    {
      "offerId": 303514047,
      "url": "https://www.olx.ro/d/oferta/...",
      "title": "BMW X5 3.0d xDrive",
      "price": 9500,
      "currency": "EUR",
      "year": 2017,
      "mileageKm": 145000,
      "make": "BMW",
      "model": "X5",
      "firstSeenAt": "2026-05-18T10:05:00Z"
    }
  ],
  "priceDrops": [
    {
      "offerId": 303400001,
      "url": "https://www.olx.ro/d/oferta/...",
      "title": "VW Golf TDI 2018",
      "priceCurrent": 7200,
      "pricePrevious": 8000,
      "priceDropPct": 10.0,
      "currency": "EUR"
    }
  ],
  "summaryText": "OLX Cars run (ro, notifyOn=both): 12 new, 5 price drops (>=5%)."
}
```

**Key fields:**
- `counts` -- totals by `changeType`. **Note:** counts reflect items that reach the notification pipeline AFTER the incremental diff stage. UNCHANGED items are dropped before reaching the pipeline unless `emitUnchanged: true` is set, so `counts.unchanged` and `counts.total` will be 0 on warm runs with no `emitUnchanged`. NEW, UPDATED, and REAPPEARED counts are always accurate. MISSING is counted when `emitMissing: true`.
- `counts.priceDropsQualified` -- total UPDATED items that passed the `notifyMinPriceDropPct` threshold, regardless of `notifyTopN` truncation.
- `newItems` -- up to `notifyTopN` items sorted by most-recent `firstSeenAt`. Each entry carries: `offerId, url, title, price, currency, year, mileageKm, make, model, firstSeenAt`.
- `priceDrops` -- up to `notifyTopN` items sorted by highest `priceDropPct`. Each entry carries: `offerId, url, title, priceCurrent, pricePrevious, priceDropPct, currency`. Items with an undisclosed price are excluded.
- `summaryText` -- pre-formatted human-readable one-liner, max 280 characters (Telegram-compatible length). Suitable as a direct Slack or Discord message body without custom templating.
- `startUrlsCount` -- scalar count of `startUrls` entries when that input mode was used. The full `startUrls` array is not included (could be very large).

### Where the digest is stored

Every run with `notifyOn != "none"` writes the digest to the **`olx-cars-notifications`** Apify key-value store (a named store, separate from the incremental-state store). Two keys are written:

- **`digest-latest`** -- overwritten every run. Fetch this when you always want the most recent digest.
- **`digest-<runId>`** -- immutable per-run archive. Fetch by `runId` (available in Apify webhook payloads) to retrieve a specific run's digest.

The digest is **not** written to the actor's dataset -- it is structurally incompatible with car-listing items and would break dataset exports.

To find `STORE_ID` for the `olx-cars-notifications` store: Apify console → Storage → Key-value stores → `olx-cars-notifications` → copy the store ID from the URL.

### First-run (cold-start) behaviour

The digest **is emitted on the first run** (cold start), even though the dataset will be empty. On cold start:
- `counts.new` is `0` (all new items are suppressed to build the baseline snapshot).
- `newItems` and `priceDrops` arrays are empty.
- `summaryText` reads: `"OLX Cars baseline run: 0 items emitted (snapshot seeded with N listings). Next run will detect changes."`

This is a positive heartbeat. If you have a Slack or Discord integration, you will see a "baseline run" message on the first run, then real event messages from the second run onward.

### Channel integration recipes

The actor offers two delivery paths. They are independent and can be used simultaneously.

#### Path A -- Apify-native webhook + KV store (recommended, no credentials in actor input)

This path keeps your webhook credentials out of the actor's run input entirely. You configure the integration once in the Apify console.

1. In the Apify console, go to **Settings → Integrations → Add webhook**.
2. Set event: **"Actor run finished"**.
3. Action: **"Fetch a URL"**.
4. URL: `https://api.apify.com/v2/key-value-stores/{STORE_ID}/records/digest-latest?token={API_TOKEN}`
   - Replace `{STORE_ID}` with the store ID of `olx-cars-notifications` (see above).
   - Replace `{API_TOKEN}` with your Apify API token.
5. Forward the fetched JSON to your channel using the integration's built-in HTTP action, or pipe it to Zapier/Make for further routing.

#### Path B -- Direct webhook POST via `notifyWebhookUrl`

Set `notifyWebhookUrl` in your actor input to have the actor POST the digest JSON directly at run end.

##### Slack incoming webhook (direct POST)

```json
{
  "country": "ro",
  "brands": ["BMW"],
  "incrementalMode": true,
  "stateKey": "olx-cars-ro-bmw",
  "notifyOn": "both",
  "notifyWebhookUrl": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX"
}
```

The actor POSTs the raw digest JSON. Slack's incoming webhook endpoint (`https://hooks.slack.com/services/...`) accepts arbitrary JSON but renders only the `text` key as a formatted message. The `summaryText` field maps directly to what Slack would display if the body were `{"text": "..."}`, but the actor sends the full digest object -- Slack will silently ignore all fields except `text` (which is absent in our payload) and show nothing. **For a properly formatted Slack message, use the Apify-native webhook path (Path A) and use Make or Zapier to shape the `summaryText` field into `{"text": "..."}` before forwarding to Slack.**

##### Discord webhook (direct POST)

```json
{
  "notifyOn": "new_listings",
  "notifyWebhookUrl": "https://discord.com/api/webhooks/{WEBHOOK_ID}/{WEBHOOK_TOKEN}"
}
```

Discord's webhook endpoint expects `{"content": "..."}`. The actor sends raw digest JSON. Similar to Slack, Discord will not render the message natively. For a clean Discord message, use the Apify-native webhook path (Path A) and shape `summaryText` into `{"content": summaryText}` in Make or Zapier before posting to Discord.

##### Telegram Bot API (not supported via direct POST)

Telegram's `sendMessage` API endpoint (`https://api.telegram.org/bot{BOT_TOKEN}/sendMessage`) expects a bespoke JSON body: `{"chat_id": ..., "text": ...}`. The actor POSTs the raw digest JSON, which does not match this shape. **Direct `notifyWebhookUrl` to the Telegram Bot API does not work.**

Recommended approach for Telegram:
- **Option 1 (recommended):** Use the Apify-native webhook path (Path A) to read the digest from the KV store, then pipe it through Zapier, Make, or n8n with a "Send Telegram message" step. These platforms have native Telegram actions that accept the `summaryText` field as the message body.
- **Option 2:** Write a small relay server (e.g. a Cloudflare Worker or AWS Lambda) that accepts the raw digest POST and forwards `summaryText` to `api.telegram.org/bot.../sendMessage`.

##### Generic POST / Make / n8n / Zapier

```json
{
  "notifyOn": "price_drops",
  "notifyMinPriceDropPct": 10,
  "notifyTopN": 5,
  "notifyWebhookUrl": "https://hook.us1.make.com/..."
}
```

Make, n8n, and Zapier all handle arbitrary JSON bodies natively. This is the easiest path for custom routing -- the full digest object is available in the workflow for you to parse, filter, and forward as needed.

## Limitations and Known Issues

**OLX API caps a single unfiltered query at 1,000 results.** One country-wide structured-filter run retrieves at most 1,000 of the approximately 128,000 listings available. The actor logs an INFO message when the cap is hit, explaining how to enumerate more. When `maxItems > 1000`, the actor automatically fans out over brand and year sub-slices to retrieve more data -- this significantly increases run time and compute cost.

**Brazil (olx.com.br) is not supported in v1.** See the Brazil section above. Do not attempt to pass `www.olx.com.br` URLs in `startUrls` -- the domain will not be recognised.

**Phone number is not extracted.** The `seller.hasPhone` field is a boolean indicating whether the seller accepts phone contact. The actual phone number is not returned; it requires a separate authenticated API call. This is tracked for a potential v2 feature.

**PT standvirtual cross-listings are skipped.** Some olx.pt listings link out to standvirtual.com (a sister site in the same OLX group). These offers are silently skipped and a count is logged at run end (e.g. "Skipped 3 offers on olx.pt that link to standvirtual.com"). Genuine olx.pt-native listings are unaffected.

**Unmapped brand names fall back to the parent category.** Every country ships with a brand map (41-74 brands per country), but the OLX brand taxonomy is long-tailed -- rare model lines, kit cars, and short-lived marques may not be in the bundled map. When a brand name is not found, the actor logs a warning with the list of recognised brands for that country and falls back to scraping the parent cars category. Brand filtering does not apply for the fallback path, but the rest of the scrape proceeds normally. Brand maps are refreshed quarterly.

**KZ engine size data quality.** Kazakhstan sellers are inconsistent about whether they enter engine displacement in litres or cm3 in the OLX platform. The actor returns the value as provided by OLX without conversion.

A worked example: a listing where the seller typed `2` into the engine-size field will appear in the output as `"engineCapacityCm3": 2` and the raw `paramsRaw` entry will carry the label `"2 см³"`. The seller almost certainly meant 2.0 litres (= 2,000 cm³), not a literal 2 cm³.

Practical guidance for KZ engine-size data:

- **Filter by `engineCapacityCm3 < 50`** to identify rows where the seller entered litres. Reinterpret those values as litres (multiply by 1,000 to get cm³) in your downstream processing.
- **Read `paramsRaw`** and look for the entry whose label contains `"см³"` (Cyrillic for cm³) -- the numeric part of that label is the seller's raw input, which you can parse independently of the normalised field.

**BG body type unavailable.** On `olx.bg`, the `type` parameter used by the OLX API returns condition-state flags (`technically-upright`, `service-book`, `with-mileage`, `with-improvements`) rather than body-shape values. This is a platform-level constraint on olx.bg, not a spider bug. The `BODY_NORMALIZATION` map intentionally has no entry for any of these BG-specific flags, so the normalisation step emits the default value `"other"` for every Bulgarian listing. Treat `bodyType: "other"` on `country: "bg"` as "unknown", not as a literal body-shape classification.

If you need a heuristic body-type classification for BG listings, read the `paramsRaw` field and inspect any entry with `key: "type"`. The condition flags present there can sometimes serve as weak signals (e.g. `"technically-upright"` is more common among sedans and SUVs), but there is no reliable automated mapping. Body type is available and accurate for all other supported countries.

**`make` field is null in startUrls / parent-category mode.** The `make` field is populated from OLX's category metadata (`cat_l2_name`), which is only present in brand-leaf category responses. When using `startUrls` pointing to a parent category URL (not a brand-specific sub-category), or when a brand is not found in the brand map, `make` will be null. `model` and other fields extracted from per-listing `params` are unaffected.

**Fair-price rating coverage depends on listing density.** The `priceVsMedianPct` and `priceRating` fields are computed within each run by bucketing listings on make, model, 5-year year-band, 50,000 km mileage-band, and currency. A bucket must contain at least 5 listings before any item in it receives a rating. In typical single-country single-brand runs, ~40 % of items receive a rating; broader runs (parent cars category, multi-brand) push this higher. Niche models, rare brands on small markets, or runs with fewer than ~20-30 total items may still return few or no rated items. The rating reflects current within-run prices only, not a historical OLX market median.

**History filters drop items client-side and may produce fewer than `maxItems` items.** The `excludeDamaged`, `firstOwnerOnly`, and `serviceBookOnly` filters work by inspecting each listing's raw condition slug after fetching from OLX (no API-level filter is available). Listings are dropped at pipeline priority 150, which fires AFTER the `maxItems` cap at priority 100. As a result, a run with `maxItems: 100` plus any of these filters may yield fewer than 100 output items if some fetched listings were filtered out. To compensate, increase `maxItems` by ~10-30% over your target sample size when using these filters. For example: set `maxItems: 130` to typically land near 100 output items when around 20-25% of listings in your query are damaged.

**`MISSING` incremental items do not receive fair-price fields.** When `emitMissing: true`, items emitted with `changeType: MISSING` come from the prior-run snapshot and may have stale prices. `priceVsMedianPct` and `priceRating` are intentionally absent for MISSING items to avoid comparing stale snapshot prices against the current run's median.

**`extraAttributes` values are in the listing language.** The `extraAttributes` dict passes through OLX param labels as-is: Romanian on olx.ro, Polish on olx.pl, Bulgarian Cyrillic on olx.bg, etc. These are not normalised to English. For the normalised versions of fuel type, transmission, and body type, use the top-level `fuelType`, `transmission`, and `bodyType` fields instead.

**GPS coordinates may be obfuscated.** Some sellers hide their exact location. When `location.gpsObfuscated` is `true`, the `latitude` and `longitude` coordinates represent a neighbourhood centroid rather than the exact address.

**Notifications require `incrementalMode: true`.** Setting `notifyOn` to anything other than `"none"` while `incrementalMode: false` causes the actor to fail with a clear error message before the scrape starts. This is by design -- new-listing and price-drop signals are undefined without a prior-run snapshot to compare against.

**Direct `notifyWebhookUrl` POST to Slack or Discord does not render natively.** The actor POSTs the raw digest JSON. Slack and Discord expect `{"text": "..."}` and `{"content": "..."}` shaped bodies respectively for rendered messages. Use the Apify-native webhook path (Path A in the Notifications section) with Make or Zapier to shape the payload before forwarding.

**Direct `notifyWebhookUrl` POST to Telegram Bot API is not supported.** Telegram's `sendMessage` endpoint requires a bespoke `{"chat_id": ..., "text": ...}` body. Use Zapier, Make, or n8n to relay the digest, or author a small relay server. See the Notifications section for details.

**Notification webhook POST failure does not fail the actor run.** If the outbound HTTP POST to `notifyWebhookUrl` fails, the actor logs a WARNING and the run completes with `SUCCEEDED` status. The digest is still written to the `olx-cars-notifications` KV store. Only the outbound POST is affected.

**Notification KV write failure DOES fail the actor run.** If the actor cannot write the digest to the `olx-cars-notifications` KV store (e.g., transient storage outage), the run is marked `FAILED` via `Actor.fail()`. This asymmetry is intentional: a failed KV write would silently break the user's notification pipeline, while a failed webhook POST is recoverable since the digest is still queryable from KV.

**Compact mode (`outputMode: "compact"`) excludes FairPrice, VIN enrichment, nested objects, media, and incremental fields.** If your workflow uses `vinDecoded`, `priceVsMedianPct`, `priceRating`, `seller`, `location`, `images`, or incremental tracking fields, use `outputMode: "full"` (the default). See the Output mode section for the full field list.

**VIN disclosure is voluntary and varies by country.** Sellers in Romania, Bulgaria, Portugal, and Kazakhstan rarely include a VIN in their OLX listings. Setting `enrichVIN: true` on these countries adds no HTTP overhead (no vPIC requests are made when no VIN is present) but will produce `vinDecoded` on virtually no items. Poland and Ukraine have the highest VIN disclosure rates (20-60% of listings); these are the only markets where `enrichVIN: true` is worth enabling.

**NHTSA vPIC data coverage is sparse for EU-market vehicles.** The NHTSA vPIC database is US-centric. For European production vehicles (which represent the majority of OLX listings), plant country/city/company and manufacturer fields are reliably populated; model/trim/series/doors fields are often absent. In a sample of Polish BMW listings, only 5 of 18 declared sub-fields were populated. `vinDecoded` is not a substitute for a vehicle history service (CARFAX, AutoScout24 Histcheck, etc.) -- it returns static OEM manufacture data from the VIN, not accident history, ownership records, or service history.

**VIN enrichment on incremental `MISSING` items is not supported.** Items emitted with `changeType: MISSING` come from the prior-run snapshot, not from a live OLX fetch. No VIN context is available for re-decoding, so `vinDecoded` is absent on all MISSING items even when `enrichVIN: true`.

## Frequently Asked Questions

**What is the OLX Car Listings Scraper?**
The OLX Car Listings Scraper is an Apify actor that extracts car and vehicle listings from OLX classifieds sites in Romania, Poland, Bulgaria, Portugal, Ukraine, and Kazakhstan. It returns structured JSON with 44 always-on fields per listing including price, make, model, year, mileage, fuel type, seller info, and location. An additional 5 fields are added when `incrementalMode: true`.

**Which OLX country sites does this actor support?**
Romania (olx.ro), Poland (olx.pl), Bulgaria (olx.bg), Portugal (olx.pt), Ukraine (olx.ua), and Kazakhstan (olx.kz). Pass the `country` parameter to select a country, or use `startUrls` to provide a direct OLX URL -- the country is inferred from the domain automatically.

**Does this actor work with OLX Brazil (olx.com.br)?**
No. Brazil is not in v1. The olx.com.br platform uses a different technical stack with Cloudflare TLS-fingerprint blocking that requires Playwright and residential proxy -- a dedicated actor is planned for the roadmap.

**What car data does the actor extract?**
The actor returns 44 always-on fields grouped into: identification (offerId, url, title, description), pricing (price, currency, priceNegotiable, pricePrevious, priceConverted), vehicle specs (make, model, year, mileageKm, fuelType, transmission, bodyType, condition, conditionRaw, engineCapacityCm3, powerHp, color, vin, features), country-specific fields (drivetrain, steeringWheelSide, doorCount, seatCount, registrationStatus, co2Emissions, etc.), seller info, location with GPS, photos, timestamps, and a `paramsRaw` pass-through of all raw API parameters.

**Does this actor return seller phone numbers?**
No. The actor returns `seller.hasPhone` as a boolean only -- `true` means the seller accepts phone contact, but the phone number itself is not extracted in v1. Retrieving the phone number requires a separate authenticated API call.

**Do I need a proxy subscription to run this actor?**
No. The actor calls OLX's public `/api/v1/offers/` endpoint using direct datacenter IP access. No residential or datacenter proxy subscription is required.

**How do I decode VINs from OLX car listings?**
Set `enrichVIN: true` in your input. For any listing in Poland, Ukraine, Romania, Bulgaria, Portugal, or Kazakhstan that carries a valid 17-character VIN, the actor calls the free NHTSA vPIC API and returns a `vinDecoded` sub-object with make, model, year, engine specs, body class, and plant information. Poland and Ukraine have the highest VIN disclosure rates (40-60% and 20-40% respectively). The feature is free and requires no API key. Results are cached across runs so the same VIN is decoded at most once.

**How does the 1,000-result OLX API cap work, and how does this actor handle it?**
OLX's API rejects pagination requests beyond offset 1,000 with HTTP 400. A single unfiltered country-wide query therefore returns at most 1,000 listings. When `maxItems <= 1000`, the actor uses a single paginated query (fast and inexpensive). When `maxItems > 1000`, the actor automatically splits the request into brand-level sub-queries and, where needed, further into year-band and price-band sub-queries. Each sub-slice is paginated independently. This increases run time and cost proportionally but allows retrieval of far more than 1,000 listings.

**Can I filter by car brand, year, and price?**
Yes. Set `brands` to an array of brand names (e.g. `["BMW", "Toyota"]`), `yearFrom`/`yearTo` for year range, and `priceFrom`/`priceTo`/`priceCurrency` for price range. All filters can be combined. Filters are ignored when `startUrls` is provided.

**How do I scrape a pre-filtered OLX search URL?**
Go to the OLX website for your country, apply the filters you want (brand, year, price, etc.) using the site's own interface, then copy the resulting search URL. Paste it as a `{ "url": "..." }` object in the `startUrls` array. The actor will paginate through all results from that pre-filtered URL up to `maxItems`. The country is auto-detected from the hostname -- no additional configuration needed.

**How do I reduce token cost when feeding output to an LLM?**
Set `outputMode: "compact"` to emit only the 18 core fields (`offerId`, `url`, `country`, `title`, `price`, `currency`, `make`, `model`, `year`, `mileageKm`, `fuelType`, `transmission`, `bodyType`, `condition`, `description`, `engineCapacityCm3`, `powerHp`, `color`). This cuts output size by roughly 60% compared to the full schema. You can also set `descriptionMaxLength` (e.g. `300`) to cap long listing descriptions, which are often the largest field by character count. Note: compact mode excludes `vinDecoded`, `priceVsMedianPct`, `priceRating`, `seller`, `location`, and all incremental tracking fields. If you need any of those, use `outputMode: "full"`.

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

**Why am I getting fewer items than `maxItems` when I use `excludeDamaged`, `firstOwnerOnly`, or `serviceBookOnly`?**
These filters are client-side post-filters -- they drop items after the `maxItems` cap is enforced. If you ask for 100 items and 20% are damaged (or non-first-owner, or lack a service book), you will receive approximately 80 output items. Increase `maxItems` to compensate, for example set `maxItems: 130` to typically land near 100 items after filtering. The actor does not raise an error in this situation; it simply outputs fewer items than requested.

**Why does `firstOwnerOnly` only work on some countries?**
OLX exposes a first-owner flag on three of the six supported countries (BG, UA, KZ). The other three (RO, PL, PT) do not surface ownership history in their API responses. When you set `firstOwnerOnly: true` for an unsupported country, the actor logs an INFO message once per run and proceeds without filtering -- no listings are dropped and the run succeeds normally. See the History filter support matrix in the Input Parameters section for the full breakdown.

**Why does `serviceBookOnly` only work on Bulgaria?**
OLX exposes a `service-book` condition flag exclusively on olx.bg (in the `technical_condition` field). The other five supported countries (RO, PL, PT, UA, KZ) do not surface a service-book attribute in their OLX `params[]` response. When you set `serviceBookOnly: true` for an unsupported country, the actor logs an INFO message once per run and proceeds without filtering -- no listings are dropped and the run succeeds normally.

**Why are `priceVsMedianPct` and `priceRating` absent from my output?**
These fields require at least 5 listings in the same bucket (same make, model, 5-year year-band, 50,000 km mileage-band, and currency) within a single run. As of v0.6.0, typical single-country single-brand runs (e.g. BMW in Romania or Poland) rate roughly 40 % of items; broader runs (omit the `brands` filter or include multiple brands) push this higher. Very narrow queries -- a single niche model, a rare brand on a small market, or runs with fewer than ~20-30 total items -- may still return few or no rated items. The fields are also absent for `MISSING` incremental items and for listings where price is undisclosed. Additionally, these fields are always absent when `outputMode: "compact"` is set -- they are excluded from the compact field set by design.

**Why does my first run with incremental mode show 0 items?**
This is expected. The first run with `incrementalMode: true` builds the baseline snapshot and emits nothing to the dataset. Run the actor a second time with the same `stateKey` and it will emit only listings that are new or changed since the first run. See the Incremental Monitoring section for details.

## Related Actors

- [eMAG Product Scraper](https://apify.com/extractify-labs/emag-scraper) -- Scrapes product listings from eMAG (Romania, Bulgaria, Hungary), the leading e-commerce marketplace in Eastern Europe

## Changelog

See [.actor/CHANGELOG.md](https://github.com/web-crawling/apify-olx-cars/blob/main/.actor/CHANGELOG.md) for the full release history.

## Support

Report bugs and request features via the [GitHub issue tracker](https://github.com/web-crawling/apify-olx-cars/issues).

