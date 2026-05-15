# Changelog

## [1.0] - 2026-05-15

### Added
- Scrape car and vehicle listings from OLX across Romania (olx.ro), Poland (olx.pl), Bulgaria (olx.bg), Portugal (olx.pt), Ukraine (olx.ua), and Kazakhstan (olx.kz).
- Structured-filter input mode: `country`, `brands`, `query`, `yearFrom`, `yearTo`, `priceFrom`, `priceTo`, `priceCurrency`, `sortBy`, `maxItems`.
- Direct URL input mode: pass any OLX search or listing URL via `startUrls`; country is auto-inferred from the domain.
- 50 output fields per listing: identification, pricing (including price reductions and currency conversion), normalised vehicle specs (make, model, year, mileage, fuel type, transmission, body type, condition, engine size, power, color, VIN), country-specific fields (drivetrain, doors, seats, registration, CO2 emissions, customs cleared, previous owners), seller info, GPS location (with obfuscation flag), photo URLs, promotion flags, timestamps, and full raw params pass-through.
- Automatic brand-level and year-band slicing when `maxItems > 1000` to overcome the OLX API 1,000-result cap.
- Brand name resolution via bundled `brand_categories.json` per country (partial maps for RO, PL, BG on initial release; PT/UA/KZ maps pending).
