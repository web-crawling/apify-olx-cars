# Changelog

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
