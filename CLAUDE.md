# GA4 AutoTrack — AI-Powered Analytics Instrumentation

## Project Purpose

This tool uses AI to automate the work that Google Analytics consultants and specialists do today: analyzing websites, creating tracking plans (SDRs), and generating tag management implementations. The goal is to make GA4 instrumentation dramatically easier for site owners.

## Target Site for Development

**Oaklandish.com** (oaklandish.com) — A Shopify-based e-commerce site selling Oakland civic pride apparel. Shopify provides server-side rendered HTML, which makes it a good crawling target. The site has a rich variety of page types: homepage, collection/category pages, product detail pages, blog/news, info pages (store locator, FAQ, about), and cart/checkout flows.

## Resources and Links
- Claude chat to start project: https://claude.ai/chat/dc6ba83d-6711-47b9-88e5-d8022bbf4f5d

## Use Cases to Support

1. **Green field (current focus)**: New site, no existing tracking. Crawl → Analyze → Generate tracking plan and GTM container from scratch.
2. **Consistency checking (future)**: Site already has tracking. Accept an existing SDR/implementation as input, then when a page changes, verify the new page's tracking is consistent with the established plan.
3. **Audit/documentation (future)**: Scan an existing site's tracking implementation (gtag calls, GTM containers, dataLayer pushes) and reverse-engineer a human-readable SDR documenting what's currently tracked.

## What Needs Work Next

### Misc To Do's
- Get several high quality SDR examples
- Work with Playwright to crawl and measure generated traffic

### Near-term improvements
- **JavaScript-rendered page support**: The current crawler uses plain HTTP requests, which doesn't capture content rendered by JavaScript (SPAs, React/Vue apps). Need to integrate Playwright or Puppeteer for headless browser rendering. This is important for many modern e-commerce sites.
- **Live testing against Oaklandish.com**: Run the full pipeline with real API calls against Oaklandish.com to validate and refine the AI analysis prompt.
- **Shopify-specific enhancements**: Oaklandish is Shopify-based. Shopify sites have predictable patterns (Liquid templates, Shopify Analytics meta tags, standard product JSON-LD). The analyzer could use these signals for better accuracy.
- **Error handling and resilience**: The crawler and analyzer need better error handling for network issues, rate limiting, malformed HTML, and API failures.

### Longer-term features
- Import existing GTM container or SDR for audit/consistency use cases
- GA4 Admin API integration to auto-create custom dimensions/metrics
- CI/CD integration (analyze changed pages in pull requests)
- Web UI or interactive mode for reviewing and adjusting recommendations
- Support for non-Shopify platforms (WooCommerce, Magento, custom builds)


## Architecture

The system is a four-stage pipeline:

```
Crawl → Analyze → Plan → Generate
```

1. **Crawler** (`src/crawler.py`) — Takes a starting URL, discovers internal links, classifies pages by type (homepage, collection, product, cart, blog, info_page, etc.), and fetches HTML. Respects robots.txt, limits crawl rate, and prioritizes page type diversity over exhaustive coverage.

2. **AI Analyzer** (`src/analyzer.py`) — For each crawled page, condenses the HTML and sends it to Claude API (claude-sonnet-4-20250514) with a structured prompt. Claude analyzes the page and returns JSON with: page purpose, interactive elements, trackable user actions, available data points, and recommended GA4 events with parameters. There is also a `generate_demo_analyses()` function that returns pre-built analysis for Oaklandish.com for testing without API calls.

3. **SDR Generator** (`src/sdr_generator.py`) — Synthesizes all page analyses into a multi-tab Excel spreadsheet (the Solution Design Reference / tracking plan). Tabs: Overview, Event Tracking Plan, Parameters Reference, Page Inventory, Data Layer Spec. Uses openpyxl with professional formatting.

4. **GTM Generator** (`src/gtm_generator.py`) — Converts the tracking plan into an importable Google Tag Manager container JSON. Creates GA4 Configuration tag, event-specific tags, Custom Event triggers, Data Layer Variables, and organizes everything into folders. The container JSON follows GTM's import format and can be imported via Admin → Import Container.

## Key Design Decisions

- **SDR is the central artifact**: The tracking plan spreadsheet is what humans review and approve. The GTM container is a mechanical translation of the plan. This mirrors how analytics consultants work.
- **GA4 recommended events first**: The system leans on GA4's standard event taxonomy (page_view, view_item, add_to_cart, begin_checkout, etc.) and only proposes custom events when no standard event fits. This unlocks GA4's built-in reporting.
- **dataLayer-based architecture**: GTM tags listen for custom events pushed to the dataLayer. This keeps the GTM container clean and decouples tag management from site code.
- **Page type diversity over exhaustive crawling**: The crawler aims for ~2 representative pages per page type rather than crawling every page. A 10-page sample across 5-6 page types is enough to build a complete tracking plan.
- **Human-in-the-loop**: Each step has an implicit review point. The SDR is the approval gate before implementation.

## Current State

The prototype is functional with:
- Working crawler that classifies Shopify page types
- AI analyzer with Claude API integration + demo fallback
- SDR generator producing a professional 5-tab spreadsheet
- GTM container generator producing importable JSON
- CLI entry point (`main.py`) with --demo, --url, and --crawl-only modes
- Demo output for Oaklandish.com: 6 page types, 20 events, 27 variables

Demo mode works without network or API access. Full pipeline requires `requests` for crawling and `anthropic` for AI analysis.


## Technical Stack

- Python 3.12+
- requests + beautifulsoup4 + lxml (crawling)
- anthropic SDK (AI analysis)
- openpyxl (SDR spreadsheet generation)
- json (GTM container generation)

## Running the Tool

```bash
# Demo mode (no network/API needed):
python main.py --demo

# Full pipeline:
export ANTHROPIC_API_KEY=sk-ant-...
python main.py --url https://www.oaklandish.com --ga4-id G-XXXXXXX

# Crawl only:
python main.py --url https://www.oaklandish.com --crawl-only
```

## File Structure

```
ga4-autotrack/
├── CLAUDE.md          # This file — project context
├── README.md          # User-facing documentation
├── main.py            # CLI entry point
├── src/
│   ├── __init__.py
│   ├── crawler.py     # Site crawler and page classifier
│   ├── analyzer.py    # Claude AI page analysis + demo data
│   ├── sdr_generator.py   # SDR spreadsheet generator
│   └── gtm_generator.py   # GTM container JSON generator
└── output/            # Generated files go here
```
