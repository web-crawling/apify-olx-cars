"""Re-verify BG normalization after parser_maps fix.

Runs a BG parent-cat scrape (maxItems=20), checks fuelType/transmission/condition
distributions and asserts BG-specific keys (benzinov/dizelov/avtomatichna/rchna,
technically-upright/service-book) now resolve correctly.
"""
import base64
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ACTOR_ROOT = Path(__file__).parent.parent
out_file = ACTOR_ROOT / "scripts" / "_bg_verify.jsonl"
if out_file.exists():
    out_file.unlink()

scenario = {"input": {"country": "bg", "maxItems": 20}}
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
print("STDOUT:", result.stdout[-200:])

items = []
if out_file.exists():
    with out_file.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))

print(f"\n=== {len(items)} BG items ===")
fuel_counts = {}
trans_counts = {}
cond_counts = {}
for it in items:
    fuel_counts[it.get('fuelType')] = fuel_counts.get(it.get('fuelType'), 0) + 1
    trans_counts[it.get('transmission')] = trans_counts.get(it.get('transmission'), 0) + 1
    cond_counts[it.get('condition')] = cond_counts.get(it.get('condition'), 0) + 1

print("fuelType counts:", fuel_counts)
print("transmission counts:", trans_counts)
print("condition counts:", cond_counts)

out_file.unlink(missing_ok=True)

other_fuel = fuel_counts.get('other', 0)
other_trans = trans_counts.get('other', 0)
other_cond = cond_counts.get('other', 0)

if len(items) == 0:
    print("FAIL: no BG items")
    sys.exit(1)
if other_fuel > len(items) * 0.3:
    print(f"FAIL: too many fuel='other' ({other_fuel}/{len(items)})")
    sys.exit(1)
if other_trans > len(items) * 0.3:
    print(f"FAIL: too many trans='other' ({other_trans}/{len(items)})")
    sys.exit(1)
if other_cond > len(items) * 0.3:
    print(f"FAIL: too many cond='other' ({other_cond}/{len(items)})")
    sys.exit(1)

print("\nPASS — BG normalization works")
