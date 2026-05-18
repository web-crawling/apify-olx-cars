"""Syntax and JSON-validity checker for olx-cars implementation files.

Checks:
1. Python AST parse for all modified .py files
2. JSON parse for all modified .json files

Usage:
    python scripts/check_olx_cars_syntax.py

Exit code: 0 = all OK, 1 = any error.
"""

import ast
import json
import sys
from pathlib import Path

ACTOR_ROOT = Path(__file__).parent.parent

PY_FILES = [
    "src/items.py",
    "src/itemloaders.py",
    "src/pipelines.py",
    "src/settings.py",
    "src/main.py",
    "src/spiders/olx_cars.py",
    "scripts/qa_C_single.py",
    "scripts/qa_C_e2e.py",
]

JSON_FILES = [
    ".actor/input_schema.json",
    ".actor/dataset_schema.json",
]

errors = []
ok = []

print("=== Python syntax check ===")
for rel in PY_FILES:
    path = ACTOR_ROOT / rel
    try:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        print(f"  OK   {rel}")
        ok.append(rel)
    except SyntaxError as e:
        msg = f"  ERR  {rel}: SyntaxError at line {e.lineno}: {e.msg}"
        print(msg)
        errors.append(msg)
    except FileNotFoundError:
        msg = f"  ERR  {rel}: file not found"
        print(msg)
        errors.append(msg)

print()
print("=== JSON validity check ===")
for rel in JSON_FILES:
    path = ACTOR_ROOT / rel
    try:
        text = path.read_text(encoding="utf-8")
        json.loads(text)
        print(f"  OK   {rel}")
        ok.append(rel)
    except json.JSONDecodeError as e:
        msg = f"  ERR  {rel}: JSONDecodeError at line {e.lineno} col {e.colno}: {e.msg}"
        print(msg)
        errors.append(msg)
    except FileNotFoundError:
        msg = f"  ERR  {rel}: file not found"
        print(msg)
        errors.append(msg)

print()
print(f"=== Results: {len(ok)} OK, {len(errors)} errors ===")
if errors:
    print("FAIL")
    sys.exit(1)
else:
    print("ALL PASS")
    sys.exit(0)
