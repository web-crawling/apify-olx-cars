"""Re-verify UA normalization after parser_maps fix.

Runs a UA BMW scrape (maxItems=10), checks fuelType/transmission/condition
distributions and asserts none falls back to 'other'.
"""
import base64
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ACTOR_ROOT = Path(__file__).parent.parent
out_file = ACTOR_ROOT / "scripts" / "_ua_verify.jsonl"
if out_file.exists():
    out_file.unlink()

scenario = {"input": {"country": "ua", "brands": ["BMW"], "maxItems": 10}}
scenario_b64 = base64.b64encode(json.dumps(scenario).encode()).decode()

result = subprocess.run(
    [str(ACTOR_ROOT / ".venv" / "Scripts" / "python.exe"),
     str(ACTOR_ROOT / "scripts" / "qa_C_single.py"),
     scenario_b64,
     str(out_file)],
    cwd=str(ACTOR_ROOT),
    capture_output=True,
    text=True,
    timeout=180,
)
print("STDERR tail:", result.stderr[-2000:] if result.stderr else "(none)")
print("STDOUT:", result.stdout[-500:])

if not out_file.exists():
    print("FAIL: no output produced")
    sys.exit(1)

items = []
with out_file.open(encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            items.append(json.loads(line))

print(f"\n=== {len(items)} UA BMW items ===")
fuel_counts = {}
trans_counts = {}
body_counts = {}
cond_counts = {}
for it in items:
    fuel_counts[it.get('fuelType')] = fuel_counts.get(it.get('fuelType'), 0) + 1
    trans_counts[it.get('transmission')] = trans_counts.get(it.get('transmission'), 0) + 1
    body_counts[it.get('bodyType')] = body_counts.get(it.get('bodyType'), 0) + 1
    cond_counts[it.get('condition')] = cond_counts.get(it.get('condition'), 0) + 1

print("fuelType counts:", fuel_counts)
print("transmission counts:", trans_counts)
print("bodyType counts:", body_counts)
print("condition counts:", cond_counts)

# Sample one item to inspect mileage/engine normalization
if items:
    s = items[0]
    print(f"\nsample item:")
    print(f"  make={s.get('make')!r} model={s.get('model')!r} year={s.get('year')!r}")
    print(f"  mileageKm={s.get('mileageKm')!r} engineCapacityCm3={s.get('engineCapacityCm3')!r}")
    print(f"  fuelType={s.get('fuelType')!r} transmission={s.get('transmission')!r}")
    print(f"  condition={s.get('condition')!r} bodyType={s.get('bodyType')!r}")

# Cleanup
out_file.unlink(missing_ok=True)

# Assertions
other_share_fuel = fuel_counts.get('other', 0) + fuel_counts.get(None, 0)
other_share_trans = trans_counts.get('other', 0) + trans_counts.get(None, 0)
other_share_cond = cond_counts.get('other', 0) + cond_counts.get(None, 0)
print(f"\nfuel='other' or null: {other_share_fuel}/{len(items)}")
print(f"trans='other' or null: {other_share_trans}/{len(items)}")
print(f"cond='other' or null: {other_share_cond}/{len(items)}")

if other_share_fuel > len(items) * 0.2:
    print("FAIL: > 20% of fuelType is 'other'")
    sys.exit(1)
if other_share_trans > len(items) * 0.2:
    print("FAIL: > 20% of transmission is 'other'")
    sys.exit(1)
if other_share_cond > len(items) * 0.2:
    print("FAIL: > 20% of condition is 'other'")
    sys.exit(1)

print("\nPASS — UA normalization works")
