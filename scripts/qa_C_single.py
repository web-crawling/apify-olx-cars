"""Single-scenario Scrapy runner for QA.

Called by qa_C_e2e_runner.py for each scenario in a fresh subprocess.
Usage: python qa_C_single.py <scenario_json_b64> <output_file>
"""

import base64
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ACTOR_ROOT))

scenario_json = base64.b64decode(sys.argv[1]).decode("utf-8")
scenario = json.loads(scenario_json)
out_file = sys.argv[2]

input_data = dict(scenario["input"])
input_data.setdefault("country", "ro")
input_data.setdefault("sortBy", "created_at:desc")
input_data.setdefault("maxItems", 100)
input_data.setdefault("startUrls", [])
input_data.setdefault("brands", [])

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from src.spiders.olx_cars import OlxCarsSpider

settings = get_project_settings()
settings.setmodule("src.settings")
settings.set("INPUT_DATA", input_data, priority="spider")
settings.set("FEEDS", {out_file: {"format": "jsonlines", "overwrite": True}}, priority="spider")
settings.set("LOG_LEVEL", "WARNING")
settings.set(
    "ITEM_PIPELINES",
    {
        "src.pipelines.MaxItemsPipeline": 100,
        "src.pipelines.DropNonesPipeline": 500,
    },
    priority="spider",
)

OlxCarsSpider.crawl_failed = False

process = CrawlerProcess(settings)
process.crawl(OlxCarsSpider)
process.start()

result = {
    "crawl_failed": OlxCarsSpider.crawl_failed,
    "skipped_partner_count": 0,  # will read from logs
}
print(json.dumps(result))
