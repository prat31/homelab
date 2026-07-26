"""Lightweight CrowdSec stats API for Homarr dashboard integration.

Queries CrowdSec LAPI /v1/decisions, aggregates counts by scenario / origin / type,
caches the result for CACHE_TTL seconds, and serves a tiny JSON payload on /stats.
No external dependencies — stdlib only.
"""

import http.server
import json
import os
import threading
import time
import urllib.request
from collections import Counter

LAPI_HOST = os.environ.get("CROWDSEC_LAPI_HOST", "homelab-crowdsec:8080")
LAPI_KEY = os.environ.get("CROWDSEC_BOUNCER_KEY", "")
CACHE_TTL = int(os.environ.get("CACHE_TTL", "60"))
PORT = int(os.environ.get("PORT", "8088"))

_cache = {"data": None, "ts": 0}
_lock = threading.Lock()

SCENARIO_LABELS = {
    "http:crawl": "HTTP Crawling",
    "http:scan": "HTTP Scanning",
    "ssh:bruteforce": "SSH Brute Force",
    "generic:scan": "Generic Scan",
    "http:exploit": "HTTP Exploit",
    "http:bruteforce": "HTTP Brute Force",
}


def _fetch_decisions():
    req = urllib.request.Request(
        f"http://{LAPI_HOST}/v1/decisions",
        headers={"X-Api-Key": LAPI_KEY},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def get_stats():
    now = time.time()
    with _lock:
        if _cache["data"] is not None and now - _cache["ts"] < CACHE_TTL:
            return _cache["data"]

    try:
        decisions = _fetch_decisions()

        by_scenario = Counter(d.get("scenario", "unknown") for d in decisions)
        by_origin = Counter(d.get("origin", "unknown") for d in decisions)
        by_type = Counter(d.get("type", "unknown") for d in decisions)

        scenarios = []
        for scenario, count in by_scenario.most_common():
            scenarios.append({
                "scenario": scenario,
                "label": SCENARIO_LABELS.get(scenario, scenario),
                "count": count,
            })

        stats = {
            "total_decisions": len(decisions),
            "community_bans": by_origin.get("CAPI", 0),
            "local_bans": by_origin.get("cscli", 0) + by_origin.get("local", 0),
            "by_type": dict(by_type),
            "scenarios": scenarios,
            "healthy": True,
            "fetched_at": now,
        }

        with _lock:
            _cache["data"] = stats
            _cache["ts"] = now
        return stats
    except Exception as e:
        return {"error": str(e), "total_decisions": 0, "healthy": False}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/stats":
            body = json.dumps(get_stats()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"CrowdSec stats API listening on :{PORT}", flush=True)
    server.serve_forever()
