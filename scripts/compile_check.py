"""Compile check for parser-implementer deliverables."""
import py_compile
import sys

files = [
    'src/items.py',
    'src/itemloaders.py',
    'src/spiders/olx_cars.py',
]

errors = []
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f'OK  {f}')
    except py_compile.PyCompileError as e:
        print(f'ERR {f}: {e}')
        errors.append(f)

if errors:
    sys.exit(1)
else:
    print('\nAll files compiled successfully.')
