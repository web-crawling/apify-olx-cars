"""Per-country parameter key mapping and normalisation lookup tables.

Used by CarItemLoader (parser-implementer) to extract and normalise
car spec fields from the OLX API ``params[]`` array.

Sources:
  - PARAM_KEY_MAP keys verified by efficiency-researcher (02-efficiency.md)
    against live param key dumps for all six countries.
  - Normalisation dicts derived from 01-data-points.md and live samples.
  - UA/KZ numeric id lookups from live listing samples (issue #9, PR #62).
    Regenerate with: python scripts/build_brand_categories.py --dump-color-ids
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Six-country param key map
#
# Keyed by conceptual field name → {country_code: param_key_in_api}.
# None means the country does not expose this field via params.
# ---------------------------------------------------------------------------

PARAM_KEY_MAP: dict[str, dict[str, str | None]] = {
    "year": {
        "ro": "year",
        "pl": "year",
        "bg": "auto_make_year",
        "pt": "year",
        "ua": "motor_year",
        "kz": "motor_year",
    },
    "mileage": {
        "ro": "rulaj_pana",
        "pl": "milage",
        "bg": "auto_mileage",
        "pt": "quilometros",
        "ua": "motor_mileage_thou",  # thousands of km; multiply by 1000 in loader
        "kz": "motor_mileage",       # km directly
    },
    "fuel": {
        "ro": "petrol",
        "pl": "petrol",
        "bg": "auto_engine_type",
        "pt": "combustivel",
        "ua": "fuel_type",
        "kz": "fuel_type",
    },
    "transmission": {
        "ro": "gearbox",
        "pl": "transmission",
        "bg": "auto_transmission_type",
        "pt": "gearbox",
        "ua": "transmission_type",   # may return numeric ids 545/546
        "kz": "transmission_type",   # may return numeric ids 545/546
    },
    "body": {
        "ro": "car_body",
        "pl": "car_body",
        "bg": "type",
        "pt": "body_type",
        "ua": "car_body",
        "kz": "car_body",
    },
    "condition": {
        "ro": "state",
        "pl": "condition",
        "bg": "technical_condition",
        "pt": "condicao",
        "ua": "condition",
        "kz": "condition",
    },
    "engine_size": {
        "ro": "enginesize",
        "pl": "enginesize",
        "bg": "enginesize",
        "pt": "engine_capacity",
        "ua": "motor_engine_size_litre",  # litres; multiply by 1000 in loader
        "kz": "motor_engine_size",        # cm3 directly
    },
    "power": {
        "ro": "engine_power",
        "pl": "enginepower",
        "bg": "horsepower",
        "pt": "engine_power",
        "ua": "power",
        "kz": None,  # KZ does not expose engine power
    },
    "color": {
        "ro": "color",
        "pl": "color",
        "bg": "color",
        "pt": "color",
        "ua": "color",   # may return numeric ids; see UA_COLOR_MAP
        "kz": "color",   # may return numeric ids; see KZ_COLOR_MAP
    },
    "vin": {
        "ro": None,
        "pl": "vin",
        "bg": "vinnomer",
        "pt": None,
        "ua": "vin_number",
        "kz": None,
    },
    "license_plate": {
        "ro": None,
        "pl": None,
        "bg": None,
        "pt": "matricula",
        "ua": "license_plate",
        "kz": None,
    },
    "doors": {
        "ro": "door_count",
        "pl": None,
        "bg": "doors",
        "pt": "portas",
        "ua": "doors_num",
        "kz": None,
    },
    "seats": {
        "ro": None,
        "pl": None,
        "bg": "seats",
        "pt": "nr_seats",
        "ua": "seats_num",
        "kz": None,
    },
    "drivetrain": {
        "ro": None,
        "pl": "drive",
        "bg": None,
        "pt": None,
        "ua": "drive_type",
        "kz": None,
    },
    "steering_wheel": {
        "ro": "steering_wheel",
        "pl": "righthanddrive",
        "bg": None,
        "pt": None,
        "ua": None,
        "kz": None,
    },
    "registration_status": {
        "ro": "registration_state",
        "pl": None,
        "bg": None,
        "pt": None,
        "ua": None,
        "kz": None,
    },
    "country_of_origin": {
        "ro": None,
        "pl": "country_origin",
        "bg": "import",
        "pt": "origin",
        "ua": None,
        "kz": None,
    },
    "customs_cleared": {
        "ro": None,
        "pl": None,
        "bg": None,
        "pt": None,
        "ua": "cleared_customs",
        "kz": None,
    },
    "owners_count": {
        "ro": None,
        "pl": None,
        "bg": None,
        "pt": None,
        "ua": None,
        "kz": "owners",
    },
    "co2_emissions": {
        "ro": None,
        "pl": None,
        "bg": None,
        "pt": "co2_emissions",
        "ua": None,
        "kz": None,
    },
    # Feature checklist keys (array-valued params — value.key is a list)
    "features_ua_kz": {
        "ro": None,
        "pl": None,
        "bg": None,
        "pt": None,
        "ua": "car_option",
        "kz": "car_option",
    },
    # BG feature checklist keys (each is a separate array param)
    "features_bg_comfort": {
        "ro": None,
        "pl": None,
        "bg": "comfort",
        "pt": None,
        "ua": None,
        "kz": None,
    },
    "features_bg_multimedia": {
        "ro": None,
        "pl": None,
        "bg": "multimedia",
        "pt": None,
        "ua": None,
        "kz": None,
    },
    "features_bg_safety": {
        "ro": None,
        "pl": None,
        "bg": "safety",
        "pt": None,
        "ua": None,
        "kz": None,
    },
    "features_bg_other": {
        "ro": None,
        "pl": None,
        "bg": "other",
        "pt": None,
        "ua": None,
        "kz": None,
    },
}

# ---------------------------------------------------------------------------
# Normalisation tables
#
# Maps raw ``value.key`` strings (as returned by OLX API) → normalised
# output enum values.  Unmapped values fall back to "other".
# ---------------------------------------------------------------------------

FUEL_NORMALIZATION: dict[str, str] = {
    # Standard English slugs (RO, PL)
    "petrol": "petrol",
    "gasoline": "petrol",
    "benzyna": "petrol",          # PL
    "diesel": "diesel",
    "electric": "electric",
    "hybrid": "hybrid",
    "hibrid": "hybrid",           # RO variant
    "lpg": "lpg",
    "gpl": "lpg",                 # RO/PT variant
    "ethanol": "other",
    "cng": "other",
    "hydrogen": "other",
    # BG (auto_engine_type) — verified slugs from live offers
    "benzinov": "petrol",         # BG: бензинов
    "dizelov": "diesel",          # BG: дизелов
    "elektricheski": "electric",  # BG: електрически
    "hibriden": "hybrid",          # BG: хибриден
    "gaz": "lpg",                 # BG: газ
    # PT (combustivel)
    "gasolina": "petrol",
    "gasóleo": "diesel",
    "gasoleo": "diesel",
    "electrico": "electric",
    "hibrido": "hybrid",
    "híbrido": "hybrid",
    "plugin-hybrid": "hybrid",    # PT plug-in hybrid
    "glp": "lpg",
    # UA/KZ (fuel_type) — numeric IDs verified from live offers
    "542": "petrol",              # UA/KZ: Бензин
    "543": "diesel",              # UA/KZ: Дизель
    "544": "lpg",                 # UA/KZ: Газ/Бензин (LPG)
    "electro": "electric",        # UA/KZ: Електро (text variant)
    "gas": "lpg",                 # generic gas → lpg
}

TRANSMISSION_NORMALIZATION: dict[str, str] = {
    # RO (gearbox)
    "manual": "manual",
    "automatic": "automatic",
    "semi-automatic": "semi-automatic",
    "semi_automatic": "semi-automatic",
    "automated_manual": "semi-automatic",
    "cvt": "automatic",
    # PL (transmission)
    "manualna": "manual",
    "automatyczna": "automatic",
    # BG (auto_transmission_type) — verified from live offers
    "rchna": "manual",            # BG: ръчна (transliterated)
    "avtomatichna": "automatic",  # BG: автоматична
    # PT (gearbox) — shares same keys as RO mostly
    # UA/KZ (transmission_type) — NUMERIC IDs (verified)
    "545": "manual",
    "546": "automatic",
    "547": "semi-automatic",
    # String fallbacks for UA/KZ
    "mekhanichna": "manual",
    "avtomatychna": "automatic",
}

BODY_NORMALIZATION: dict[str, str] = {
    "sedan": "sedan",
    "limousine": "sedan",
    "limuzyna": "sedan",
    "suv": "suv",
    "crossover": "suv",
    "terenowy": "suv",
    "off-road-vehicle": "suv",    # UA/KZ standard key for SUV/off-road
    "hatchback": "hatchback",
    "liftback": "hatchback",      # UA: liftback is a hatchback variant
    "city-car": "hatchback",      # PT small city car
    "compact": "hatchback",       # PT compact hatchback
    "mini": "hatchback",          # PT mini
    "estate": "estate",
    "estate-car": "estate",       # RO/PL/UA/KZ standard estate/wagon key
    "combi": "estate",
    "kombivan": "estate",
    "kombi": "estate",
    "station_wagon": "estate",
    "stationwagon": "estate",
    "caravan": "estate",          # UA caravan = estate/wagon
    "coupe": "coupe",
    "cabrio": "convertible",
    "cabriolet": "convertible",
    "convertible": "convertible",
    "pickup": "pickup",
    "mpv": "mpv",
    "minivan": "mpv",
    "van": "mpv",
    "minibus": "mpv",             # KZ/PL minibus → mpv
    "mikrobus": "mpv",
    "other": "other",
    # BG body (type) — these are NOT body-type slugs but condition flags
    # ("with-mileage", "with-improvements"). BG does not expose body type
    # cleanly; left intentionally absent so unknown BG keys → "other".
    # PT (body_type) — English slugs shared with RO
}

CONDITION_NORMALIZATION: dict[str, str] = {
    # RO (state)
    "used": "used",
    "new": "new",
    "damaged": "damaged",
    "notdamaged": "used",
    "slightly_damaged": "damaged",
    # PL (condition)
    "uzywane": "used",
    "nowe": "new",
    "uszkodzone": "damaged",
    # BG (technical_condition) — verified from live offers
    "technically-upright": "used",   # BG: В движение, технически изправен
    "service-book": "used",          # BG: Сервизна книжка (qualifier, still "used")
    "with-mileage": "used",          # BG: На пробег
    "with-improvements": "used",     # BG: С подобрения
    # PT (condicao)
    "usado": "used",
    "novo": "new",
    "danificado": "damaged",
    # UA/KZ (condition) — verified from live offers; array-valued, see _make_item
    "good": "used",
    "excellent": "used",
    "fine_condition": "used",
    "garage-storage": "used",
    "not-bit": "used",
    "not-colored": "used",
    "first-owner": "used",
    "mediocre": "used",
    "after-an-accident": "damaged",
    "needs_body_repair": "damaged",
    "needs_repairs": "damaged",
    "needs_engine_repair": "damaged",
    "perfect": "used",            # KZ: ideal/perfect condition
}

# Severity ranking for UA condition (which returns a LIST of flags).
# Higher value = more severe. _make_item picks the most-severe member.
CONDITION_SEVERITY: dict[str, int] = {
    "new": 0,
    "used": 1,
    "damaged": 2,
}

# ---------------------------------------------------------------------------
# Color maps for UA/KZ (numeric IDs returned instead of text slugs)
#
# Numeric string id → canonical English slug.
# IDs harvested from live listing params (issue #9, 2026-05-18).
# Regenerate with: python scripts/build_brand_categories.py --dump-color-ids
# Output JSON files: src/data/_color_ids_ua.json, _color_ids_kz.json
#
# Note: IDs 16 and 19 were absent from all sampling runs for both countries
# (presumed unused/deprecated by OLX).  ID 20 appears only on UA
# ("Матовий" = matte finish) — KZ does not expose it.
# ---------------------------------------------------------------------------

UA_COLOR_MAP: dict[str, str] = {
    # Numeric string id → English slug
    # Source: live UA listing params, 2026-05-18 (22 ids discovered)
    # OLX UA label (Ukrainian) noted in comments
    "1": "white",       # Білий
    "2": "black",       # Чорний
    "3": "blue",        # Синій
    "4": "gray",        # Сірий
    "5": "silver",      # Сріблястий
    "6": "red",         # Червоний
    "7": "green",       # Зелений
    "8": "orange",      # Апельсин (lit. "orange fruit")
    "9": "gray",        # Асфальт (dark charcoal/asphalt → gray family)
    "10": "beige",      # Бежевий
    "11": "other",      # Бірюзовий (turquoise — no canonical equivalent)
    "12": "gold",       # Бронзовий (bronze → gold family)
    "13": "bordeaux",   # Вишневий (cherry/burgundy)
    "14": "blue",       # Блакитний (light blue → blue family)
    "15": "yellow",     # Жовтий
    "17": "gold",       # Золотий
    "18": "brown",      # Коричневий
    "20": "other",      # Матовий (matte finish — a surface treatment, not a hue)
    "21": "green",      # Оливковий (olive green → green family)
    "22": "other",      # Рожевий (pink — not in canonical vocabulary)
    "24": "purple",     # Фіолетовий (violet)
    "25": "other",      # Хамелеон (chameleon/colour-shifting paint)
    # Text-slug fallbacks (issue #63). OLX UA's API occasionally returns text
    # slugs instead of numeric ids for the color param. Without these entries
    # they pass through `UA_COLOR_MAP.get(color_str, color_str)` unchanged and
    # reach the dataset as non-canonical values.
    "grey": "gray",           # British spelling → canonical US spelling
    "light_blue": "blue",     # no canonical light_blue → blue family
    "multicolor": "other",    # not in canonical vocabulary
    "pixel": "other",         # data-quality artefact (not a real colour)
}

KZ_COLOR_MAP: dict[str, str] = {
    # Numeric string id → English slug
    # Source: live KZ listing params, 2026-05-18 (21 ids discovered)
    # OLX KZ label (Russian) noted in comments
    # KZ ids largely overlap UA but are discovered standalone per
    # the project rule against sharing taxonomy maps between countries.
    "1": "white",       # Белый
    "2": "black",       # Черный
    "3": "blue",        # Синий
    "4": "gray",        # Серый
    "5": "silver",      # Серебристый
    "6": "red",         # Красный
    "7": "green",       # Зеленый
    "8": "orange",      # Апельсин (lit. "orange fruit")
    "9": "gray",        # Асфальт (dark charcoal/asphalt → gray family)
    "10": "beige",      # Бежевый
    "11": "other",      # Бирюзовый (turquoise — no canonical equivalent)
    "12": "gold",       # Бронзовый (bronze → gold family)
    "13": "bordeaux",   # Вишнёвый (cherry/burgundy)
    "14": "blue",       # Голубой (light blue → blue family)
    "15": "yellow",     # Желтый
    "17": "gold",       # Золотой
    "18": "brown",      # Коричневый
    "22": "other",      # Розовый (pink — not in canonical vocabulary)
    "23": "other",      # Сафари (safari/khaki — not in canonical vocabulary)
    "24": "purple",     # Фиолетовый (violet)
    "25": "other",      # Хамелеон (chameleon/colour-shifting paint)
    # Text-slug fallbacks (issue #63). Mirrored from UA_COLOR_MAP for safety —
    # KZ was not observed returning these slugs in the PR #62 sample, but the
    # API surface is identical to UA and may return text slugs in future
    # samples. Cheap defensive coverage.
    "grey": "gray",           # British spelling → canonical US spelling
    "light_blue": "blue",     # no canonical light_blue → blue family
    "multicolor": "other",    # not in canonical vocabulary
    "pixel": "other",         # data-quality artefact (not a real colour)
}
