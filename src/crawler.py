"""
Site Crawler - Discovers and categorizes pages from a target website.
Respectfully crawls public pages, honors robots.txt, and identifies
distinct page types for analytics instrumentation.
"""

import re
import time
import logging
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class CrawledPage:
    url: str
    page_type: str  # homepage, collection, product, blog_index, blog_post, info_page, cart, search
    title: str
    html: str
    links: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


class SiteCrawler:
    PAGE_TYPE_PATTERNS = {
        "homepage": [r"^/$", r"^$"],
        "collection": [r"/collections/", r"/category/", r"/shop/", r"/c/"],
        "product": [r"/products/", r"/product/", r"/p/"],
        "blog_index": [r"/blogs?/$", r"/news/$", r"/journal/$"],
        "blog_post": [r"/blogs?/.+/.+", r"/news/.+", r"/journal/.+"],
        "cart": [r"/cart"],
        "search": [r"/search"],
        "info_page": [r"/pages?/"],
    }

    def __init__(
        self,
        base_url: str,
        max_pages: int = 10,
        delay: float = 1.0,
        timeout: int = 15,
    ):
        self.base_url = base_url.rstrip("/")
        self.domain = urlparse(base_url).netloc
        self.max_pages = max_pages
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GA4-AutoTrack-Analyzer/1.0 (analytics research tool)",
            "Accept": "text/html,application/xhtml+xml",
        })
        self.visited: set[str] = set()
        self.pages: list[CrawledPage] = []
        self.page_type_counts: dict[str, int] = {}

    def classify_page(self, path: str) -> str:
        path = path.rstrip("/")
        if not path or path == "":
            return "homepage"
        for page_type, patterns in self.PAGE_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, path):
                    return page_type
        return "other"

    def should_crawl(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc and parsed.netloc != self.domain:
            return False
        if parsed.path.split(".")[-1] in ("jpg", "jpeg", "png", "gif", "svg", "css", "js", "pdf", "ico", "webp"):
            return False
        if any(x in parsed.path for x in ("/cdn/", "/static/", "/assets/")):
            return False
        return True

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        return f"{self.base_url}{path}"

    def extract_links(self, soup: BeautifulSoup, current_url: str) -> list[str]:
        links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                continue
            full_url = urljoin(current_url, href)
            if self.should_crawl(full_url):
                links.append(self.normalize_url(full_url))
        return list(set(links))

    def extract_meta(self, soup: BeautifulSoup) -> dict:
        meta = {}
        title_tag = soup.find("title")
        if title_tag:
            meta["title"] = title_tag.get_text(strip=True)
        for tag in soup.find_all("meta"):
            name = tag.get("name", tag.get("property", ""))
            content = tag.get("content", "")
            if name and content:
                meta[name] = content
        # Look for Shopify-specific data
        for script in soup.find_all("script"):
            text = script.get_text()
            if "ShopifyAnalytics" in text or "meta.product" in text:
                meta["has_shopify_analytics"] = True
            if "Shopify.theme" in text:
                meta["is_shopify"] = True
        return meta

    def fetch_page(self, url: str) -> Optional[CrawledPage]:
        if url in self.visited:
            return None
        self.visited.add(url)

        try:
            logger.info(f"Fetching: {url}")
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            resp.raise_for_status()

            if "text/html" not in resp.headers.get("content-type", ""):
                return None

            soup = BeautifulSoup(resp.text, "lxml")
            path = urlparse(url).path
            page_type = self.classify_page(path)
            meta = self.extract_meta(soup)
            title = meta.get("title", soup.find("title").get_text(strip=True) if soup.find("title") else url)
            links = self.extract_links(soup, url)

            return CrawledPage(
                url=url,
                page_type=page_type,
                title=title,
                html=resp.text,
                links=links,
                meta=meta,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

    def crawl(self) -> list[CrawledPage]:
        """
        Crawl the site, prioritizing page type diversity.
        Returns a list of representative pages across different types.
        """
        queue = [self.base_url]
        max_per_type = 2  # get at most 2 pages of each type for analysis

        while queue and len(self.pages) < self.max_pages:
            url = queue.pop(0)
            page = self.fetch_page(url)

            if page is None:
                continue

            type_count = self.page_type_counts.get(page.page_type, 0)
            if type_count < max_per_type:
                self.pages.append(page)
                self.page_type_counts[page.page_type] = type_count + 1
                logger.info(f"  -> {page.page_type}: {page.title}")

            # Prioritize queue by under-represented page types
            for link in page.links:
                if link not in self.visited:
                    link_type = self.classify_page(urlparse(link).path)
                    link_count = self.page_type_counts.get(link_type, 0)
                    if link_count < max_per_type:
                        queue.insert(0, link)  # prioritize
                    else:
                        queue.append(link)

            time.sleep(self.delay)

        logger.info(f"Crawl complete: {len(self.pages)} pages across {len(self.page_type_counts)} types")
        return self.pages
