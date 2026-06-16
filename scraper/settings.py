"""Scrapy settings for imtihan_scraper."""

BOT_NAME = 'imtihan_scraper'

SPIDER_MODULES = ['scraper.spiders']
NEWSPIDER_MODULE = 'scraper.spiders'

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)

ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = 4
DOWNLOAD_DELAY = 1.5
CONCURRENT_REQUESTS_PER_DOMAIN = 2

DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

ITEM_PIPELINES = {
    'scraper.pipelines.DjangoPipeline': 300,
}

LOG_LEVEL = 'WARNING'

# Feed the Django settings so models are importable from pipeline
DJANGO_SETTINGS_MODULE = 'imtihanBackend.settings'
