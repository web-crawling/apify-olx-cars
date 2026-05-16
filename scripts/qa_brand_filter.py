"""Live QA — verify brand-filter resolution across all 6 countries.

For each (country, brand) pair, runs the spider with maxItems=15 and
asserts every output row's `make` field matches the requested brand
(case-insensitive). Failures indicate that the brand-leaf category
wasn't resolved and the spider fell back to the parent cars category.

Scenario list mixes:
  * BMW on all 6 countries — regression check (BMW is in every map).
  * Newly-discovered RO/PL brands (dacia, tesla) — forward check that
    refresh exposed brand-leaf categories that previously fell back to
    the parent cars cat.
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

# (country, brand-name) pairs to test.
SCENARIOS: tuple[tuple[str, str], ...] = (
    ('ro', 'BMW'),
    ('pl', 'BMW'),
    ('bg', 'BMW'),
    ('pt', 'BMW'),
    ('ua', 'BMW'),
    ('kz', 'BMW'),
    ('ro', 'Dacia'),
    ('pl', 'Dacia'),
)
MAX_ITEMS = 15


def run_scenario(country: str, brand: str) -> tuple[bool, list[dict], str]:
    scenario = {
        'name': f'{country}-brand-{brand.lower().replace(" ", "-")}',
        'input': {
            'country': country,
            'brands': [brand],
            'maxItems': MAX_ITEMS,
        },
    }
    blob = base64.b64encode(json.dumps(scenario).encode('utf-8')).decode('ascii')

    with tempfile.NamedTemporaryFile(
        suffix='.jsonl', delete=False, dir=str(ACTOR_ROOT),
    ) as fh:
        out_file = fh.name

    try:
        proc = subprocess.run(
            [str(PY), str(SINGLE), blob, out_file],
            cwd=str(ACTOR_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        items = []
        if os.path.exists(out_file):
            with open(out_file, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        items.append(json.loads(line))
        return proc.returncode == 0, items, proc.stderr[-2000:]
    finally:
        if os.path.exists(out_file):
            os.unlink(out_file)


def assess(brand: str, items: list[dict]) -> tuple[bool, str]:
    if not items:
        return False, 'no items produced'
    target = brand.strip().lower()
    makes = [(it.get('make') or '').strip().lower() for it in items]
    match_count = sum(1 for m in makes if m == target)
    other = [m for m in makes if m and m != target]
    pct = 100 * match_count / len(items)
    msg = (
        f'{len(items)} items, {match_count} {brand} ({pct:.0f}%), '
        f'others: {sorted(set(other))[:5]}'
    )
    return pct == 100, msg


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print('Live QA - brand filter resolution\n')
    results: list[tuple[str, str, bool, str]] = []
    for country, brand in SCENARIOS:
        print(f'  [{country}/{brand}] running spider, maxItems={MAX_ITEMS} ...')
        ok, items, stderr = run_scenario(country, brand)
        if not ok:
            print(f'  [{country}/{brand}] spider crashed')
            print(stderr[-800:])
            results.append((country, brand, False, 'spider exit != 0'))
            continue
        passed, summary = assess(brand, items)
        marker = 'PASS' if passed else 'FAIL'
        print(f'  [{country}/{brand}] {marker} - {summary}')
        results.append((country, brand, passed, summary))

    print('\nSummary:')
    for country, brand, passed, summary in results:
        marker = '[PASS]' if passed else '[FAIL]'
        print(f'  {marker} {country}/{brand}: {summary}')

    return 0 if all(r[2] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
