# DealHunter Scraper - Python Flask Backend
FROM docker:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl wget ca-certificates fonts-liberation \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libxss1 libgtk-3-0 fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install playwright && \
    playwright install chromium

# Force fresh code copy — changing this text invalidates Docker cache
# CACHE INVALIDATION MARKER: v5-2025-05-13-healthsrv
COPY . .
RUN chmod +x start.sh

# Download Firebase SDK
RUN curl -sL https://www.gstatic.com/firebasejs/9.22.0/firebase-app-compat.js -o firebase-app-compat.js && \
    curl -sL https://www.gstatic.com/firebasejs/9.22.0/firebase-firestore-compat.js -o firebase-firestore-compat.js && \
    curl -sL https://www.gstatic.com/firebasejs/9.22.0/firebase-auth-compat.js -o firebase-auth-compat.js

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=3s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE ${PORT}

# Start scraper in background, minimal Python HTTP server in foreground
CMD python -c "
import os, sys, json
from http.server import BaseHTTPRequestHandler, HTTPServer
PORT = int(os.getenv('PORT', 5000))
class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{\"status\":\"ok\"}')
        elif self.path.startswith('/api/debug/scraper-log'):
            try:
                n = int(__import__('urllib.parse').parse.parse_qs(self.path.split('?')[1]).get('lines',['50'])[0])
            except: n = 50
            try:
                with open('/tmp/scraper.log','r',encoding='utf-8',errors='replace') as f:
                    lines = f.readlines()
                    log = ''.join(lines[-n:]) if len(lines)>n else ''.join(lines)
            except: log = 'Scraper log not found'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'log': log}).encode())
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{\"error\":\"Not Found\"}')
print(f'[health] Starting on port {PORT}')
# Start scraper in background first
import subprocess
subprocess.Popen([sys.executable, '-u', 'scraper.py'], stdout=open('/tmp/scraper.log','w'), stderr=subprocess.STDOUT)
HTTPServer(('0.0.0.0', PORT), H).serve_forever()
"
