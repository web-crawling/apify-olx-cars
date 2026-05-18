"""Schema verification for Issue #23 (post-fix).

Checks:
  1. conditionRaw is in dataset_schema.json fields.properties
  2. conditionRaw is NOT in required array
  3. conditionRaw has type: string (after B1/WARN fix — always emitted as str)
  4. conditionRaw has NO nullable field (removed in fix)
  5. conditionRaw has a description
  6. Check input_schema.json for excludeDamaged and firstOwnerOnly
"""

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ACTOR_ROOT = Path(__file__).parent.parent
PROJECT_ROOT = ACTOR_ROOT.parent

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
results = []


def check(label: str, ok: bool, detail: str = ""):
    status = PASS if ok else FAIL
    results.append((status, label, detail))
    mark = "  OK  " if ok else " FAIL "
    extra = f" -- {detail}" if detail else ""
    print(f"[{mark}] {label}{extra}")


def warn(label: str, detail: str = ""):
    results.append((WARN, label, detail))
    print(f"[ WARN ] {label} -- {detail}")


# ---------------------------------------------------------------------------
# Load dataset_schema.json
# ---------------------------------------------------------------------------
ds_path = ACTOR_ROOT / ".actor" / "dataset_schema.json"
try:
    with open(ds_path, encoding="utf-8") as f:
        ds = json.load(f)
    check("dataset_schema.json loads as valid JSON", True)
except Exception as e:
    check("dataset_schema.json loads as valid JSON", False, str(e))
    sys.exit(1)

properties = ds.get("fields", {}).get("properties", {})
required_fields = ds.get("fields", {}).get("required", [])

# 1. conditionRaw present in properties
check("conditionRaw present in fields.properties",
      "conditionRaw" in properties,
      f"keys found: {list(properties.keys())[-5:]}")

# 2. conditionRaw NOT in required
if "conditionRaw" in required_fields:
    check("conditionRaw NOT in required array", False,
          f"required fields: {required_fields}")
else:
    check("conditionRaw NOT in required array", True,
          f"required array: {required_fields[:5]}")

cond_raw_def = properties.get("conditionRaw", {})

# 3. type: string present (post-fix: always emitted as str)
check("conditionRaw has type: string",
      cond_raw_def.get("type") == "string",
      f"actual: {cond_raw_def}")

# 4. nullable NOT present (removed in fix — DropNonesPipeline handles absence)
check("conditionRaw has NO nullable field",
      "nullable" not in cond_raw_def,
      f"actual definition: {cond_raw_def}")

# 5. description is present
check("conditionRaw has description",
      bool(cond_raw_def.get("description")),
      f"description: {str(cond_raw_def.get('description', ''))[:60]}")

# ---------------------------------------------------------------------------
# Verify conditionRaw schema risk is resolved (no untyped field)
# ---------------------------------------------------------------------------
print("\n--- Schema risk resolved: conditionRaw now has type: string ---")
# After the B1/WARN fix, conditionRaw is always a string (UA arrays ';'-joined).
# No need to search for untyped+nullable precedent — this field is now typed.
check("conditionRaw schema risk resolved (type: string declared)",
      cond_raw_def.get("type") == "string",
      "Post-fix: UA arrays are ';'-joined to str — no union type needed")

# ---------------------------------------------------------------------------
# Check olx-cars for any remaining untyped nullable fields
# ---------------------------------------------------------------------------
print("\n--- Internal olx-cars schema: check for untyped fields ---")
untyped_fields = []
for fname, fdef in properties.items():
    if "type" not in fdef:
        untyped_fields.append(fname)
        print(f"  Field '{fname}': no type — nullable={fdef.get('nullable')}, "
              f"keys={list(fdef.keys())}")
check("conditionRaw is not in untyped fields list",
      "conditionRaw" not in untyped_fields,
      f"untyped fields: {untyped_fields}")

# ---------------------------------------------------------------------------
# input_schema.json checks
# ---------------------------------------------------------------------------
print("\n--- input_schema.json checks ---")
is_path = ACTOR_ROOT / ".actor" / "input_schema.json"
try:
    with open(is_path, encoding="utf-8") as f:
        isch = json.load(f)
    check("input_schema.json loads as valid JSON", True)
except Exception as e:
    check("input_schema.json loads as valid JSON", False, str(e))
    sys.exit(1)

iprops = isch.get("properties", {})

# excludeDamaged
ed = iprops.get("excludeDamaged", {})
check("excludeDamaged present in input_schema.json", bool(ed))
check("excludeDamaged type=boolean", ed.get("type") == "boolean",
      f"actual type: {ed.get('type')}")
check("excludeDamaged default=false", ed.get("default") is False,
      f"actual default: {ed.get('default')}")

# firstOwnerOnly
fo = iprops.get("firstOwnerOnly", {})
check("firstOwnerOnly present in input_schema.json", bool(fo))
check("firstOwnerOnly type=boolean", fo.get("type") == "boolean",
      f"actual type: {fo.get('type')}")
check("firstOwnerOnly default=false", fo.get("default") is False,
      f"actual default: {fo.get('default')}")

# Position: both after sellerType (keys list order)
prop_keys = list(iprops.keys())
if "sellerType" in prop_keys and "excludeDamaged" in prop_keys and "firstOwnerOnly" in prop_keys:
    idx_seller = prop_keys.index("sellerType")
    idx_ed = prop_keys.index("excludeDamaged")
    idx_fo = prop_keys.index("firstOwnerOnly")
    check("excludeDamaged placed after sellerType in input_schema",
          idx_ed > idx_seller,
          f"sellerType at {idx_seller}, excludeDamaged at {idx_ed}")
    check("firstOwnerOnly placed after excludeDamaged in input_schema",
          idx_fo > idx_ed,
          f"excludeDamaged at {idx_ed}, firstOwnerOnly at {idx_fo}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
total = len(results)
passed = sum(1 for s, *_ in results if s == PASS)
warned = sum(1 for s, *_ in results if s == WARN)
failed = total - passed - warned
print(f"Results: {passed}/{total} passed, {warned} warnings, {failed} failed")
if failed:
    print("\nFailed:")
    for status, label, detail in results:
        if status == FAIL:
            print(f"  FAIL: {label} -- {detail}")
    sys.exit(1)
else:
    print("ALL PASS (schema checks green)")
    sys.exit(0)
