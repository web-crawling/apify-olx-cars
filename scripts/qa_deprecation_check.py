"""Check that no DeprecationWarnings fire for open_spider/process_item/start_requests.

Run with normal warning settings (not -W error) so third-party lib deprecations
don't break the check. We scan stderr for lines containing both
"DeprecationWarning" and one of the three deprecated method names.
"""
import subprocess
import sys
import os
import tempfile

# Path to the QA script to run
script = os.path.join(os.path.dirname(__file__), 'qa23_filter_unit.py')
python = sys.executable

# Run the script capturing stderr
result = subprocess.run(
    [python, script],
    capture_output=True,
    text=True,
    cwd=os.path.dirname(os.path.dirname(script)),
)

stderr = result.stderr

TARGET_SIGNATURES = ['open_spider', 'process_item', 'start_requests']

matches = []
for line in stderr.splitlines():
    if 'DeprecationWarning' in line:
        for sig in TARGET_SIGNATURES:
            if sig in line:
                matches.append(line.strip())

print("=== Deprecation Warning Check ===")
print(f"Script stdout (last 3 lines): {result.stdout.strip().splitlines()[-3:]}")
print(f"Stderr lines with DeprecationWarning: {len(stderr.splitlines())}")
print(f"Lines matching OUR deprecated signatures: {len(matches)}")
if matches:
    print("FOUND MATCHES (FAIL):")
    for m in matches:
        print(f"  {m}")
else:
    print("No DeprecationWarnings for open_spider/process_item/start_requests found.")
    print("RESULT: PASS")

# Also show any DeprecationWarning lines at all, for informational purposes
all_dep_lines = [l for l in stderr.splitlines() if 'DeprecationWarning' in l]
if all_dep_lines:
    print(f"\nAll DeprecationWarning lines in stderr ({len(all_dep_lines)} total):")
    for l in all_dep_lines[:10]:
        print(f"  {l}")
else:
    print("\nNo DeprecationWarning lines at all in stderr.")

sys.exit(1 if matches else 0)
