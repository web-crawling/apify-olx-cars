"""E2E QA for Issue #24: Compact / LLM-friendly output mode.

Runs the OLX Cars spider in-process twice against country='ro', brands=['BMW'],
maxItems=20.  Neither run uses the Apify SDK (no Actor context) — items are
written to a JSONL temp file via Scrapy FEEDS.

PIPELINE OVERRIDE RATIONALE
============================
Production pipeline chain (settings.py):
  100  MaxItemsPipeline
  150  HistoryFilterPipeline
  200  IncrementalDiffPipeline
  250  NotificationBufferPipeline
  500  DropNonesPipeline
  600  FairPricePipeline          <- raises DropItem for EVERY item
  700  OutputShapingPipeline
 1000  (Apify push -- omitted here, replaced by FEEDS)

Because FairPricePipeline raises DropItem at 600, NO item ever reaches
OutputShapingPipeline (700) through the Scrapy chain.  In production,
shape_output() is called from main.py's post-crawl blocks (MISSING items
and FairPrice buffer), not through the pipeline.

To exercise OutputShapingPipeline directly in this QA harness, we OMIT
FairPricePipeline from the override so items flow all the way through to
OutputShapingPipeline -> FEEDS writer.  This tests the pipeline class in
isolation.  The post-crawl main.py path (FairPrice buffer + MISSING items)
is exercised by the live Apify run in orchestrator Step 6.

We also omit IncrementalDiffPipeline and NotificationBufferPipeline (they
need a KV snapshot context) -- but retain MaxItemsPipeline, HistoryFilterPipeline,
and DropNonesPipeline to keep the chain as close to production as possible.

TWO-SUBPROCESS PATTERN
========================
Scrapy's Twisted reactor can only be started once per process.  We run
each crawl scenario in a fresh subprocess so both runs can use an
independent reactor.  This is the standard pattern for multi-run QA harnesses.

Usage:
    .venv/Scripts/python scripts/qa_pr_compact_mode_e2e.py

Exit codes:
    0 -- all assertions pass
    1 -- one or more assertions failed or crawl blocked
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Force UTF-8 on Windows stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ACTOR_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# WORKER MODULE
# When this script is invoked with --worker <run_id> <out_path>, it runs
# as a subprocess performing a single crawl.
# ---------------------------------------------------------------------------
if len(sys.argv) >= 4 and sys.argv[1] == '--worker':
    # Worker mode: argv = [script, '--worker', run_id, out_path]
    run_id = sys.argv[2]   # '1' = full, '2' = compact
    out_path = sys.argv[3]

    sys.path.insert(0, str(ACTOR_ROOT))

    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    from src.spiders.olx_cars import OlxCarsSpider
    from src.pipelines import FairPricePipeline, OutputShapingPipeline

    QA_PIPELINE_OVERRIDE = {
        'src.pipelines.MaxItemsPipeline': 100,
        'src.pipelines.HistoryFilterPipeline': 150,
        # IncrementalDiffPipeline omitted -- requires KV snapshot context
        # NotificationBufferPipeline omitted -- depends on IncrementalDiffPipeline
        'src.pipelines.DropNonesPipeline': 500,
        # FairPricePipeline intentionally OMITTED so items reach OutputShapingPipeline
        'src.pipelines.OutputShapingPipeline': 700,
        # Apify push (1000) replaced by FEEDS writer
    }

    if run_id == '1':
        extra_input = {'outputMode': 'full', 'descriptionMaxLength': None}
    else:
        extra_input = {'outputMode': 'compact', 'descriptionMaxLength': 200}

    input_data = {
        'country': 'ro',
        'brands': ['BMW'],
        'maxItems': 20,
        'sortBy': 'created_at:desc',
        'startUrls': [],
        'query': None,
        'yearFrom': None,
        'yearTo': None,
        'priceFrom': None,
        'priceTo': None,
        'priceCurrency': 'EUR',
        'sellerType': 'any',
        'excludeDamaged': False,
        'firstOwnerOnly': False,
        'serviceBookOnly': False,
        'incrementalMode': False,
        'stateKey': 'olx-cars-state',
        'emitUnchanged': False,
        'emitMissing': False,
        '_snapshot': {},
        '_runTs': '2026-05-18T00:00:00Z',
        'notifyOn': 'none',
        'notifyMinPriceDropPct': 5,
        'notifyTopN': 20,
        'notifyWebhookUrl': '',
        **extra_input,
    }

    settings = get_project_settings()
    settings.setmodule('src.settings')
    settings.set('INPUT_DATA', input_data, priority='spider')
    settings.set('FEEDS', {out_path: {'format': 'jsonlines', 'overwrite': True}},
                 priority='spider')
    settings.set('ITEM_PIPELINES', QA_PIPELINE_OVERRIDE, priority='spider')
    settings.set('LOG_LEVEL', 'WARNING')

    OlxCarsSpider.crawl_failed = False
    FairPricePipeline.items_buffer = []
    FairPricePipeline.keys_buffer = []

    process = CrawlerProcess(settings)
    process.crawl(OlxCarsSpider)
    process.start()
    sys.exit(0)


# ---------------------------------------------------------------------------
# ORCHESTRATOR MODE (main invocation)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(ACTOR_ROOT))
from src.pipelines import COMPACT_FIELDS  # noqa: E402 — after sys.path setup


def run_crawl_subprocess(run_id: str, out_path: str) -> tuple[list[dict], str]:
    """Spawn a worker subprocess and return (items, stderr_tail)."""
    python = sys.executable
    script = str(Path(__file__).resolve())
    result = subprocess.run(
        [python, script, '--worker', run_id, out_path],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(ACTOR_ROOT),
    )
    stderr_tail = result.stderr[-3000:] if result.stderr else ''
    items: list[dict] = []
    p = Path(out_path)
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return items, stderr_tail, result.returncode


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
_pass_count = 0
_fail_count = 0
_failures: list[str] = []


def check(name: str, condition: bool, msg: str = '') -> bool:
    global _pass_count, _fail_count
    if condition:
        _pass_count += 1
        print(f'    PASS  {name}')
        return True
    else:
        _fail_count += 1
        detail = f': {msg}' if msg else ''
        _failures.append(f'{name}{detail}')
        print(f'    FAIL  {name}{detail}')
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print('=' * 65)
    print('E2E QA -- Compact / LLM-friendly output mode (Issue #24)')
    print('country=ro, brands=[BMW], maxItems=20')
    print('=' * 65)

    # -----------------------------------------------------------------------
    # Run 1: Full mode (outputMode=full, no descriptionMaxLength)
    # -----------------------------------------------------------------------
    print('\n[Run 1] Full mode -- outputMode=full, no descriptionMaxLength')
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as tmp:
        run1_path = tmp.name

    try:
        items_run1, stderr1, rc1 = run_crawl_subprocess('1', run1_path)
    except subprocess.TimeoutExpired:
        print('  BLOCKED: crawl timed out (>180s)')
        return 1
    except Exception as exc:
        print(f'  BLOCKED: subprocess error: {exc}')
        return 1

    if rc1 != 0:
        print(f'  WARNING: worker exited with code {rc1}')
        if stderr1:
            print(f'  stderr tail:\n{stderr1[-500:]}')

    print(f'  Items returned: {len(items_run1)}')

    check('R1-1: at least 1 item returned', len(items_run1) >= 1,
          f'got {len(items_run1)}')

    if items_run1:
        non_compact_present = any(
            bool(set(item.keys()) - COMPACT_FIELDS)
            for item in items_run1
        )
        check(
            'R1-2: at least one item has fields outside COMPACT_FIELDS',
            non_compact_present,
            'all items look like compact output in full mode',
        )

        has_images = any('images' in item for item in items_run1)
        has_seller = any('seller' in item for item in items_run1)
        check('R1-3: at least one item has images field', has_images)
        check('R1-4: at least one item has seller field', has_seller)

        has_desc = any(
            item.get('description') and len(item['description']) > 0
            for item in items_run1
        )
        check('R1-5: at least one item has a non-empty description', has_desc)

    # -----------------------------------------------------------------------
    # Run 2: Compact mode + descriptionMaxLength=200
    # -----------------------------------------------------------------------
    print('\n[Run 2] Compact mode -- outputMode=compact, descriptionMaxLength=200')
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as tmp:
        run2_path = tmp.name

    try:
        items_run2, stderr2, rc2 = run_crawl_subprocess('2', run2_path)
    except subprocess.TimeoutExpired:
        print('  BLOCKED: crawl timed out (>180s)')
        return 1
    except Exception as exc:
        print(f'  BLOCKED: subprocess error: {exc}')
        return 1

    if rc2 != 0:
        print(f'  WARNING: worker exited with code {rc2}')
        if stderr2:
            print(f'  stderr tail:\n{stderr2[-500:]}')

    print(f'  Items returned: {len(items_run2)}')

    check('R2-1: at least 1 item returned', len(items_run2) >= 1,
          f'got {len(items_run2)}')

    if items_run2:
        bad_items = []
        for i, item in enumerate(items_run2):
            extra = set(item.keys()) - COMPACT_FIELDS
            if extra:
                bad_items.append((i, sorted(extra)))
        check(
            'R2-2: every emitted item has only keys in COMPACT_FIELDS',
            len(bad_items) == 0,
            f'items with extra fields: {bad_items[:3]}',
        )

        long_descs = [
            (i, len(item['description']))
            for i, item in enumerate(items_run2)
            if 'description' in item and len(item['description']) > 200
        ]
        check(
            'R2-3: every description <= 200 chars',
            len(long_descs) == 0,
            f'items with long descriptions: {long_descs[:3]}',
        )

        expected_absent = [
            'images', 'seller', 'location', 'paramsRaw',
            'scrapedAt', 'postedAt', 'priceVsMedianPct', 'priceRating',
        ]
        for field in expected_absent:
            present_in = [i for i, item in enumerate(items_run2) if field in item]
            check(
                f'R2-4: field {field!r} absent from all compact items',
                len(present_in) == 0,
                f'found in items: {present_in[:3]}',
            )

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print('\n' + '=' * 65)
    total = _pass_count + _fail_count
    print(f'Results: {_pass_count}/{total} PASS, {_fail_count}/{total} FAIL')

    if _failures:
        print('\nFailed assertions:')
        for msg in _failures:
            print(f'  - {msg}')
        print('\nFINAL: FAIL')
        return 1

    print('\nFINAL: ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
