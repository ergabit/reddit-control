#!/usr/bin/env python3
"""
Radar scanner — reads Reddit via reddit.py skill, scores threads, pushes to API.
Run from cron or manually.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

API_URL = os.environ.get("API_URL", "http://localhost:8000")
RADAR_SCRIPT = os.path.expanduser("~/.hermes/scripts/reddit_radar_quick.sh")


def run_radar_command(cmd: str) -> str:
    """Run a radar script command and return stdout."""
    try:
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=300
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def parse_radar_output(output: str) -> list[dict]:
    """Parse radar digest output into thread dicts."""
    threads = []
    current = {}
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            if current.get("title"):
                threads.append(current)
                current = {}
            continue

        # Parse key: value pairs from radar output
        if ": " in line and not line.startswith("•") and not line.startswith("==="):
            key, _, value = line.partition(": ")
            key = key.strip().lower().replace(" ", "_")
            if key in ("title", "url", "subreddit", "author", "topic", "body_preview"):
                current[key] = value
            elif key in ("score", "num_comments"):
                try:
                    current[key] = int(value)
                except ValueError:
                    current[key] = 0
            elif key in ("score_radar"):
                try:
                    current[key] = float(value)
                except ValueError:
                    current[key] = 0

    if current.get("title"):
        threads.append(current)

    return threads


def push_to_api(threads: list[dict]):
    """Push threads to the mission control API."""
    if not threads:
        print("No threads to push")
        return

    print(f"Pushing {len(threads)} threads to API...")
    data = json.dumps(threads).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/api/radar/import",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            print(f"  Imported {result.get('imported', 0)} threads")
    except urllib.error.HTTPError as e:
        print(f"  API error: {e.code} {e.read().decode()[:200]}")
    except Exception as e:
        print(f"  Push error: {e}")


def run_quick_sweep():
    """Run the quick sweep radar command."""
    print("Running quick sweep...")
    output = run_radar_command(
        "cd /home/hermes/workspaces/isearchfrom/content/reddit/radar && "
        "python3 radar.py sweep --quick 2>&1"
    )
    threads = parse_radar_output(output)
    push_to_api(threads)
    return threads


def run_full_sweep():
    """Run the full sweep radar command."""
    print("Running full sweep...")
    output = run_radar_command(
        "cd /home/hermes/workspaces/isearchfrom/content/reddit/radar && "
        "python3 radar.py sweep --full 2>&1"
    )
    threads = parse_radar_output(output)
    push_to_api(threads)
    return threads


def run_digest():
    """Run the digest and push top threads + drafts."""
    print("Running digest...")
    output = run_radar_command(
        "cd /home/hermes/workspaces/isearchfrom/content/reddit/radar && "
        "python3 radar.py digest 2>&1"
    )
    threads = parse_radar_output(output)
    push_to_api(threads)
    return threads


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "quick"

    if cmd == "quick":
        run_quick_sweep()
    elif cmd == "full":
        run_full_sweep()
    elif cmd == "digest":
        run_digest()
    elif cmd == "all":
        run_quick_sweep()
        time.sleep(65)  # Wait for rate limit
        run_full_sweep()
        time.sleep(65)
        run_digest()
    else:
        print(f"Usage: {sys.argv[0]} [quick|full|digest|all]")
        sys.exit(1)


if __name__ == "__main__":
    main()
