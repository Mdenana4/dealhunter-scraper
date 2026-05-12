#!/bin/sh
# Start scraper in background, minimal health server in foreground.
# PORT env var is set by Railway/Render; defaults to 5000 locally.
PORT=${PORT:-5000}
SCRAPER_LOG=/tmp/scraper.log

echo "Starting scraper (log -> $SCRAPER_LOG)..."
PYTHONUNBUFFERED=1 python -u scraper.py > "$SCRAPER_LOG" 2>&1 &
SCRAPER_PID=$!
echo "Scraper PID: $SCRAPER_PID"

echo "Starting health server on port $PORT..."
PORT=$PORT python health_server.py
SERVER_EXIT=$?

kill "$SCRAPER_PID" 2>/dev/null
exit $SERVER_EXIT
