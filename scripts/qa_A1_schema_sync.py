"""QA Test A1 -- Schema sync: every Field() in items.py matches dataset_schema.json 1:1."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ITEMS_PY = ROOT / "src" / "items.py"
SCHEMA_JSON = ROOT / ".actor" / "dataset_schema.json"

items_text = ITEMS_PY.read_text(encoding="utf-8")
items_fields = re.findall(r"^\s+(\w+)\s*=\s*scrapy\.Field\(\)", items_text, re.MULTILINE)

schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
schema_fields = list(schema["fields"]["properties"].keys())

items_set = set(items_fields)
schema_set = set(schema_fields)

print("=== Schema Sync Test ===")
print(f"items.py fields ({len(items_fields)}): {sorted(items_set)}")
print(f"dataset_schema.json fields ({len(schema_fields)}): {sorted(schema_set)}")

in_items_not_schema = items_set - schema_set
in_schema_not_items = schema_set - items_set

ok = True
if in_items_not_schema:
    print(f"\nFAIL -- In items.py but NOT in dataset_schema.json: {sorted(in_items_not_schema)}")
    ok = False
else:
    print("\nPASS -- No fields in items.py missing from schema.")

if in_schema_not_items:
    print(f"FAIL -- In dataset_schema.json but NOT in items.py: {sorted(in_schema_not_items)}")
    ok = False
else:
    print("PASS -- No fields in schema missing from items.py.")

print(f"\nResult: {'ALL PASS' if ok else 'FAILURES FOUND'}")
sys.exit(0 if ok else 1)
