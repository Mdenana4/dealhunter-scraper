#!/bin/sh
PORT=${PORT:-5000}
SCRAPER_LOG=/tmp/scraper.log

echo "[start] Starting scraper background..."
PYTHONUNBUFFERED=1 python -u scraper.py > "$SCRAPER_LOG" 2>&1 &
SCRAPER_PID=$!
echo "[start] Scraper PID: $SCRAPER_PID"

echo "[start] Starting Flask server on port $PORT..."
PORT=$PORT python server.py
