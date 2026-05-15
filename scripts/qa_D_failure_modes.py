"""QA Test D -- Failure-mode verification.

1. Verify spider sets crawl_failed = True on non-200/400 HTTP responses.
2. Verify main.py uses OlxCarsSpider.crawl_failed (CLASS attr, not instance).
3. Static code check: errback_fatal sets type(self).crawl_failed = True.
4. Static code check: parse_listing sets type(self).crawl_failed on unexpected status.
"""

import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ACTOR_ROOT = Path(__file__).parent.parent
SPIDER_PY = ACTOR_ROOT / "src" / "spiders" / "olx_cars.py"
MAIN_PY = ACTOR_ROOT / "src" / "main.py"

ok = True

def check(label, condition, details=""):
    global ok
    status = "PASS" if condition else "FAIL"
    if not condition:
        ok = False
    msg = f"{status} -- {label}"
    if details:
        msg += f"\n    {details}"
    print(msg)

spider_text = SPIDER_PY.read_text(encoding="utf-8")
main_text = MAIN_PY.read_text(encoding="utf-8")

# D1: errback_fatal sets type(self).crawl_failed = True (not self.crawl_failed)
has_errback_class_attr = "type(self).crawl_failed = True" in spider_text
check(
    "Spider errback_fatal uses type(self).crawl_failed = True (class attribute)",
    has_errback_class_attr,
    "Look for 'type(self).crawl_failed = True' in errback_fatal"
)

# D2: parse_listing also sets type(self).crawl_failed for non-200/400 responses
has_parse_class_attr = spider_text.count("type(self).crawl_failed = True") >= 2
check(
    "Spider parse_listing also sets type(self).crawl_failed = True (multiple usages)",
    has_parse_class_attr,
    f"Found {spider_text.count('type(self).crawl_failed = True')} occurrences of type(self).crawl_failed = True"
)

# D3: main.py checks OlxCarsSpider.crawl_failed (class attribute), NOT getattr(spider, ...)
has_class_check = "OlxCarsSpider.crawl_failed" in main_text
check(
    "main.py checks OlxCarsSpider.crawl_failed (class attribute)",
    has_class_check,
    "Grep result: " + ("found" if has_class_check else "NOT found")
)

# Check for live code (not comments) using getattr on spider for crawl_failed
# Strip comment lines before checking
main_code_lines = [l for l in main_text.splitlines() if not l.strip().startswith("#")]
main_code_only = "\n".join(main_code_lines)
has_bad_getattr = "getattr(spider" in main_code_only.lower() or "getattr(crawl" in main_code_only.lower()
check(
    "main.py does NOT use getattr(spider_instance, ...) in live code (comments are OK)",
    not has_bad_getattr,
    "Found forbidden getattr(spider...) in non-comment code" if has_bad_getattr else ""
)

# D4: crawl_failed is declared as class attribute in spider
has_class_decl = re.search(r"crawl_failed\s*:\s*bool\s*=\s*False", spider_text)
check(
    "OlxCarsSpider.crawl_failed is declared as class attribute (not instance)",
    bool(has_class_decl),
    "Pattern: 'crawl_failed: bool = False' at class level"
)

# D5: main.py resets the class attr before each run
has_reset = "OlxCarsSpider.crawl_failed = False" in main_text
check(
    "main.py resets OlxCarsSpider.crawl_failed = False before each run",
    has_reset,
    "Prevents false positives on re-runs in same process"
)

# D6: main.py calls Actor.fail() when crawl_failed
has_actor_fail = "await Actor.fail(" in main_text
check(
    "main.py calls await Actor.fail() when crawl_failed is True",
    has_actor_fail,
    "Propagates fatal errors to Apify platform"
)

# D7: HTTP 400 at offset>0 is NOT treated as crawl_failed
# Check the parse_listing logic: offset > 0 path returns without setting crawl_failed
# The code path: if response.status == 400: if offset > 0: logger.debug(...); return
check(
    "HTTP 400 at offset>0 is treated as normal pagination cap (not crawl_failed)",
    "response.status == 400" in spider_text and "crawl_failed" not in spider_text.split("response.status == 400")[1][:200],
    "The 400-status block must not set crawl_failed"
)

print(f"\nResult: {'ALL PASS' if ok else 'FAILURES FOUND'}")
sys.exit(0 if ok else 1)
