"""Static-analysis check: every input_schema.json property must appear as a
key in main.py's INPUT_DATA dict literal.

Background — issue #55 (suggested by qa during PR #53/#54 review):
    PR #53 added `serviceBookOnly` to `.actor/input_schema.json` and to
    `HistoryFilterPipeline`, but missed adding it to the hand-listed allow-list
    in `src/main.py` that builds `INPUT_DATA`. The pipeline silently saw
    `False` for every run; the filter never applied in production. Unit
    harnesses that mock `INPUT_DATA={...}` directly bypassed `main.py`, so
    the gap survived until live verification on build 1.0.19.

    This class of bug will recur every time we add a new input field. This
    script catches it pre-merge.

How it works:
    1. Parse `.actor/input_schema.json` and collect top-level `properties` keys
       (the public input surface — minus meta keys like `title`/`description`).
    2. AST-parse `src/main.py` and find the dict literal passed as the second
       positional arg to any `settings.set('INPUT_DATA', {...}, ...)` call.
    3. Assert every schema property is present as a key in that dict.

    INPUT_DATA may contain internal-only keys (those starting with `_`, e.g.
    `_snapshot`, `_runTs`) — these are not checked.

Usage:
    .venv/Scripts/python scripts/qa_input_passthrough.py

Exit code:
    0 — every input_schema property has a matching INPUT_DATA key.
    1 — at least one property is missing (prints the missing names).
    2 — could not locate the INPUT_DATA dict literal in main.py (refactor
        breakage — investigate before relying on this check).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INPUT_SCHEMA = ROOT / ".actor" / "input_schema.json"
MAIN_PY = ROOT / "src" / "main.py"


def collect_schema_properties() -> list[str]:
    """Return the list of top-level property names in `.actor/input_schema.json`."""
    schema = json.loads(INPUT_SCHEMA.read_text(encoding="utf-8"))
    properties = schema.get("properties") or {}
    return sorted(properties.keys())


def find_input_data_keys(source: str) -> list[str] | None:
    """Locate `settings.set('INPUT_DATA', {...}, ...)` and return the dict keys.

    Returns None if no matching call is found.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Match attribute call shaped like `<obj>.set(...)`
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "set":
            continue
        # First positional arg must be the literal string 'INPUT_DATA'
        if not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and first.value == "INPUT_DATA"):
            continue
        # Second positional arg must be a Dict literal
        if len(node.args) < 2 or not isinstance(node.args[1], ast.Dict):
            return None
        keys: list[str] = []
        for key_node in node.args[1].keys:
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                keys.append(key_node.value)
            else:
                # Non-string-literal key (e.g. **kwargs unpack, dynamic key).
                # We don't try to evaluate these — they make the static check
                # unreliable. Bail with None so the caller can flag this clearly.
                return None
        return keys
    return None


def main() -> int:
    print("=== INPUT_DATA Passthrough Audit ===")
    print(f"Schema:  {INPUT_SCHEMA.relative_to(ROOT)}")
    print(f"main.py: {MAIN_PY.relative_to(ROOT)}\n")

    schema_props = collect_schema_properties()
    source = MAIN_PY.read_text(encoding="utf-8")
    input_data_keys = find_input_data_keys(source)

    if input_data_keys is None:
        print(
            "FAIL -- could not locate `settings.set('INPUT_DATA', {...})` dict "
            "literal in src/main.py.\n"
            "If main.py was refactored (e.g. INPUT_DATA built dynamically or "
            "via dict unpack), update this script to match the new pattern."
        )
        return 2

    schema_set = set(schema_props)
    # Internal keys begin with `_` (e.g. `_snapshot`, `_runTs`) — exclude from
    # the diff since they have no schema counterpart by design.
    forwarded_set = {k for k in input_data_keys if not k.startswith("_")}

    print(f"input_schema.json properties ({len(schema_set)}): {sorted(schema_set)}")
    print(f"main.py INPUT_DATA keys ({len(forwarded_set)}): {sorted(forwarded_set)}")
    internal_keys = [k for k in input_data_keys if k.startswith("_")]
    if internal_keys:
        print(f"  (internal-only keys skipped: {sorted(internal_keys)})")
    print()

    missing = schema_set - forwarded_set
    extras = forwarded_set - schema_set

    ok = True
    if missing:
        print(
            f"FAIL -- {len(missing)} input_schema.json property(ies) NOT forwarded "
            f"by src/main.py INPUT_DATA: {sorted(missing)}"
        )
        print(
            "       Add the missing key(s) to the dict passed to "
            "`settings.set('INPUT_DATA', {...})` in src/main.py."
        )
        ok = False
    else:
        print("PASS -- every input_schema.json property is forwarded by INPUT_DATA.")

    if extras:
        print(
            f"FAIL -- {len(extras)} INPUT_DATA key(s) have NO matching "
            f"input_schema.json property: {sorted(extras)}"
        )
        print(
            "       Either add the property to input_schema.json, prefix the "
            "key with '_' to mark it as internal-only, or remove it from main.py."
        )
        ok = False
    else:
        print(
            "PASS -- no orphan keys in INPUT_DATA (every non-internal key has "
            "a matching schema property)."
        )

    print(f"\nResult: {'ALL PASS' if ok else 'FAILURES FOUND'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
