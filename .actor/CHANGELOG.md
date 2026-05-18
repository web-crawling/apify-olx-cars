# Changelog

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
