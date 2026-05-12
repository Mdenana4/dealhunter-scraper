#!/bin/sh
# Railway-specific startup: scraper background + minimal health server foreground.
# This avoids server.py which is too heavy for Railway's 10s healthcheck window.
PORT=${PORT:-5000}
SCRAPER_LOG=/tmp/scraper.log

echo "[railway] Starting scraper background process..."
PYTHONUNBUFFERED=1 python -u scraper.py > "$SCRAPER_LOG" 2>&1 &
SCRAPER_PID=$!
echo "[railway] Scraper PID: $SCRAPER_PID"

echo "[railway] Starting health server on port $PORT..."
exec python health_server.py
