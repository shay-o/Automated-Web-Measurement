# GA4 AutoTrack — AI-Powered Analytics Instrumentation

An AI-powered tool that automates the creation of Google Analytics 4 tracking plans and Google Tag Manager implementations for websites.

## What It Does

Given a website URL, GA4 AutoTrack will:

1. **Crawl** the site to discover and classify page types (homepage, collection, product, blog, info pages, cart, etc.)
2. **Analyze** each page using AI (Claude via OpenRouter) to identify interactive elements, meaningful user actions, and available data points
3. **Generate an SDR** (Solution Design Reference) — a comprehensive tracking plan spreadsheet documenting every recommended event, its parameters, triggers, and business purpose
4. **Export a GTM Container** — an importable JSON file for Google Tag Manager with all tags, triggers, and variables pre-configured

## Quick Start

### Demo Mode (no API key needed)
```bash
python main.py --demo
```
This generates a complete SDR and GTM container for **Oaklandish.com** using pre-built analysis.

### Full Pipeline (requires OpenRouter API key)
```bash
export OPENROUTER_API_KEY=sk-or-...
python main.py --url https://www.example.com --ga4-id G-XXXXXXX
```

### Crawl Only (inspect site structure)
```bash
python main.py --url https://www.example.com --crawl-only
```

## Output Files

### SDR Spreadsheet (`.xlsx`)
A multi-tab tracking plan with:
- **Overview** — Site summary, page types covered, event counts
- **Event Tracking Plan** — Every event with trigger, parameters, priority, and business purpose. Color-coded: green = GA4 standard events, orange = custom events
- **Parameters Reference** — All event/item parameters with types, scope, and example values
- **Page Inventory** — Every analyzed page with interactive elements and recommended actions
- **Data Layer Spec** — Ready-to-use `dataLayer.push()` code snippets for each event

### GTM Container JSON
Importable into Google Tag Manager via **Admin → Import Container**. Includes:
- GA4 Configuration tag with Measurement ID
- Event tags for all recommended events (standard + custom)
- Custom Event triggers listening to dataLayer pushes
- Data Layer Variables for all event parameters
- Organized into folders for maintainability

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│   Crawler    │────▶│  AI Analyzer  │────▶│ SDR Generator │────▶│  .xlsx file  │
│  (requests   │     │  (OpenRouter) │     │  (openpyxl)   │     │              │
│  + BS4)      │     │              │     └───────────────┘     └──────────────┘
└─────────────┘     │              │     ┌───────────────┐     ┌──────────────┐
                    │              │────▶│ GTM Generator │────▶│  .json file  │
                    └──────────────┘     │  (container)  │     │              │
                                        └───────────────┘     └──────────────┘
```

## Dependencies

```
pip install requests beautifulsoup4 lxml openpyxl openai
```

## Configuration Options

| Flag | Description | Default |
|------|-------------|---------|
| `--url` | Target website URL | — |
| `--api-key` | OpenRouter API key | `$OPENROUTER_API_KEY` |
| `--ga4-id` | GA4 Measurement ID | `G-XXXXXXXXXX` |
| `--output-dir` | Output directory | `output/` |
| `--max-pages` | Max pages to crawl | `10` |
| `--demo` | Run demo mode | — |
| `--crawl-only` | Crawl without analysis | — |

## Extending This Tool

### Adding New Page Type Patterns
Edit `SiteCrawler.PAGE_TYPE_PATTERNS` in `src/crawler.py` to add recognition patterns for additional page types (e.g., account pages, wishlist, compare).

### Customizing the Analysis Prompt
Edit `ANALYSIS_PROMPT` in `src/analyzer.py` to adjust what the AI focuses on. You can add industry-specific guidance, require certain events, or change the output format.

### Supporting Other Tag Managers
The `src/gtm_generator.py` module can be adapted to produce output for other tag management systems. The SDR is platform-agnostic — only the final export step is GTM-specific.

## Roadmap

- [ ] JavaScript-rendered SPA support (Puppeteer/Playwright integration)
- [ ] Import existing SDR as input for consistency checking
- [ ] Import existing GTM container for audit/documentation
- [ ] Support for additional e-commerce platforms (Shopify Liquid, WooCommerce, Magento)
- [ ] CI/CD integration for tracking consistency on code changes
- [ ] GA4 Admin API integration to auto-create custom dimensions
