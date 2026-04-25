# scraper_health.py
# Tracks per-scraper product counts every cycle. Fires an FCM admin alert
# whenever a scraper's yield drops to less than 20 % of its rolling average —
# the strongest signal that a platform has changed its HTML structure.
#
# Usage in scraper.py:
#   from scraper_health import health
#   health.record("amazon_eg", products_found)   # once per scraper
#   health.flush()                               # once at end of run_scraper()
#
# Firestore writes:
#   scraper_health/latest          ← always overwritten with the latest cycle
#   scraper_health/{auto_id}       ← archived copy of each cycle
#
# Admin FCM topic: "admin_alerts"
# Admins subscribe to this topic in the admin Flutter app.

import json
from datetime import datetime, timezone

from firebase_admin import firestore, messaging

# Alert when current count < this fraction of the rolling average
_ALERT_THRESHOLD = 0.20
# How many past cycles to average over
_ROLLING_WINDOW  = 5


class _HealthTracker:
    """Accumulates per-scraper counts during a cycle, then flushes to Firestore."""

    def __init__(self):
        self._cycle:   dict[str, int]        = {}
        self._history: dict[str, list[int]]  = {}

    def record(self, scraper_name: str, products_found: int) -> None:
        """Call once per scraper function, passing the number of products saved."""
        self._cycle[scraper_name] = products_found

    def flush(self) -> None:
        """
        Call at the end of run_scraper().
        - Updates the rolling history in memory.
        - Writes the cycle summary to Firestore.
        - Sends an FCM alert to the "admin_alerts" topic if any scraper looks broken.
        """
        if not self._cycle:
            return

        try:
            db  = firestore.client()
            now = datetime.now(timezone.utc)

            # Update in-memory rolling window
            for name, count in self._cycle.items():
                buf = self._history.setdefault(name, [])
                buf.append(count)
                if len(buf) > _ROLLING_WINDOW:
                    buf.pop(0)

            # Detect scrapers whose yield dropped suspiciously
            broken = []
            for name, count in self._cycle.items():
                hist = self._history.get(name, [])
                # Need at least 2 cycles: one past + this one
                if len(hist) < 2:
                    continue
                past_avg = sum(hist[:-1]) / len(hist[:-1])
                # Only alert if there was meaningful past activity
                if past_avg < 5:
                    continue
                if count < past_avg * _ALERT_THRESHOLD:
                    broken.append({
                        "scraper":     name,
                        "current":     count,
                        "rolling_avg": round(past_avg, 1),
                        "drop_pct":    round((past_avg - count) / past_avg * 100, 1),
                    })

            cycle_doc = {
                "timestamp":      now,
                "cycle":          self._cycle,
                "broken_scrapers": broken,
                "has_alerts":     len(broken) > 0,
            }

            # Overwrite the "latest" document (used by admin dashboard)
            db.collection("scraper_health").document("latest").set(cycle_doc)
            # Archive a timestamped copy
            db.collection("scraper_health").document().set(cycle_doc)

            if broken:
                _send_admin_fcm_alert(broken)

            status = "⚠️  ALERTS: " + ", ".join(b["scraper"] for b in broken) if broken else "✓ all OK"
            print(f"  [HEALTH] {status}")

        except Exception as e:
            print(f"  [HEALTH] flush error: {e}")
        finally:
            self._cycle = {}


def _send_admin_fcm_alert(broken: list[dict]) -> None:
    """
    Send a Firebase Cloud Messaging notification to the 'admin_alerts' topic.
    Admin Flutter app must subscribe to this topic on login.
    """
    try:
        names   = ", ".join(b["scraper"] for b in broken)
        details = " | ".join(
            f"{b['scraper']}: {b['current']} (avg {b['rolling_avg']:.0f}, -{b['drop_pct']:.0f}%)"
            for b in broken
        )
        messaging.send(messaging.Message(
            topic="admin_alerts",
            notification=messaging.Notification(
                title="⚠️ Scraper Selector Alert",
                body=f"{names} returned far fewer products than usual — HTML may have changed.",
            ),
            data={
                "type":    "scraper_health_alert",
                "broken":  json.dumps(broken),
                "details": details,
            },
            android=messaging.AndroidConfig(priority="high"),
        ))
        print(f"  [HEALTH] FCM admin alert sent: {names}")
    except Exception as e:
        print(f"  [HEALTH] FCM send error: {e}")


# Module-level singleton — import and use directly
health = _HealthTracker()
