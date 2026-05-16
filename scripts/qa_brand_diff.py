"""QA — diff brand_categories.json against a baseline snapshot.

Generic comparator. For each of the 6 countries, reports added and
dropped brand keys vs the baseline. Fails on any drop not listed in
``ALLOWED_DROPS`` — refreshes should be additive.

Also normalises both old-format (``{brand: cat_id}``) and new-format
(``{brand: {id, label}}``) entries to a uniform key set, so the diff
is meaningful across the #40 schema migration.

Usage:
    python scripts/qa_brand_diff.py <baseline.json> <current.json>
"""

from __future__ import annotations

import io
import json
import sys


ALL_COUNTRIES = ('ro', 'pl', 'bg', 'pt', 'ua', 'kz')

# Drops allowed per country. Used to scrub Romanian-only labels that
# were incorrectly inherited into PL pre-#32 (when PL=copy(RO)). The
# corresponding cat-ids still exist on olx.pl but under native Polish
# labels (e.g. cat 209 is 'pozostałe osobowe' on olx.pl, 'alte marci'
# on olx.ro). Any other drop signals a regression.
ALLOWED_DROPS = {
    'ro': set(),
    'pl': {'alte marci'},
    'bg': set(),
    'pt': set(),
    'ua': set(),
    'kz': set(),
}


def load(path: str) -> dict[str, dict]:
    with open(path, encoding='utf-8') as fh:
        raw = json.load(fh)
    return {k: v for k, v in raw.items() if not k.startswith('_')}


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    baseline = load(sys.argv[1])
    current = load(sys.argv[2])

    failed = False

    for cc in ALL_COUNTRIES:
        base_map = baseline.get(cc) or {}
        cur_map = current.get(cc) or {}
        added = sorted(set(cur_map) - set(base_map))
        dropped = sorted(set(base_map) - set(cur_map))
        print(f'[{cc}] baseline={len(base_map)} current={len(cur_map)}')
        if added:
            print(f'  added ({len(added)}): {added}')
        unexpected_drops = sorted(set(dropped) - ALLOWED_DROPS.get(cc, set()))
        if unexpected_drops:
            print(f'  DROPPED ({len(unexpected_drops)}): {unexpected_drops}  -- FAIL')
            failed = True
        elif dropped:
            print(f'  allowed-dropped ({len(dropped)}): {dropped}')

    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
