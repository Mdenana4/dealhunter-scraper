# DealHunter Egypt - Web Server Wrapper
# Keeps Render alive + runs scraper in background thread

import threading
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import schedule


class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "30")
        self.end_headers()
        self.wfile.write(b"DealHunter Scraper is running!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # silence access logs


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"Web server started on port {port}")
    server.serve_forever()


def run_scheduler():
    from scraper import run_scraper, INTERVAL
    print("Scheduler started — running first scrape now...")
    run_scraper()
    schedule.every(INTERVAL).minutes.do(run_scraper)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    print("DealHunter Egypt Starting...")
    scraper_thread = threading.Thread(target=run_scheduler, daemon=True)
    scraper_thread.start()
    run_web_server()
