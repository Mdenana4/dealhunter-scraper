#!/usr/bin/env python3
"""DealHunter Cloud Run Job — ALWAYS runs on execution."""
import os, sys, traceback

# Ensure current dir is in path
sys.path.insert(0, "/app")

from scraper_cloudrun import DealHunterScraper

def main():
    print("[OK] DealHunter Cloud Run Job starting...")
    print(f"[OK] Proxy token set: {bool(os.environ.get('SCRAPEDO_TOKEN','') or os.environ.get('SCRAPE_DO_TOKEN',''))}")
    print(f"[OK] Database URL set: {bool(os.environ.get('DATABASE_URL',''))}")

    try:
        scraper = DealHunterScraper()
        print("[OK] DealHunterScraper initialized")

        print("[OK] Starting discovery cycle...")
        result = scraper.run_cycle()

        total_found = result.get("deals_found", 0)
        print(f"[OK] Cycle complete: {total_found} deals found")
        print(f"[OK] By source: {result.get('by_source', {})}")

        if total_found == 0:
            print("[WARN] No deals found — check proxy status and HTML selectors")

        return 0

    except Exception as e:
        print(f"[ERROR] Scraper job failed: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
