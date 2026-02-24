#!/usr/bin/env python3
"""
GA4 AutoTrack — AI-Powered Analytics Instrumentation

Usage:
    # Full pipeline with live crawling + Claude API analysis:
    python main.py --url https://www.oaklandish.com --api-key sk-ant-... --ga4-id G-XXXXXXX

    # Demo mode (uses pre-built analysis of Oaklandish.com):
    python main.py --demo

    # Crawl only (saves page inventory without AI analysis):
    python main.py --url https://www.oaklandish.com --crawl-only
"""

import argparse
import logging
import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional; fall back to environment variables

sys.path.insert(0, os.path.dirname(__file__))

from src.crawler import SiteCrawler
from src.analyzer import analyze_page, generate_demo_analyses
from src.sdr_generator import generate_sdr
from src.gtm_generator import generate_gtm_container

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_full_pipeline(url: str, api_key: str = None, ga4_id: str = "G-XXXXXXXXXX", output_dir: str = "output"):
    """Run the complete crawl → analyze → plan → generate pipeline."""
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Crawl
    logger.info(f"Step 1/4: Crawling {url}")
    crawler = SiteCrawler(url, max_pages=10, delay=1.0)
    pages = crawler.crawl()

    if not pages:
        logger.error("No pages were crawled. Check the URL and try again.")
        return

    logger.info(f"  Discovered {len(pages)} pages across {len(crawler.page_type_counts)} types")

    # Step 2: Analyze with OpenRouter
    logger.info("Step 2/4: Analyzing pages with OpenRouter API")
    analyses = []
    for page in pages:
        logger.info(f"  Analyzing: {page.page_type} — {page.url}")
        try:
            analysis = analyze_page(page, api_key=api_key)
            analyses.append(analysis)
            logger.info(f"    → {len(analysis.recommended_events)} events recommended")
        except Exception as e:
            logger.error(f"    → Failed: {e}")

    if not analyses:
        logger.error("No pages were successfully analyzed.")
        return

    # Step 3: Generate SDR
    sdr_path = os.path.join(output_dir, "tracking_plan_sdr.xlsx")
    logger.info(f"Step 3/4: Generating SDR → {sdr_path}")
    site_name = url.replace("https://", "").replace("http://", "").split("/")[0]
    generate_sdr(analyses, sdr_path, site_name=site_name)

    # Step 4: Generate GTM Container
    gtm_path = os.path.join(output_dir, "gtm_container_import.json")
    logger.info(f"Step 4/4: Generating GTM container → {gtm_path}")
    generate_gtm_container(analyses, ga4_measurement_id=ga4_id, output_path=gtm_path)

    logger.info("=" * 60)
    logger.info("Pipeline complete! Outputs:")
    logger.info(f"  SDR (tracking plan):  {sdr_path}")
    logger.info(f"  GTM container JSON:   {gtm_path}")
    logger.info("=" * 60)
    logger.info("Next steps:")
    logger.info("  1. Review the SDR spreadsheet — adjust events/parameters as needed")
    logger.info("  2. Import the GTM container JSON into Google Tag Manager")
    logger.info("     (Admin → Import Container → Choose file → Merge)")
    logger.info("  3. Implement dataLayer.push() calls in your site code")
    logger.info("     (See the 'Data Layer Spec' tab in the SDR)")
    logger.info("  4. Test in GTM Preview mode before publishing")


def run_demo(output_dir: str = "output"):
    """Run demo mode with pre-built Oaklandish.com analysis."""
    os.makedirs(output_dir, exist_ok=True)

    logger.info("Running in DEMO mode with pre-built Oaklandish.com analysis")
    logger.info("")

    # Generate demo analyses
    analyses = generate_demo_analyses()
    logger.info(f"Loaded {len(analyses)} pre-built page analyses:")
    for a in analyses:
        logger.info(f"  • {a.page_type:15s} → {a.url}")
    logger.info("")

    # Generate SDR
    sdr_path = os.path.join(output_dir, "oaklandish_tracking_plan_sdr.xlsx")
    logger.info(f"Generating SDR → {sdr_path}")
    generate_sdr(analyses, sdr_path, site_name="Oaklandish.com")

    # Generate GTM Container
    gtm_path = os.path.join(output_dir, "oaklandish_gtm_container.json")
    logger.info(f"Generating GTM container → {gtm_path}")
    generate_gtm_container(analyses, ga4_measurement_id="G-XXXXXXXXXX", output_path=gtm_path)

    logger.info("")
    logger.info("=" * 60)
    logger.info("Demo complete! Generated files:")
    logger.info(f"  SDR:  {sdr_path}")
    logger.info(f"  GTM:  {gtm_path}")
    logger.info("=" * 60)

    return sdr_path, gtm_path


def main():
    parser = argparse.ArgumentParser(
        description="GA4 AutoTrack — AI-powered analytics instrumentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--url", help="Target website URL to analyze")
    parser.add_argument("--api-key", help="OpenRouter API key (or set OPENROUTER_API_KEY env var)")
    parser.add_argument("--ga4-id", default="G-XXXXXXXXXX", help="GA4 Measurement ID")
    parser.add_argument("--output-dir", default="output", help="Output directory for generated files")
    parser.add_argument("--demo", action="store_true", help="Run demo with pre-built Oaklandish.com analysis")
    parser.add_argument("--crawl-only", action="store_true", help="Only crawl and list pages, no AI analysis")
    parser.add_argument("--max-pages", type=int, default=10, help="Max pages to crawl")

    args = parser.parse_args()

    if args.demo:
        run_demo(args.output_dir)
    elif args.url:
        if args.crawl_only:
            crawler = SiteCrawler(args.url, max_pages=args.max_pages)
            pages = crawler.crawl()
            for p in pages:
                print(f"  {p.page_type:15s} {p.title[:50]:50s} {p.url}")
        else:
            api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                logger.warning("No API key provided. Running in demo mode instead.")
                logger.warning("For full pipeline, provide --api-key or set OPENROUTER_API_KEY")
                run_demo(args.output_dir)
            else:
                run_full_pipeline(args.url, api_key=api_key, ga4_id=args.ga4_id, output_dir=args.output_dir)
    else:
        parser.print_help()
        print("\nQuick start: python main.py --demo")


if __name__ == "__main__":
    main()
