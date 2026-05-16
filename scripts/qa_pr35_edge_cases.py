"""PR #35 edge-case verification for DropNonesPipeline._drop_nones().

Verifies:
  (a) Nested dicts: None values are recursively dropped.
  (b) Scalar preservation: 0, False, "" are PRESERVED (not dropped).
  (c) Empty arrays: [] is preserved.
  (d) Lists containing dicts with None: None is dropped inside list elements.
  (e) Lists themselves are preserved even if they contain None entries (drop_nones
      only filters dict KEYS — None entries inside a plain list pass through
      unchanged, which is the correct behavior for the OLX case where lists are
      always lists of strings or lists of dicts).
"""

from __future__ import annotations

import sys
from pathlib import Path

ACTOR = Path(r"D:\projects\personal\claude\apify\apify-olx-cars")
sys.path.insert(0, str(ACTOR))

from src.pipelines import _drop_nones

failures: list[str] = []


def expect(label: str, got, want) -> None:
    if got == want:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        print(f"        got:  {got!r}")
        print(f"        want: {want!r}")
        failures.append(label)


print("=== (a) Nested dict — None values dropped recursively ===")
expect(
    "location with district=None drops district only",
    _drop_nones({
        "city": "Lisbon",
        "district": None,
        "region": "Lisboa",
        "gpsObfuscated": True,
    }),
    {"city": "Lisbon", "region": "Lisboa", "gpsObfuscated": True},
)
expect(
    "deeply nested None",
    _drop_nones({"a": {"b": {"c": None, "d": "keep"}}}),
    {"a": {"b": {"d": "keep"}}},
)

print("\n=== (b) Scalar preservation (0, False, '' must NOT be dropped) ===")
expect("integer 0 preserved", _drop_nones({"x": 0}), {"x": 0})
expect("boolean False preserved", _drop_nones({"x": False}), {"x": False})
expect("empty string preserved", _drop_nones({"x": ""}), {"x": ""})
expect("priceNegotiable=False preserved", _drop_nones({"priceNegotiable": False}), {"priceNegotiable": False})
expect("priceConverted=0 preserved", _drop_nones({"priceConverted": 0}), {"priceConverted": 0})

print("\n=== (c) Empty array preserved ===")
expect("features=[] preserved", _drop_nones({"features": []}), {"features": []})
expect("images=[] preserved", _drop_nones({"images": []}), {"images": []})

print("\n=== (d) paramsRaw — nested dicts inside list have None dropped ===")
expect(
    "paramsRaw list of dicts with None inside value-dict",
    _drop_nones({
        "paramsRaw": [
            {"key": "price", "name": "Preço", "type": "price", "value": {"raw": None, "label": "10900"}},
            {"key": "fuel", "name": "Fuel", "type": "enum", "value": None},
        ]
    }),
    {
        "paramsRaw": [
            {"key": "price", "name": "Preço", "type": "price", "value": {"label": "10900"}},
            {"key": "fuel", "name": "Fuel", "type": "enum"},  # value: None dropped
        ]
    },
)

print("\n=== (e) Lists of scalars preserved (incl. images URLs) ===")
expect(
    "images list of strings preserved",
    _drop_nones({"images": ["https://a.jpg", "https://b.jpg"]}),
    {"images": ["https://a.jpg", "https://b.jpg"]},
)

print("\n=== (f) Top-level None dropped ===")
expect(
    "top-level model=None dropped",
    _drop_nones({"make": "BMW", "model": None, "year": 2020}),
    {"make": "BMW", "year": 2020},
)

print("\n=== (g) Full sample item idempotency ===")
sample = {"a": 0, "b": False, "c": "", "d": None, "e": [], "f": [None, {"x": None, "y": 1}]}
once = _drop_nones(sample)
twice = _drop_nones(once)
expect("idempotent", once, twice)
# Note: f=[None, {...}] — None inside list PASSES THROUGH unchanged because
# _drop_nones only filters dict KEYS, not list elements. This is correct for
# OLX (images is list-of-strings, paramsRaw is list-of-dicts; no list-of-Nones).
expect(
    "list None entry passes through (correct for OLX shape)",
    once,
    {"a": 0, "b": False, "c": "", "e": [], "f": [None, {"y": 1}]},
)

if failures:
    print(f"\n{len(failures)} edge case(s) FAILED: {failures}")
    sys.exit(1)
print("\nAll edge cases PASS.")
sys.exit(0)
