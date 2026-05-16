"""PR #35 — six-country sanity: verify the cleaned items pass dataset_schema
validation for ALL 6 countries.

This is the comprehensive cross-country check the PR review asked for.
For each country we run the spider with brands=["BMW"], maxItems=5,
then for every produced item we:
  1. Run _drop_nones() on it
  2. Validate against dataset_schema.json
  3. Assert: zero validation errors per item, items > 0
"""

from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ACTOR_ROOT = Path(__file__).parent.parent
SINGLE = ACTOR_ROOT / 'scripts' / 'qa_C_single.py'
PY = ACTOR_ROOT / '.venv' / 'Scripts' / 'python.exe'
SCHEMA_PATH = ACTOR_ROOT / '.actor' / 'dataset_schema.json'

sys.path.insert(0, str(ACTOR_ROOT))
from src.pipelines import _drop_nones  # noqa: E402

from jsonschema import Draft7Validator  # noqa: E402

with open(SCHEMA_PATH, encoding='utf-8') as fh:
    full = json.load(fh)
validator = Draft7Validator(full['fields'])

COUNTRIES = ('ro', 'pl', 'bg', 'pt', 'ua', 'kz')
MAX_ITEMS = 5


def run_one(country: str) -> list[dict]:
    scenario = {
        'name': f'{country}-pr35',
        'input': {'country': country, 'brands': ['BMW'], 'maxItems': MAX_ITEMS},
    }
    blob = base64.b64encode(json.dumps(scenario).encode('utf-8')).decode('ascii')
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False, dir=str(ACTOR_ROOT)) as fh:
        out_file = fh.name
    try:
        proc = subprocess.run(
            [str(PY), str(SINGLE), blob, out_file],
            cwd=str(ACTOR_ROOT), capture_output=True, text=True, timeout=180,
        )
        items = []
        if os.path.exists(out_file):
            with open(out_file, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        items.append(json.loads(line))
        if proc.returncode != 0:
            print(f'  [{country}] spider exit != 0: stderr tail:\n{proc.stderr[-500:]}')
        return items
    finally:
        if os.path.exists(out_file):
            os.unlink(out_file)


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print(f'PR #35 six-country sanity ({MAX_ITEMS} items per country, BMW filter)\n')
    all_pass = True
    for country in COUNTRIES:
        items = run_one(country)
        if not items:
            print(f'  [{country}] FAIL — 0 items produced')
            all_pass = False
            continue
        # Validate every item, both raw and cleaned
        raw_fail = 0
        cleaned_fail = 0
        cleaned_district_dropped = 0
        for it in items:
            raw_errors = list(validator.iter_errors(it))
            if raw_errors:
                raw_fail += 1
            cleaned = _drop_nones(it)
            cleaned_errors = list(validator.iter_errors(cleaned))
            if cleaned_errors:
                cleaned_fail += 1
                # Print first error for diagnostic
                err = cleaned_errors[0]
                path = '/'.join(str(p) for p in err.absolute_path) or '<root>'
                print(f'    [{country}] cleaned item still fails: [{path}] {err.message}')
            if 'location' in it and isinstance(it['location'], dict) and it['location'].get('district') is None:
                cleaned_district_dropped += 1
        marker = 'PASS' if cleaned_fail == 0 else 'FAIL'
        if cleaned_fail != 0:
            all_pass = False
        print(
            f'  [{country}] {marker} — {len(items)} items, '
            f'raw_fail={raw_fail}, cleaned_fail={cleaned_fail}, '
            f'district=None: {cleaned_district_dropped}'
        )
    print('\nResult:', 'ALL PASS' if all_pass else 'FAILURES')
    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())
