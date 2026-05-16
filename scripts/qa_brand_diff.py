"""QA — diff brand_categories.json against a baseline snapshot.

For PR #32 (refresh RO/PL/BG via listing-based discovery + fix PL to
discover standalone instead of inheriting RO), assert:
  * RO, PL, BG each gained at least 1 brand (positive refresh).
  * RO has no drops vs baseline. Union-with-existing guarantees this.
  * BG has no drops vs baseline. Same guarantee.
  * PL is allowed to drop ``alte marci`` (a Romanian-only label that
    was incorrectly inherited from RO; cat 209 still exists on olx.pl
    but under the native Polish label ``pozostałe osobowe``). No other
    drops permitted.
  * RO and PL maps MAY differ (PL no longer inherits RO).
  * PT / UA / KZ are byte-equal to the baseline (untouched).

Usage:
    python scripts/qa_brand_diff.py <baseline.json> <current.json>
"""

from __future__ import annotations

import io
import json
import sys


REFRESHED = ('ro', 'pl', 'bg')
UNTOUCHED = ('pt', 'ua', 'kz')

# Drops allowed per country. Used to scrub Romanian-only labels that
# were incorrectly inherited into PL pre-#32 (when PL=copy(RO)). The
# corresponding cat-ids still exist on olx.pl but under native Polish
# labels (e.g. cat 209 is 'pozostałe osobowe' on olx.pl, 'alte marci'
# on olx.ro). Any other drop signals a regression.
ALLOWED_DROPS = {
    'ro': set(),
    'pl': {'alte marci'},
    'bg': set(),
}


def load(path: str) -> dict[str, dict[str, int]]:
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

    for cc in REFRESHED:
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
        if not added:
            print(f'  FAIL: {cc} added no new brands (positive refresh expected)')
            failed = True

    for cc in UNTOUCHED:
        if (baseline.get(cc) or {}) != (current.get(cc) or {}):
            base_map = baseline.get(cc) or {}
            cur_map = current.get(cc) or {}
            added = sorted(set(cur_map) - set(base_map))
            dropped = sorted(set(base_map) - set(cur_map))
            print(f'FAIL: {cc} should be untouched; added={added} dropped={dropped}')
            failed = True
        else:
            print(f'[{cc}] unchanged ({len(current.get(cc) or {})} brands)')

    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
