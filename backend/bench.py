"""
Performance benchmark script for RGM backend.
Tests response times for all key endpoints and produces a report.
Usage: python3 bench.py <uid>
"""
import sys
import time
import json
import urllib.request
import urllib.error
from typing import Optional, Tuple, Any

BASE = "http://localhost:8000"

def req(method: str, path: str, body: Optional[dict] = None, timeout: int = 30) -> Tuple[int, float, Any]:
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}

    start = time.perf_counter()
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, data=data, headers=headers, method=method),
            timeout=timeout
        )
        elapsed = time.perf_counter() - start
        resp_body = json.loads(r.read())
        return r.status, round(elapsed, 3), resp_body
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - start
        return e.code, round(elapsed, 3), e.read().decode()
    except Exception as e:
        elapsed = time.perf_counter() - start
        return 0, round(elapsed, 3), str(e)


def bar(elapsed: float, limit: float = 5.0) -> str:
    filled = int((elapsed / limit) * 20)
    filled = min(filled, 20)
    color = "\033[92m" if elapsed < 1.0 else "\033[93m" if elapsed < 3.0 else "\033[91m"
    reset = "\033[0m"
    return color + "█" * filled + "░" * (20 - filled) + reset + f" {elapsed}s"


def run(uid: str):
    print(f"\n{'='*60}")
    print(f"  RGM Backend Performance Benchmark")
    print(f"  UID: {uid[:12]}...")
    print(f"{'='*60}\n")

    tests = [
        ("GET",  "/api/health",                           None,        "Health check"),
        ("POST", "/api/coach/analyze",                    {"uid": uid}, "AI Coach analyze"),
        ("POST", "/api/science/fitness-trend",            {"uid": uid, "days": 30}, "Fitness Trend (CTL/ATL)"),
        ("POST", "/api/sync/trigger",                     {"uid": uid}, "Strava Sync"),
    ]

    results = []
    for method, path, body, label in tests:
        print(f"  Testing: {label}...")
        status, elapsed, resp = req(method, path, body, timeout=30)
        status_str = "✓" if 200 <= status < 300 else f"✗ {status}"
        results.append((label, status, elapsed, status_str))

    print(f"\n{'─'*60}")
    print(f"  {'Endpoint':<30} {'Status':<8} {'Time':<6}  Chart")
    print(f"{'─'*60}")
    for label, status, elapsed, status_str in results:
        print(f"  {label:<30} {status_str:<8} {elapsed:<6}s  {bar(elapsed)}")

    print(f"\n{'─'*60}")
    slowest = max(results, key=lambda x: x[2])
    fastest = min(results, key=lambda x: x[2])
    print(f"  ⚡ Fastest: {fastest[0]} ({fastest[2]}s)")
    print(f"  🐢 Slowest: {slowest[0]} ({slowest[2]}s)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 bench.py <uid>")
        sys.exit(1)
    run(sys.argv[1])
