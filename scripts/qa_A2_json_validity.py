"""QA Test A2 -- JSON validity: every file under .actor/ parses cleanly."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ACTOR_DIR = ROOT / ".actor"

ok = True
for path in sorted(ACTOR_DIR.glob("*.json")):
    try:
        json.loads(path.read_text(encoding="utf-8"))
        print(f"PASS -- {path.name}")
    except json.JSONDecodeError as exc:
        print(f"FAIL -- {path.name}: {exc}")
        ok = False

print(f"\nResult: {'ALL PASS' if ok else 'FAILURES FOUND'}")
sys.exit(0 if ok else 1)
