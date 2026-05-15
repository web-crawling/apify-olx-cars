"""QA Test A3 -- MEMORY.md gotchas: verify all Apify schema constraints."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ACTOR = ROOT / ".actor"

ok = True

def check(label, condition, details=""):
    global ok
    status = "PASS" if condition else "FAIL"
    if not condition:
        ok = False
    msg = f"{status} -- {label}"
    if details:
        msg += f"\n    {details}"
    print(msg)

# ---- 1. actor.json version ----
actor = json.loads((ACTOR / "actor.json").read_text())
version = actor.get("version", "")
check(
    'actor.json version is "1.0" (MAJOR.MINOR only)',
    version == "1.0",
    f"Got: {version!r}"
)

# ---- 2 & 3. input_schema.json ----
input_schema = json.loads((ACTOR / "input_schema.json").read_text())
props = input_schema.get("properties", {})

has_format_date = any(
    p.get("format") == "date"
    for p in props.values()
    if isinstance(p, dict)
)
check(
    'input_schema.json: no format:"date" on any property',
    not has_format_date,
    "Found format:date on one or more properties" if has_format_date else ""
)

has_type_union = any(
    isinstance(p.get("type"), list)
    for p in props.values()
    if isinstance(p, dict)
)
check(
    'input_schema.json: no type unions (["string","null"] etc)',
    not has_type_union,
    "Found type union on one or more properties" if has_type_union else ""
)

# ---- 4. startUrls prefill entries are {"url":"..."} objects ----
start_urls_prop = props.get("startUrls", {})
prefill = start_urls_prop.get("prefill", [])
if not prefill:
    check("startUrls prefill is non-empty", False, "prefill is missing or empty")
else:
    all_objects = all(isinstance(e, dict) and "url" in e for e in prefill)
    check(
        'startUrls prefill entries are {"url":"..."} objects (not plain strings)',
        all_objects,
        f"Prefill: {prefill!r}"
    )

# ---- 5. output_schema.json ----
output_schema = json.loads((ACTOR / "output_schema.json").read_text())
has_output_version = output_schema.get("actorOutputSchemaVersion") == 1
check(
    "output_schema.json has actorOutputSchemaVersion: 1",
    has_output_version,
    f"Got: {output_schema.get('actorOutputSchemaVersion')!r}"
)
has_properties_block = "properties" in output_schema and bool(output_schema["properties"])
check(
    "output_schema.json has non-empty properties block",
    has_properties_block,
    f"properties: {list(output_schema.get('properties', {}).keys())}"
)

# ---- 6. key_value_store_schema.json ----
kv_schema = json.loads((ACTOR / "key_value_store_schema.json").read_text())
has_kv_version = kv_schema.get("actorKeyValueStoreSchemaVersion") == 1
check(
    "key_value_store_schema.json has actorKeyValueStoreSchemaVersion: 1",
    has_kv_version,
    f"Got: {kv_schema.get('actorKeyValueStoreSchemaVersion')!r}"
)

# ---- 7. dataset_schema.json: no format:date-time on top-level fields ----
dataset_schema = json.loads((ACTOR / "dataset_schema.json").read_text())
ds_props = dataset_schema.get("fields", {}).get("properties", {})
fields_with_datetime_format = [
    k for k, v in ds_props.items()
    if isinstance(v, dict) and v.get("format") in ("date-time", "date")
]
check(
    'dataset_schema.json: no format:date-time on timestamp fields (conservative)',
    len(fields_with_datetime_format) == 0,
    f"Fields with date/datetime format: {fields_with_datetime_format}" if fields_with_datetime_format else ""
)

print(f"\nResult: {'ALL PASS' if ok else 'FAILURES FOUND'}")
sys.exit(0 if ok else 1)
