#!/usr/bin/env python3
"""
DealHunter Price Tracker Job
Runs every 8 hours via Cloud Scheduler.

What it does:
1. Reads accumulated price_snapshots to compute real highest/lowest prices per product
2. Updates deals table with real historical data (highest_price_ever, lowest_price_ever)
3. Re-evaluates fake_score and verdict using real price history
4. Marks deals FAKE if original_price was inflated vs real historical prices
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
TIMESCALE_URL = os.environ.get("TIMESCALE_URL", DATABASE_URL)


def get_conn(url: str):
    return psycopg2.connect(url, connect_timeout=15)


def update_price_history(conn) -> int:
    """Populate highest_price_ever and lowest_price_ever from price_snapshots."""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE deals d
            SET
                highest_price_ever = subq.max_original,
                lowest_price_ever  = subq.min_price
            FROM (
                SELECT
                    product_id,
                    MAX(original_price) AS max_original,
                    MIN(price)          AS min_price
                FROM price_snapshots
                WHERE product_id IS NOT NULL
                  AND product_id <> ''
                GROUP BY product_id
            ) subq
            WHERE d.product_id = subq.product_id
        """)
        updated = cur.rowcount
        conn.commit()
        logger.info(f"[OK] Updated price history fields for {updated} deals")
        return updated


def re_evaluate_verdicts(conn) -> dict:
    """
    Re-score deals using real price history.

    Fake detection logic (priority order):
    1. original_price > 1.8x lowest_price_ever → FAKE (inflated original)
    2. original_price > 1.4x lowest_price_ever → SUSPICIOUS
    3. discount >= 85% with no history → FAKE (statistically impossible)
    4. discount >= 65% with no history → SUSPICIOUS
    5. Otherwise → GENUINE
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, product_id, original_price, current_price,
                   discount_percent, highest_price_ever, lowest_price_ever,
                   verdict
            FROM deals
            WHERE is_active = true
        """)
        rows = cur.fetchall()

    fake_count = suspicious_count = genuine_count = skipped = 0

    updates = []
    for row in rows:
        (deal_id, product_id, original_price, current_price,
         discount_pct, highest_ever, lowest_ever, old_verdict) = row

        if not original_price or not current_price:
            skipped += 1
            continue

        fake_score = 0
        fraud_reasons = []
        verdict = "GENUINE"

        if lowest_ever and lowest_ever > 0:
            inflation_ratio = original_price / lowest_ever

            if inflation_ratio > 1.8:
                verdict = "FAKE"
                fake_score = min(95, int((inflation_ratio - 1) * 40))
                fraud_reasons.append(
                    f"Original price ({original_price:.0f}) is {inflation_ratio:.1f}x "
                    f"higher than historical low ({lowest_ever:.0f}) — price was artificially inflated"
                )
                fake_count += 1
            elif inflation_ratio > 1.4:
                verdict = "SUSPICIOUS"
                fake_score = min(70, int((inflation_ratio - 1) * 30))
                fraud_reasons.append(
                    f"Original price ({original_price:.0f}) is {inflation_ratio:.1f}x "
                    f"higher than historical low ({lowest_ever:.0f}) — possible inflation"
                )
                suspicious_count += 1
            else:
                verdict = "GENUINE"
                fake_score = max(0, int((inflation_ratio - 1) * 10))
                genuine_count += 1
        else:
            # No history — fall back to discount-ratio heuristic
            if discount_pct and discount_pct >= 85:
                verdict = "FAKE"
                fake_score = 90
                fraud_reasons.append(
                    f"Discount of {discount_pct}% is statistically implausible — no price history available"
                )
                fake_count += 1
            elif discount_pct and discount_pct >= 65:
                verdict = "SUSPICIOUS"
                fake_score = 55
                fraud_reasons.append(
                    f"Discount of {discount_pct}% is unusually high — no price history to verify"
                )
                suspicious_count += 1
            else:
                verdict = "GENUINE"
                fake_score = 0
                genuine_count += 1

        confidence = round(
            0.85 if lowest_ever else 0.35, 2
        )

        recommendation = (
            "avoid" if verdict == "FAKE"
            else "caution" if verdict == "SUSPICIOUS"
            else "buy"
        )

        updates.append((
            verdict, fake_score, fraud_reasons, confidence, recommendation, deal_id
        ))

    if updates:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,
                """
                UPDATE deals
                SET verdict        = %s,
                    fake_score     = %s,
                    fraud_reasons  = %s,
                    confidence     = %s,
                    recommendation = %s
                WHERE id = %s
                """,
                updates,
                page_size=200,
            )
        conn.commit()

    result = {
        "fake": fake_count,
        "suspicious": suspicious_count,
        "genuine": genuine_count,
        "skipped": skipped,
        "total": len(updates),
    }
    logger.info(
        f"[OK] Verdicts: {fake_count} FAKE, {suspicious_count} SUSPICIOUS, "
        f"{genuine_count} GENUINE, {skipped} skipped"
    )
    return result


def main():
    logger.info("[START] DealHunter Price Tracker Job")

    if not DATABASE_URL:
        logger.error("[ERROR] DATABASE_URL not set")
        sys.exit(1)

    # Use TIMESCALE_URL for snapshots if separate, else same DB
    snap_url = TIMESCALE_URL or DATABASE_URL
    deals_url = DATABASE_URL

    try:
        snap_conn = get_conn(snap_url)
        logger.info("[OK] Connected to price_snapshots database")
    except Exception as e:
        logger.error(f"[ERROR] Cannot connect to snapshots DB: {e}")
        sys.exit(1)

    try:
        deals_conn = get_conn(deals_url) if snap_url != deals_url else snap_conn
        if snap_url != deals_url:
            logger.info("[OK] Connected to deals database")
    except Exception as e:
        logger.error(f"[ERROR] Cannot connect to deals DB: {e}")
        snap_conn.close()
        sys.exit(1)

    try:
        # Step 1: check how many snapshots exist
        with snap_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM price_snapshots")
            row = cur.fetchone()
            count, oldest, newest = row
            logger.info(f"[INFO] price_snapshots: {count} rows | oldest={oldest} | newest={newest}")

        if count == 0:
            logger.warning(
                "[WARN] price_snapshots is empty — scraper must run first to collect data. "
                "Skipping price history update."
            )
        else:
            # Step 2: populate highest/lowest in deals table
            updated = update_price_history(deals_conn)
            logger.info(f"[OK] Price history updated for {updated} deals")

        # Step 3: always re-evaluate verdicts (uses whatever history exists)
        stats = re_evaluate_verdicts(deals_conn)
        logger.info(f"[DONE] Verdict re-evaluation complete: {stats}")

    except Exception as e:
        logger.error(f"[ERROR] Tracker job failed: {e}")
        sys.exit(1)
    finally:
        snap_conn.close()
        if snap_url != deals_url:
            deals_conn.close()

    logger.info("[DONE] Price tracker job complete")


if __name__ == "__main__":
    main()
