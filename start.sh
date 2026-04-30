#!/bin/sh
# Start scraper in background, server in foreground.
# -u = unbuffered stdout/stderr so Render logs show scraper output immediately.
echo "Starting scraper..."
PYTHONUNBUFFERED=1 python -u scraper.py 2>&1 &
SCRAPER_PID=$!

echo "Starting server..."
python server.py
SERVER_EXIT=$?

kill "$SCRAPER_PID" 2>/dev/null
exit $SERVER_EXIT
