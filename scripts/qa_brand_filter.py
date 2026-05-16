"""Live QA — verify brand-filter resolution for PT, UA, KZ.

For each country, runs the spider with brands=["BMW"] and a small
maxItems cap, then asserts every output row has make=="bmw" (case
insensitive). Failures indicate that the brand-leaf category wasn't
resolved and the spider fell back to the parent cars category.
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

COUNTRIES = ('pt', 'ua', 'kz')
MAX_ITEMS = 15


def run_scenario(country: str) -> tuple[bool, list[dict], str]:
    scenario = {
        'name': f'{country}-brand-bmw',
        'input': {
            'country': country,
            'brands': ['BMW'],
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


def assess(country: str, items: list[dict]) -> tuple[bool, str]:
    if not items:
        return False, 'no items produced'
    makes = [(it.get('make') or '').strip().lower() for it in items]
    bmw_count = sum(1 for m in makes if m == 'bmw')
    other = [m for m in makes if m and m != 'bmw']
    pct_bmw = 100 * bmw_count / len(items)
    msg = (
        f'{len(items)} items, {bmw_count} BMW ({pct_bmw:.0f}%), '
        f'others: {sorted(set(other))[:5]}'
    )
    return pct_bmw == 100, msg


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print('Live QA — brand filter resolution\n')
    results: list[tuple[str, bool, str]] = []
    for country in COUNTRIES:
        print(f'  [{country}] running spider with brands=["BMW"], maxItems={MAX_ITEMS} ...')
        ok, items, stderr = run_scenario(country)
        if not ok:
            print(f'  [{country}] spider crashed')
            print(stderr[-800:])
            results.append((country, False, 'spider exit != 0'))
            continue
        passed, summary = assess(country, items)
        marker = 'PASS' if passed else 'FAIL'
        print(f'  [{country}] {marker} — {summary}')
        results.append((country, passed, summary))

    print('\nSummary:')
    for country, passed, summary in results:
        marker = '[PASS]' if passed else '[FAIL]'
        print(f'  {marker} {country}: {summary}')

    return 0 if all(p for _, p, _ in results) else 1


if __name__ == '__main__':
    sys.exit(main())
