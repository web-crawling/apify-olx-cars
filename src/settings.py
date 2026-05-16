"""Scrapy settings for OLX Cars actor.

Per-domain concurrency and delay (from architecture doc and efficiency research):
  BG (www.olx.bg):  4 concurrent, 0.25s delay  — CloudFront headroom
  All others:       8 concurrent, 0.10s delay

For more details see:
  http://doc.scrapy.org/en/latest/topics/settings.html
"""

BOT_NAME = 'olx-cars'

LOG_LEVEL = 'INFO'

NEWSPIDER_MODULE = 'src.spiders'
SPIDER_MODULES = ['src.spiders']
ROBOTSTXT_OBEY = False

TELNETCONSOLE_ENABLED = False

# Do not change the Twisted reactor unless you really know what you are doing.
TWISTED_REACTOR = 'twisted.internet.asyncioreactor.AsyncioSelectorReactor'

# ---------------------------------------------------------------------------
# Concurrency and rate limiting
# ---------------------------------------------------------------------------

# Global ceiling — individual domains are further constrained via DOWNLOAD_SLOTS
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 8

# Global default download delay (overridden per domain below)
DOWNLOAD_DELAY = 0.10

# Per-domain slot settings.
# Each entry sets concurrent requests and download delay for that domain.
# BG is more conservative due to CloudFront; all others at the same rate.
DOWNLOAD_SLOTS = {
    'www.olx.ro': {'concurrency': 8,  'delay': 0.10},
    'www.olx.pl': {'concurrency': 8,  'delay': 0.10},
    'www.olx.bg': {'concurrency': 4,  'delay': 0.25},  # CloudFront headroom
    'www.olx.pt': {'concurrency': 8,  'delay': 0.10},
    'www.olx.ua': {'concurrency': 8,  'delay': 0.10},
    'www.olx.kz': {'concurrency': 8,  'delay': 0.10},
}

# ---------------------------------------------------------------------------
# Request settings
# ---------------------------------------------------------------------------

# Cookies disabled — OLX listing API is fully stateless; cookies add noise
COOKIES_ENABLED = False

# Proxy middleware disabled — OLX does not require a proxy for the 6 countries
# (verified by efficiency-researcher with 200+ requests per domain from datacenter IP)
DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': None,
}

SPIDER_MIDDLEWARES = {}

# ---------------------------------------------------------------------------
# Retry settings
# ---------------------------------------------------------------------------

# Scrapy built-in retry handles transient 5xx; 400 is NOT retried (expected
# for offset > 1000 pagination termination).
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# ---------------------------------------------------------------------------
# Item pipelines
# ---------------------------------------------------------------------------

ITEM_PIPELINES = {
    'src.pipelines.MaxItemsPipeline': 100,
    # IncrementalDiffPipeline must run AFTER MaxItemsPipeline (so only items
    # that passed the ceiling are tracked) and BEFORE DropNonesPipeline (so
    # we compare the original item values including Nones, avoiding spurious
    # UPDATED signals when a None field becomes absent after the None-strip).
    'src.pipelines.IncrementalDiffPipeline': 200,
    # DropNonesPipeline must run BEFORE the Apify dataset push pipeline
    # (registered by apply_apify_settings() at priority 1000), so its
    # priority is set between 100 and 1000.
    'src.pipelines.DropNonesPipeline': 500,
}

# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------

EXTENSIONS = {
    # Hooks scrapy.signals.item_error to mark the spider's class-level
    # crawl_failed flag whenever a pipeline raises. main.py reads that flag
    # and calls Actor.fail(), turning silent-SUCCEEDED-with-0-items runs into
    # visible FAILED runs. See src/extensions.py for the full rationale.
    'src.extensions.FailOnItemErrorExtension': 500,
}
