#!/usr/bin/env python3
"""MINIMAL server — only health and scraper log. No heavy imports."""
import os
import json
from flask import Flask, jsonify, request

app = Flask(__name__)
SCRAPER_LOG = "/tmp/scraper.log"

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/api/debug/scraper-log")
def scraper_log():
    lines = request.args.get("lines", "50")
    try:
        n = int(lines)
    except ValueError:
        n = 50
    if not os.path.exists(SCRAPER_LOG):
        return jsonify({"error": "Scraper log not found"}), 404
    try:
        with open(SCRAPER_LOG, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            tail = all_lines[-n:] if len(all_lines) > n else all_lines
            return jsonify({
                "path": SCRAPER_LOG,
                "total_lines": len(all_lines),
                "showing_last": len(tail),
                "log": "".join(tail)
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/debug/scraper-status")
def scraper_status():
    import os as os2
    exists = os2.path.exists(SCRAPER_LOG)
    return jsonify({
        "scraper_running": True,
        "has_log": exists,
        "status": "running"
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[minimal-server] Starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
