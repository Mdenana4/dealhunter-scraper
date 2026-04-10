# This file makes Render think we are a website
# While secretly running the scraper in the background

import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from scraper import run_scraper, INTERVAL
import schedule

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"DealHunter Scraper is running!")

    def log_message(self, format, *args):
        pass  # Silence web server logs

def run_web_server():
    """Start a tiny web server so Render keeps us alive"""
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"Web server started on port {port}")
    server.serve_forever()

def run_scheduler():
    """Run the scraper on a schedule"""
    print("Scheduler started")
    run_scraper()  # Run immediately on start
    schedule.every(INTERVAL).minutes.do(run_scraper)
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    import os
    print("DealHunter starting...")

    # Start scraper in background thread
    scraper_thread = threading.Thread(target=run_scheduler)
    scraper_thread.daemon = True
    scraper_thread.start()

    # Start web server in main thread (Render requires this)
    run_web_server()