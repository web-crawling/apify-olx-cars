"""Micro-tests for PR #14 + #16 inputs.

Tests:
  1. _make_year_bands(step) - correct structure, head/tail open-ended entries.
  2. _make_price_bands(step) - correct structure, open upper band.
  3. The 4 new input keys (filterByCurrency, pageLimit, sliceYearStep,
     slicePriceStep) are present in main.py's INPUT_DATA allow-list.

Usage:
    .venv/Scripts/python scripts/qa_issue14_16_inputs.py

Exit code:
    0 -- all assertions pass
    1 -- one or more assertions failed
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAIN_PY = ROOT / "src" / "main.py"

# ---------------------------------------------------------------------------
# Import helpers from spider without running the full Scrapy machinery.
# We need _make_year_bands and _make_price_bands.
# ---------------------------------------------------------------------------

def _import_band_helpers():
    """Import _make_year_bands and _make_price_bands from the spider module."""
    import importlib.util
    spider_path = ROOT / "src" / "spiders" / "olx_cars.py"
    spec = importlib.util.spec_from_file_location("olx_cars_spider", spider_path)
    module = importlib.util.module_from_spec(spec)
    # The spider imports from parent packages that may not be importable in
    # isolation. We only need the two module-level functions, which are defined
    # BEFORE any class code and only depend on built-ins. We can extract them
    # directly by reading the source and exec-ing the preamble.
    return module


def _exec_band_helpers():
    """Execute just the _make_year_bands / _make_price_bands defs from the spider source.

    This avoids importing the full Scrapy/Apify stack during unit testing.
    """
    spider_source = (ROOT / "src" / "spiders" / "olx_cars.py").read_text(encoding="utf-8")
    ns: dict = {}
    # Find and exec only the relevant helper block.
    # We look for the 'Dynamic band helpers' section.
    lines = spider_source.splitlines()
    start = None
    end = None
    for i, line in enumerate(lines):
        if "_YEAR_MIN" in line and start is None:
            start = i
        if "# ---------------------------------------------------------------------------" in line and start is not None and i > start + 5:
            end = i
            break
    if start is None:
        raise RuntimeError("Could not find _make_year_bands definition block in olx_cars.py")
    block = "\n".join(lines[start:end])
    exec(block, ns)  # noqa: S102
    return ns["_make_year_bands"], ns["_make_price_bands"], ns["_YEAR_MIN"], ns["_YEAR_MAX"], ns["_PRICE_MAX_EUR"]


def find_input_data_keys_from_source(source: str) -> list[str] | None:
    """Locate settings.set('INPUT_DATA', {...}) and return the dict keys."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "set":
            continue
        if not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and first.value == "INPUT_DATA"):
            continue
        if len(node.args) < 2 or not isinstance(node.args[1], ast.Dict):
            return None
        keys: list[str] = []
        for key_node in node.args[1].keys:
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                keys.append(key_node.value)
            else:
                return None
        return keys
    return None


failures: list[str] = []

def assert_true(condition: bool, message: str) -> None:
    if not condition:
        failures.append(f"FAIL: {message}")
        print(f"  FAIL: {message}")
    else:
        print(f"  PASS: {message}")


# ---------------------------------------------------------------------------
# Test 1: _make_year_bands
# ---------------------------------------------------------------------------
print("=== Test 1: _make_year_bands ===")
try:
    _make_year_bands, _make_price_bands, _YEAR_MIN, _YEAR_MAX, _PRICE_MAX_EUR = _exec_band_helpers()

    bands5 = _make_year_bands(5)
    # Head band: (None, _YEAR_MIN)
    assert_true(bands5[0] == (None, _YEAR_MIN), f"head band is (None, {_YEAR_MIN}), got {bands5[0]}")
    # Tail band: (_YEAR_MAX, None)
    assert_true(bands5[-1] == (_YEAR_MAX, None), f"tail band is ({_YEAR_MAX}, None), got {bands5[-1]}")
    # No gaps: each band's hi == next band's lo (for interior bands)
    interior = bands5[1:-1]
    for i in range(len(interior) - 1):
        lo_a, hi_a = interior[i]
        lo_b, hi_b = interior[i + 1]
        assert_true(
            hi_a == lo_b,
            f"interior bands contiguous at index {i+1}: {interior[i]} -> {interior[i+1]}",
        )
    # step=5 across 1900..2100 = 200 years / 5 = 40 interior bands + 2 open-ended = 42
    assert_true(len(bands5) == 42, f"step=5 should give 42 bands, got {len(bands5)}")
    print(f"  INFO: _make_year_bands(5) => {len(bands5)} bands")

    # step=1 should give 200 interior + 2 = 202
    bands1 = _make_year_bands(1)
    assert_true(bands1[0] == (None, _YEAR_MIN), "step=1 head band")
    assert_true(bands1[-1] == (_YEAR_MAX, None), "step=1 tail band")
    expected1 = (_YEAR_MAX - _YEAR_MIN) // 1 + 2
    assert_true(len(bands1) == expected1, f"step=1 gives {expected1} bands, got {len(bands1)}")

    # step=50 should give 200/50=4 interior + 2 = 6
    bands50 = _make_year_bands(50)
    assert_true(bands50[0] == (None, _YEAR_MIN), "step=50 head band")
    assert_true(bands50[-1] == (_YEAR_MAX, None), "step=50 tail band")
    assert_true(len(bands50) == 6, f"step=50 gives 6 bands, got {len(bands50)}")

except Exception as exc:
    failures.append(f"FAIL: _make_year_bands raised {exc}")
    print(f"  FAIL: _make_year_bands raised {exc}")

# ---------------------------------------------------------------------------
# Test 2: _make_price_bands
# ---------------------------------------------------------------------------
print("\n=== Test 2: _make_price_bands ===")
try:
    bands_p5000 = _make_price_bands(5000)
    # First band starts at 0
    assert_true(bands_p5000[0] == (0, 5000), f"first band should be (0, 5000), got {bands_p5000[0]}")
    # Last band is (_PRICE_MAX_EUR, None)
    assert_true(bands_p5000[-1] == (_PRICE_MAX_EUR, None), f"last band should be ({_PRICE_MAX_EUR}, None), got {bands_p5000[-1]}")
    # Second-to-last interior band ends at _PRICE_MAX_EUR
    assert_true(bands_p5000[-2][1] == _PRICE_MAX_EUR, f"penultimate band hi == {_PRICE_MAX_EUR}")
    # With step=5000 from 0..500000: 500000/5000=100 interior bands + 1 open-ended = 101
    expected_count = _PRICE_MAX_EUR // 5000 + 1
    assert_true(
        len(bands_p5000) == expected_count,
        f"step=5000 should give {expected_count} bands (100 + open-top), got {len(bands_p5000)}",
    )
    print(f"  INFO: _make_price_bands(5000) => {len(bands_p5000)} bands")

    # Contiguity: each band's hi == next band's lo for interior bands
    interior_p = bands_p5000[:-1]
    for i in range(len(interior_p) - 1):
        lo_a, hi_a = interior_p[i]
        lo_b, hi_b = interior_p[i + 1]
        assert_true(
            hi_a == lo_b,
            f"price bands contiguous at index {i+1}: {interior_p[i]} -> {interior_p[i+1]}",
        )

except Exception as exc:
    failures.append(f"FAIL: _make_price_bands raised {exc}")
    print(f"  FAIL: _make_price_bands raised {exc}")

# ---------------------------------------------------------------------------
# Test 3: 4 new keys present in main.py INPUT_DATA
# ---------------------------------------------------------------------------
print("\n=== Test 3: 4 new keys in main.py INPUT_DATA ===")
try:
    source = MAIN_PY.read_text(encoding="utf-8")
    keys = find_input_data_keys_from_source(source)
    if keys is None:
        failures.append("FAIL: could not locate settings.set('INPUT_DATA', {...}) in main.py")
        print("  FAIL: could not locate INPUT_DATA dict in main.py")
    else:
        keys_set = set(keys)
        for key in ("filterByCurrency", "pageLimit", "sliceYearStep", "slicePriceStep"):
            assert_true(key in keys_set, f"'{key}' present in main.py INPUT_DATA")
except Exception as exc:
    failures.append(f"FAIL: main.py INPUT_DATA key check raised {exc}")
    print(f"  FAIL: main.py INPUT_DATA key check raised {exc}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
if failures:
    print(f"RESULT: {len(failures)} failure(s):")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)
else:
    print("RESULT: ALL PASS")
    sys.exit(0)
