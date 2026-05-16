"""Live QA — issue #40: assert `make` is populated across query paths.

Three scenarios validate the make-extraction fix:

  1. startUrls on the parent cars cat URL (RO) — exercises the new
     reverse-lookup path. Pre-fix returned `make=None` for all items.
  2. Structured filters country=ro, brands=[BMW] — exercises the
     existing slice-level `cat_l2_name` capture (regression check).
  3. Structured filters country=pl, brands=[Dacia] — exercises the
     PL standalone brand map (regression check, follows PR #39).

For each scenario the script runs the spider via `qa_C_single.py`,
collects items into a JSONL file, and asserts every item has a
non-empty `make` value. Failures print a sample of the offending items.
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

SCENARIOS: tuple[dict, ...] = (
    {
        'name': 'starturls-ro-parent-cat',
        'input': {
            'startUrls': [
                {'url': 'https://www.olx.ro/auto-masini-moto-ambarcatiuni/autoturisme/'}
            ],
            'country': 'ro',
            'maxItems': 15,
        },
    },
    {
        'name': 'filters-ro-bmw',
        'input': {
            'country': 'ro',
            'brands': ['BMW'],
            'maxItems': 15,
        },
    },
    {
        'name': 'filters-pl-dacia',
        'input': {
            'country': 'pl',
            'brands': ['Dacia'],
            'maxItems': 15,
        },
    },
)


def run_scenario(scenario: dict) -> tuple[bool, list[dict], str]:
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
        items: list[dict] = []
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


def assess(items: list[dict]) -> tuple[bool, str]:
    if not items:
        return False, 'no items produced'
    missing = [it for it in items if not (it.get('make') or '').strip()]
    populated = len(items) - len(missing)
    msg = f'{len(items)} items, {populated} with make ({100 * populated / len(items):.0f}%)'
    if missing:
        sample = [
            {'url': it.get('url'), 'model': it.get('model'), 'category_id': (it.get('paramsRaw') or [{}])[0].get('category_id') if it.get('paramsRaw') else None}
            for it in missing[:3]
        ]
        msg += f' | missing samples: {sample}'
    return not missing, msg


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print('Live QA - make field coverage (issue #40)\n')
    results: list[tuple[str, bool, str]] = []
    for sc in SCENARIOS:
        name = sc['name']
        print(f'  [{name}] running spider, input keys = {list(sc["input"].keys())}')
        ok, items, stderr = run_scenario(sc)
        if not ok:
            print(f'  [{name}] spider crashed')
            print(stderr[-800:])
            results.append((name, False, 'spider exit != 0'))
            continue
        passed, summary = assess(items)
        marker = 'PASS' if passed else 'FAIL'
        print(f'  [{name}] {marker} - {summary}')
        # Sample 2 items
        for it in items[:2]:
            print(f'      sample: make={it.get("make")!r} model={it.get("model")!r} country={it.get("country")!r}')
        results.append((name, passed, summary))

    print('\nSummary:')
    for name, passed, summary in results:
        marker = '[PASS]' if passed else '[FAIL]'
        print(f'  {marker} {name}: {summary}')

    return 0 if all(r[1] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
