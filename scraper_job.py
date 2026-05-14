#!/usr/bin/env python3
"""
Cloud Run Job entry point for DealHunter Scraper.

Triggered every 4 hours by Cloud Scheduler.
Runs a full scraper cycle across all platforms and persists results.

Environment variables:
  DATABASE_URL          — Supabase PostgreSQL connection string
  TIMESCALE_URL         — TimescaleDB connection string
  SCRAPE_DO_TOKEN       — Scrape.do proxy token (optional)
  CRAWLBASE_TOKEN       — Crawlbase proxy token (optional)
  SCRAPINGBEE_TOKEN     — ScrapingBee proxy token (optional)
  AMAZON_ENABLED        — "true"/"false" kill switch (default: true)
  NOON_ENABLED          — "true"/"false" kill switch (default: true)
  JUMIA_ENABLED         — "true"/"false" kill switch (default: true)
  MIN_PRODUCT_PRICE     — Minimum price filter (default: 50)
  MIN_DISCOUNT          — Minimum discount % (default: 40)
  REQUEST_TIMEOUT       — HTTP timeout in seconds (default: 30)
  KEYWORD_DISCOVERY_ENABLED — Enable keyword search (default: false)
"""

import logging
import os
import sys
import traceback

# Ensure stdout is unbuffered for Cloud Run logging
sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

# Configure root logger before importing scraper
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    stream=sys.stdout,
)

from scraper_cloudrun import DealHunterScraper


def main() -> int:
    """Run the DealHunter scraper as a Cloud Run Job."""
    print("[OK] DealHunter Cloud Run Job starting...")

    # Validate environment
    db_url = os.environ.get("DATABASE_URL", "")
    ts_url = os.environ.get("TIMESCALE_URL", "")

    if not db_url:
        print("[WARN] DATABASE_URL not set — Supabase writes will be skipped")
    if not ts_url:
        print("[WARN] TIMESCALE_URL not set — price snapshots will be skipped")

    try:
        scraper = DealHunterScraper()

        # Check if discovery should run (4-hour interval guard)
        force_run = os.environ.get("FORCE_RUN", "").lower() == "true"
        if not force_run and not scraper.should_run_discovery():
            print("[OK] Discovery interval not reached (4h guard). Skipping.")
            return 0
        if force_run:
            print("[OK] FORCE_RUN=true — bypassing 4-hour interval guard.")

        print("[OK] Starting scraper cycle...")
        result = scraper.run_cycle()

        # Print structured summary for Cloud Logging
        print(
            f"[OK] Cycle complete: {result['deals_found']} found, "
            f"{result['inserted']} inserted, {result['updated']} updated, "
            f"{result['snapshots']} price snapshots recorded, "
            f"{result['price_changes']} price changes detected "
            f"({result['elapsed_seconds']}s elapsed)"
        )

        # Print per-source breakdown
        for source, count in result.get("sources", {}).items():
            status = "OK" if count > 0 else "WARN"
            print(f"  [{status}] {source}: {count} deals")

        # Non-zero exit if no deals found across any source (potential breakage)
        total_found = result["deals_found"]
        if total_found == 0:
            print(
                "[WARN] No deals found from any source — "
                "check scraper health and proxy status"
            )
            # Still return 0 — don't retry a fundamentally empty result
            return 0

        return 0

    except Exception as e:
        print(f"[ERROR] Scraper job failed: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
