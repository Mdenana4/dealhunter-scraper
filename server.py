# DealHunter Egypt - Web Server Wrapper
# Keeps Render alive while scraper runs in background

import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from scraper import run_scraper, INTERVAL
import schedule
import time


class SimpleHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "26")
        self.end_headers()
        self.wfile.write(b"DealHunter Scraper is running!")

    def do_HEAD(self):
        # UptimeRobot uses HEAD requests — we must support this
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        # Silence web server access logs — only show scraper logs
        pass


def run_web_server():
    """Start tiny web server so Render and UptimeRobot are happy"""
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"Web server started on port {port}")
    server.serve_forever()


def run_scheduler():
    """Run scraper immediately then on schedule"""
    print("Scheduler started — running first scrape now...")
    run_scraper()
    schedule.every(INTERVAL).minutes.do(run_scraper)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    print("DealHunter Egypt Starting...")

    # Start scraper in background thread
    scraper_thread = threading.Thread(target=run_scheduler, daemon=True)
    scraper_thread.start()

    # Start web server in main thread (Render requires this)
    run_web_server()