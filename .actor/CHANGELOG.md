# Changelog

## v1.2.0 -- 2026-05-18

### Added
- **`filterByCurrency` input** (boolean, default `false`) -- opt-in post-filter that drops
  listings whose `currency` does not match `priceCurrency`. Without this flag, OLX's price
  range filters operate on raw numeric values regardless of currency, so users targeting
  EUR results on non-EUR countries could receive mixed-currency listings. No effect when
  `startUrls` is provided. Default `false` preserves existing behaviour exactly.
  Closes [#14](https://github.com/web-crawling/apify-olx-cars/issues/14).

- **`pageLimit` input** (integer 1-65, default `50`) -- listings requested per OLX API call.
  Raise to 65 to cut API request count by ~30% at the same `maxItems`. Default 50 is unchanged.

- **`sliceYearStep` input** (integer 1-50, default `5`) -- year-band width when auto-slicing
  broad result sets (only active when `maxItems > 1000`). Smaller = more, narrower slices.

- **`slicePriceStep` input** (integer 1000-500000, default `5000`) -- price-band width in
  the same currency as `priceCurrency` when auto-slicing (only active when `maxItems > 1000`).
  Smaller = finer slices.

### Notes
- `pageLimit`, `sliceYearStep`, and `slicePriceStep` are grouped under a new
  "Advanced -- Slicing (rarely needed)" section in the actor's input form. Default values
  preserve existing behaviour exactly -- no changes needed for current users.
- Closes [#16](https://github.com/web-crawling/apify-olx-cars/issues/16).

## v1.1.0 -- 2026-05-18

### Added
- **Optional VIN enrichment via NHTSA vPIC** -- set `enrichVIN: true` to decode 17-character
  VINs and attach a `vinDecoded` sub-object (make, model, year, engine specs, body class, plant,
  trim) using the free NHTSA vPIC API. No API key required. Results are cached cross-run in
  a dedicated Apify KV store (`olx-cars-vin-cache`) so the same VIN is never decoded twice.
  Best on Poland (40-60% listing hit rate) and Ukraine (20-40%); other countries rarely disclose
  VINs on OLX. vPIC failures are non-fatal -- the listing is emitted without `vinDecoded` and
  the OLX scrape completes normally. `vinDecoded` contains up to 18 sub-fields: `make`, `model`,
  `modelYear`, `bodyClass`, `vehicleType`, `engineCylinders`, `engineDisplacementCc`, `engineHp`,
  `fuelTypePrimary`, `transmissionStyle`, `driveType`, `plantCountry`, `plantCity`,
  `plantCompanyName`, `manufacturer`, `series`, `trim`, `doors` (all strings; absent fields
  omitted rather than null). `vinDecoded` is excluded from `outputMode: compact` and from
  incremental `MISSING` items. Closes
  [#19](https://github.com/web-crawling/apify-olx-cars/issues/19).

## v1.0.0 -- 2026-05-18

### Added
- **Compact output mode** -- set `outputMode: "compact"` to emit only 18 core fields
  (`offerId`, `url`, `country`, `title`, `price`, `currency`, `make`, `model`, `year`,
  `mileageKm`, `fuelType`, `transmission`, `bodyType`, `condition`, `description`,
  `engineCapacityCm3`, `powerHp`, `color`) instead of the full schema. Reduces output
  size by roughly 60%, which cuts token cost and context-window usage for LLM/RAG
  pipelines.
- **`descriptionMaxLength` input** -- truncate or drop the `description` field on any
  run. Set to a positive integer to cap descriptions at that many characters; set to `0`
  to drop the field entirely; leave unset for no truncation. Applies in both `full` and
  `compact` output modes.

### Notes
- `priceVsMedianPct` and `priceRating` are excluded from compact output by design --
  they require run-wide bucket statistics and are not meaningful in a reduced-field context.
- Incremental tracking fields (`changeType`, `firstSeenAt`, `lastSeenAt`, `priceHistory`,
  `isRepost`) and nested objects (`seller`, `location`) are also excluded from compact.
- Closes [#24](https://github.com/web-crawling/apify-olx-cars/issues/24).

## v0.9.0 — 2026-05-18

### Added
- **Multi-channel notifications** — new opt-in digest feature for incremental-mode runs.
  Enable via the new `notifyOn` input (`"none"` / `"new_listings"` / `"price_drops"` / `"both"`;
  default `"none"`). When enabled, the actor builds a structured digest at run end and writes
  it to the persistent `olx-cars-notifications` Apify key-value store under two keys:
  `digest-latest` (overwritten each run) and `digest-<runId>` (immutable per-run archive).
  Optionally POST the same digest JSON to any HTTP endpoint via the new `notifyWebhookUrl`
  input — supports Slack incoming webhooks, Discord webhooks, Make/n8n/Zapier, and any
  generic HTTPS endpoint. Telegram direct POST requires a relay (see README).

- **`notifyOn`** (enum string, default `"none"`) — controls which events trigger a digest:
  `new_listings` (new listings only), `price_drops` (price drops only), `both`
  (new listings and price drops). Setting `notifyOn != "none"` without
  `incrementalMode: true` causes the actor to fail immediately with a clear error message.

- **`notifyMinPriceDropPct`** (integer 1–99, default `5`) — minimum price reduction
  percentage vs the prior-run snapshot price for a listing to appear in the digest's
  `priceDrops` array. Values outside 1–99 are clamped with a WARNING.

- **`notifyTopN`** (integer 1–200, default `20`) — maximum number of items in each digest
  section (`newItems` and `priceDrops`). New listings are ranked by most-recent `firstSeenAt`;
  price drops are ranked by highest `priceDropPct`. Values outside 1–200 are clamped.

- **`notifyWebhookUrl`** (string, default `""`) — optional HTTPS URL to POST the digest
  JSON to at run end. POST failure is non-fatal (WARNING only; the digest is still saved to
  the KV store). Keep the URL private — it is stored in run input history.

### Notes
- The digest is **not** written to the actor dataset. It lands exclusively in the
  `olx-cars-notifications` named KV store, keeping the car-listing dataset homogeneous.
- The first run with `notifyOn` enabled (cold start) emits an empty digest with
  `counts.new == 0` and a `summaryText` indicating "baseline run". This is expected and
  provides a positive heartbeat confirming the notification pipeline is wired correctly.
- Closes [#29](https://github.com/web-crawling/apify-olx-cars/issues/29).

## v0.8.0 — 2026-05-18

### Added
- **`serviceBookOnly` input** (boolean, default `false`) — keeps only listings with a
  stamped service book. Applies on Bulgaria (olx.bg) where OLX surfaces `service-book`
  in the `technical_condition` param. The filter inspects the raw OLX condition slug
  via the existing `conditionRaw` output field (set membership after `;`-split, exact
  slug match — substring matches are explicitly rejected). Listings on RO/PL/PT/UA/KZ
  pass through unchanged (no API signal) with a one-time INFO log per run. Closes
  [#51](https://github.com/web-crawling/apify-olx-cars/issues/51).

### Notes
- Filter runs client-side at pipeline priority 150 (same priority as `excludeDamaged`
  and `firstOwnerOnly`), so the `maxItems` cap (priority 100) is enforced BEFORE the
  filter. Runs with `serviceBookOnly: true` may yield fewer items than `maxItems`
  requests — increase `maxItems` by ~10–30 % to compensate.
- Combining `serviceBookOnly: true` with `firstOwnerOnly: true` on BG returns near-zero
  results: BG listings carry exactly one `technical_condition` value per offer, so
  almost no offer satisfies both filters at once. Run twice (once with each filter)
  and union the results if you need both populations.
- No new output field — reuses `conditionRaw` (shipped in v0.7.0).

## v0.7.0 — 2026-05-18

### Added
- **`excludeDamaged` input** (boolean, default `false`) — drops listings with raw condition
  `damaged` or equivalent. Applies on RO/PL/PT/UA/KZ; ignored on BG (no API signal) with
  a one-time INFO log per run.
- **`firstOwnerOnly` input** (boolean, default `false`) — keeps only listings flagged as
  first-owner. Applies on BG/UA/KZ (BG/UA via raw condition slug, KZ via `ownersCount == 1`);
  ignored on RO/PL/PT (no API signal) with a one-time INFO log per run.
- **`conditionRaw` output field** — raw OLX condition slug before normalisation
  (e.g. `"first-owner"`, `"service-book"`, `"damaged"`). Always a string: scalar on
  RO/PL/BG/PT/KZ; on UA where OLX returns an array, slugs are joined with `;`
  (e.g. `"first-owner;after-accident"`). Absent when the listing carries no condition param.
- **`serviceBookOnly` deferred** — research found the service-book signal exists on
  olx.bg only; deferred to [issue #51](https://github.com/web-crawling/apify-olx-cars/issues/51)
  for a future revisit if/when OLX exposes the field on more countries.

### Notes
- Filters are applied client-side after fetching (OLX's API has no server-side filter for
  any of these flags). The `maxItems` cap is enforced BEFORE filtering
  (`MaxItemsPipeline` at priority 100, `HistoryFilterPipeline` at priority 150), so runs
  with active filters may yield fewer items than `maxItems` requests.
- In incremental mode, filtered items never enter the snapshot (`HistoryFilterPipeline`
  at priority 150 fires before `IncrementalDiffPipeline` at priority 200).

## v0.6.0 — 2026-05-17

### Changed
- **Fair-price rating defaults tuned** — `priceVsMedianPct` and `priceRating` now
  emit on substantially more listings (~40 % of items in typical single-country
  single-brand runs, up from ~1 % in v0.5.0). New bucket parameters: minimum
  bucket size 5 (was 10), year band 5 years (was 2), mileage band 50,000 km
  (was 20,000). The field shape is unchanged; consumers will simply see ratings on
  more items. Tuned via offline ablation on 4,000 real OLX listings (see issue #49).

## v0.5.0 — 2026-05-17

### Added
- **Seller type filter** — new `sellerType` input (`any` / `private` / `business`; default `any`). Injects `filter_enum_business=0` (private) or `=1` (business) into the OLX API request. Works in both structured-filter and `startUrls` modes across all 6 supported countries. In `startUrls` mode, an existing `filter_enum_business` value in the user's URL is not overridden.
- **Extra attributes pass-through** — new `extraAttributes` output field: a flat `{key: label}` dict of all OLX `params[]` entries not suppressed as arrays. Covers country-specific fields not surfaced as dedicated top-level fields (e.g. `door_count`, `enginesize`, `color` on RO; `nr_seats`, `co2_emissions` on PT). Keys and values are the raw OLX strings; values may be in the listing language (Romanian, Polish, Bulgarian Cyrillic, etc.). Field is absent when `params[]` is empty.
- **Within-run fair-price rating** — two new output fields computed from all listings in a single run: `priceVsMedianPct` (number, % deviation from within-run bucket median) and `priceRating` (string enum). Bucket key: same `make`, `model`, 2-year year-band, 20,000 km mileage-band, and currency. Bucket must contain at least 10 items; both fields are absent when the bucket is smaller, price is undisclosed, or the listing is a `MISSING` incremental item. `priceRating` values: `very_good` (≤ −15 %), `good` (−15 % to −5 %), `fair` (±5 %), `high` (5 % to 15 %), `very_high` (≥ 15 %).

## v0.4.0 — 2026-05-17

### Added
- **Repost detection** — when `incrementalMode: true`, each output item now includes an `isRepost` boolean field. It is `true` when `changeType` is `REAPPEARED` (the listing was absent in the prior run and has returned, typically a seller deleting and re-listing for freshness), and `false` for all other change types. The field is absent entirely when `incrementalMode: false`.
- New output field (only present when `incrementalMode: true`): `isRepost` (boolean).

## v0.3.0 — 2026-05-16

### Added
- **Price history tracking** — when `incrementalMode: true`, each output item now includes a `priceHistory` array recording the seller's raw price and currency at each change event across runs. A new entry is appended only when `price` or `currency` changes; the `priceNegotiable` flag does not trigger an append. The array is capped at 50 entries (FIFO eviction). Legacy snapshots are migrated automatically on the first post-deploy run — no data wipe required.
- New output field (only present when `incrementalMode: true`): `priceHistory` (array of `{seenAt, price, currency}` objects).

## v0.2.0 — 2026-05-16

### Added
- **Incremental monitoring mode** — enable change tracking across runs via the new `incrementalMode` toggle. When enabled, each run compares scraped listings against a persisted snapshot (key-value store, configurable via `stateKey`) and emits per-item `changeType` (NEW / UPDATED / UNCHANGED / REAPPEARED / MISSING) plus `firstSeenAt` / `lastSeenAt` timestamps. The first run with incremental mode silently builds the baseline (0 items emitted). Subsequent runs emit only new and changed listings by default, dramatically reducing output size and cost for ongoing monitoring use cases.
- New input fields: `incrementalMode`, `stateKey`, `emitUnchanged`, `emitMissing`.
- New output fields (only present when `incrementalMode: true`): `changeType`, `firstSeenAt`, `lastSeenAt`.

## [1.0] - 2026-05-15

### Added
- Scrape car and vehicle listings from OLX across Romania (olx.ro), Poland (olx.pl), Bulgaria (olx.bg), Portugal (olx.pt), Ukraine (olx.ua), and Kazakhstan (olx.kz).
- Structured-filter input mode: `country`, `brands`, `query`, `yearFrom`, `yearTo`, `priceFrom`, `priceTo`, `priceCurrency`, `sortBy`, `maxItems`.
- Direct URL input mode: pass any OLX search or listing URL via `startUrls`; country is auto-inferred from the domain.
- 50 output fields per listing: identification, pricing (including price reductions and currency conversion), normalised vehicle specs (make, model, year, mileage, fuel type, transmission, body type, condition, engine size, power, color, VIN), country-specific fields (drivetrain, doors, seats, registration, CO2 emissions, customs cleared, previous owners), seller info, GPS location (with obfuscation flag), photo URLs, promotion flags, timestamps, and full raw params pass-through.
- Automatic brand-level and year-band slicing when `maxItems > 1000` to overcome the OLX API 1,000-result cap.
- Brand name resolution via bundled `brand_categories.json` per country (partial maps for RO, PL, BG on initial release; PT/UA/KZ maps pending).
