#!/bin/sh
# Start scraper in background, server in foreground.
# Render keeps the container alive as long as server.py runs.
echo "Starting scraper..."
python scraper.py &
SCRAPER_PID=$!

echo "Starting server..."
python server.py
SERVER_EXIT=$?

# If server exits for any reason, kill the scraper too
kill "$SCRAPER_PID" 2>/dev/null
exit $SERVER_EXIT
