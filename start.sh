#!/bin/sh
PORT=${PORT:-8080}
echo "[start] Starting Flask server on port $PORT..."
exec gunicorn server:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
