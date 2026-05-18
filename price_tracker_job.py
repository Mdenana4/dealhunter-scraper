#!/usr/bin/env python3
"""DealHunter Cloud Run Job — System 1: Price History Collector."""
import os, sys, traceback

sys.path.insert(0, "/app")

from price_tracker_cloudrun import PriceTracker

def main():
    print("[OK] DealHunter Price Tracker Job starting...")
    print(f"[OK] Proxy token set: {bool(os.environ.get('SCRAPEDO_TOKEN','') or os.environ.get('SCRAPE_DO_TOKEN',''))}")
    print(f"[OK] Database URL set: {bool(os.environ.get('DATABASE_URL',''))}")

    try:
        tracker = PriceTracker()
        print("[OK] PriceTracker initialized")

        print("[OK] Starting catalog collection cycle...")
        result = tracker.run_cycle()

        total_products  = result.get("products_found", 0)
        total_snapshots = result.get("snapshots_saved", 0)
        elapsed         = result.get("elapsed_seconds", 0)

        print(f"[OK] Cycle complete in {elapsed}s: {total_products} products, {total_snapshots} snapshots")
        print(f"[OK] By source: {result.get('by_source', {})}")

        if total_products == 0:
            print("[WARN] No products found — check proxy status and HTML selectors")

        return 0

    except Exception as e:
        print(f"[ERROR] Price tracker job failed: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
