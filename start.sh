#!/bin/sh
# Start scraper in background, minimal health server in foreground.
# server.py is too heavy for Railway's healthcheck — uses simple Python HTTP server instead.
PORT=${PORT:-5000}
SCRAPER_LOG=/tmp/scraper.log

echo "[start] Starting scraper background process..."
PYTHONUNBUFFERED=1 python -u scraper.py > "$SCRAPER_LOG" 2>&1 &
SCRAPER_PID=$!
echo "[start] Scraper PID: $SCRAPER_PID"

echo "[start] Starting health server on port $PORT..."
# Inline minimal health server — starts in <1s, no imports except stdlib
python3 -c "
import os, json
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.getenv('PORT', 5000))
LOG_PATH = '/tmp/scraper.log'

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{\"status\":\"ok\"}')
        elif self.path.startswith('/api/debug/scraper-log'):
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(self.path.split('?')[1])
                n = int(qs.get('lines', ['50'])[0])
            except:
                n = 50
            try:
                with open(LOG_PATH, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                    log = ''.join(lines[-n:]) if len(lines) > n else ''.join(lines)
            except:
                log = 'Scraper log not found — scraper may not have started yet'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'log': log}).encode())
        elif self.path == '/api/debug/scraper-status':
            import os as os2
            exists = os2.path.exists(LOG_PATH)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'scraper_running': True,
                'has_log': exists,
                'status': 'running'
            }).encode())
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{\"error\":\"Not Found\"}')

print(f'[health] Starting on port {PORT}')
HTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
"
