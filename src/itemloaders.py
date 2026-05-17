"""Item loaders module for OLX Cars actor.

Defines CarItemLoader with per-field input/output processors.

Processor rules:
- Scalar fields use TakeFirst() output processor (default).
- Array fields (images, features, paramsRaw) use Identity() output processor.
- Nested object fields (seller, location, promotionFlags) use TakeFirst() —
  the spider pre-assembles the dict and passes it via add_value().
- Boolean fields absent from certain countries use '' sentinel so TakeFirst()
  returns None instead of raising a loader-internal absent error.
- description: strip HTML tags via MapCompose(strip_html_tags).
- Numeric fields: coerce via parse_int_or_none / parse_float_or_none.
"""

from __future__ import annotations

import re as _re

from itemloaders import ItemLoader
from itemloaders.processors import Identity, MapCompose, TakeFirst

from .helpers.re import strip_html_tags


# ---------------------------------------------------------------------------
# Processor helper functions
# ---------------------------------------------------------------------------

def strip_extra_whitespace(value) -> str | None:
    """Strip leading/trailing whitespace from a string value.

    Returns None for empty strings and non-string values so TakeFirst()
    produces None rather than an empty string in the output.
    """
    if value is None or value == '':
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value


def parse_int_or_none(value) -> int | None:
    """Coerce value to int; return None on failure or empty sentinel."""
    if value is None or value == '':
        return None
    try:
        # int() handles both str("2021") and already-int 2021
        return int(value)
    except (TypeError, ValueError):
        try:
            # Handles float strings like "1.4" → 1 (for engine size fallback)
            return int(float(value))
        except (TypeError, ValueError):
            return None


def parse_float_or_none(value) -> float | None:
    """Coerce value to float; return None on failure or empty sentinel."""
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pass_bool(value) -> bool | None:
    """Pass a pre-computed boolean through unchanged.

    Converts empty sentinel '' to None (for absent optional boolean fields).
    The spider uses `loader.add_value('field', value or '')` for optional
    booleans so that absent fields cleanly yield None after TakeFirst().
    """
    if value == '' or value is None:
        return None
    return bool(value)


def pass_through(value):
    """Identity function — pass value unchanged.

    Used as the input processor for fields where the spider passes
    pre-processed Python objects (dicts, lists).
    """
    return value


# ---------------------------------------------------------------------------
# CarItemLoader
# ---------------------------------------------------------------------------

class CarItemLoader(ItemLoader):
    """ItemLoader for CarItem.

    Default processors:
    - Input:  MapCompose(strip_extra_whitespace) — trims strings, passes None
    - Output: TakeFirst() — scalar output for all fields

    Per-field overrides:
    - description_in:       MapCompose(strip_html_tags) — strip <br /> etc.
    - images_out:           Identity() — preserves full URL list
    - features_out:         Identity() — preserves full feature key list
    - paramsRaw_out:        Identity() — preserves full raw params list
    - *_in for int fields:  MapCompose(parse_int_or_none)
    - *_in for bool fields: MapCompose(pass_bool)
    - seller_in / location_in / promotionFlags_in: MapCompose(pass_through)
      so the pre-assembled dict passes through without str-stripping
    """

    default_input_processor = MapCompose(strip_extra_whitespace)
    default_output_processor = TakeFirst()

    # --- description: strip HTML -------------------------------------------
    description_in = MapCompose(strip_html_tags)

    # --- Integer scalar fields ---------------------------------------------
    offerId_in = MapCompose(parse_int_or_none)
    price_in = MapCompose(parse_int_or_none)
    pricePrevious_in = MapCompose(parse_int_or_none)
    priceConverted_in = MapCompose(parse_int_or_none)
    year_in = MapCompose(parse_int_or_none)
    mileageKm_in = MapCompose(parse_int_or_none)
    engineCapacityCm3_in = MapCompose(parse_int_or_none)
    powerHp_in = MapCompose(parse_int_or_none)
    doorCount_in = MapCompose(parse_int_or_none)
    seatCount_in = MapCompose(parse_int_or_none)
    ownersCount_in = MapCompose(parse_int_or_none)
    co2Emissions_in = MapCompose(parse_int_or_none)

    # --- Boolean scalar fields ---------------------------------------------
    # Spider passes `value or ''` for optional booleans; pass_bool converts
    # '' → None and any other value → bool.
    priceNegotiable_in = MapCompose(pass_bool)

    # --- Nested object fields (dict) — pass through unchanged --------------
    # The spider assembles these dicts and passes them via add_value().
    # Using MapCompose(pass_through) prevents the default strip_extra_whitespace
    # from trying to call .strip() on a dict.
    seller_in = MapCompose(pass_through)
    location_in = MapCompose(pass_through)
    promotionFlags_in = MapCompose(pass_through)

    # --- Array fields: Identity() output processor -------------------------
    # These fields hold lists assembled in the spider before add_value() call.
    # Identity() preserves the list as-is instead of wrapping in another list.
    images_out = Identity()
    features_out = Identity()
    paramsRaw_out = Identity()

    # --- Extra attributes and fair-price fields: TakeFirst() output --------
    # extraAttributes is a scalar dict assembled in the spider and passed via
    # add_value() — TakeFirst() returns it as-is, NOT Identity() which would
    # wrap the dict in a list.
    extraAttributes_in = MapCompose(pass_through)
    extraAttributes_out = TakeFirst()

    # priceVsMedianPct and priceRating are set directly on items by
    # FairPricePipeline in main.py (bypassing the loader) — but the output
    # processors are declared here for completeness and schema alignment.
    priceVsMedianPct_out = TakeFirst()
    priceRating_out = TakeFirst()
