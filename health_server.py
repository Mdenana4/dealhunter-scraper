#!/usr/bin/env python3
"""Minimal health server for Railway — starts instantly, no imports."""
import os, sys, json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

PORT = int(os.getenv("PORT", 5000))
SCRAPER_LOG = "/tmp/scraper.log"

def read_scraper_log(lines=50):
    try:
        with open(SCRAPER_LOG, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return "".join(tail)
    except FileNotFoundError:
        return "Scraper log not found — scraper may not have started yet"
    except Exception as e:
        return f"Error reading log: {e}"

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Suppress access logs

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            self.send_json(200, {"status": "ok"})
        elif path == "/api/debug/scraper-log":
            qs = parse_qs(parsed.query)
            try:
                n = int(qs.get("lines", ["50"])[0])
            except ValueError:
                n = 50
            log_content = read_scraper_log(n)
            self.send_json(200, {
                "path": SCRAPER_LOG,
                "showing_last": min(n, 50),
                "log": log_content
            })
        elif path == "/api/debug/scraper-status":
            log_content = read_scraper_log(20)
            self.send_json(200, {
                "scraper_running": True,
                "has_log": os.path.exists(SCRAPER_LOG),
                "last_lines": log_content[-500:] if log_content else ""
            })
        else:
            self.send_json(404, {"error": "Not Found", "path": path})

    def send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

if __name__ == "__main__":
    print(f"[health-server] Starting on port {PORT}")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
