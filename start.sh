#!/bin/sh
# Start scraper in background logging to file, server in foreground.
SCRAPER_LOG=/tmp/scraper.log
echo "Starting scraper (log -> $SCRAPER_LOG)..."
PYTHONUNBUFFERED=1 python -u scraper.py > "$SCRAPER_LOG" 2>&1 &
SCRAPER_PID=$!
echo "Scraper PID: $SCRAPER_PID"

echo "Starting server..."
python server.py
SERVER_EXIT=$?

kill "$SCRAPER_PID" 2>/dev/null
exit $SERVER_EXIT
