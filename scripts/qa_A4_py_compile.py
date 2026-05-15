"""QA Test A4 -- py_compile: every .py file under apify-olx-cars/ compiles cleanly."""

import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

ok = True
for path in sorted(ROOT.rglob("*.py")):
    parts = path.parts
    if ".venv" in parts or "__pycache__" in parts:
        continue
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"PASS -- {path.relative_to(ROOT)}")
    except py_compile.PyCompileError as exc:
        print(f"FAIL -- {path.relative_to(ROOT)}: {exc}")
        ok = False

print(f"\nResult: {'ALL PASS' if ok else 'FAILURES FOUND'}")
sys.exit(0 if ok else 1)
