"""Push the refuel advice to a ntfy topic (https://ntfy.sh), so anyone can subscribe.

Run by the daily workflow after the advice is written. The topic is the secret NTFY_TOPIC: the
repository is public, so the topic name must not be committed or printed. Without it, nothing
is sent. By default a message goes out only when the action for diesel B7 or E10 changed
compared with the previous data/advice.json; NTFY_DAILY=1 sends a summary every run.
Only data/advice.json is used, never the private heating module.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

DASHBOARD_URL = "https://stijndh88.github.io/fuelpricesbelgium/"
SERVER = "https://ntfy.sh"
PRODUCTS = ("diesel_b7", "e10")


def _actions(advice: dict | None) -> dict[str, str]:
    if not advice:
        return {}
    return {
        item["product"]: item["action"]
        for item in advice.get("advice", [])
        if item.get("product") in PRODUCTS
    }


def changed(current: dict, previous: dict | None) -> bool:
    """True when the action of a product differs from the previous advice (or there was none)."""
    before = _actions(previous)
    return any(before.get(p) != a for p, a in _actions(current).items())


def build_message(current: dict) -> tuple[str, str]:
    """Return (title, body): headline and reason per product."""
    items = [i for i in current.get("advice", []) if i.get("product") in PRODUCTS]
    title = "Refuel advice: " + ", ".join(f"{i['label']}: {i['headline']}" for i in items)
    body = "\n".join(f"{i['label']}: {i['reason']}" for i in items)
    return title, body


def send(topic: str, title: str, body: str, server: str = SERVER) -> None:
    request = urllib.request.Request(
        f"{server.rstrip('/')}/{topic}",
        data=body.encode(),
        headers={
            "Title": title.encode("utf-8").decode("latin-1", "ignore"),
            "Click": DASHBOARD_URL,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30):
        pass


def run(
    current_path: Path, previous_path: Path | None, topic: str, daily: bool, dry_run: bool
) -> str:
    """Decide and send; returns a short status line that is safe to log (no topic)."""
    if not current_path.exists():
        return "No advice file; nothing to send."
    current = json.loads(current_path.read_text())
    previous = None
    if previous_path and previous_path.exists():
        previous = json.loads(previous_path.read_text())
    if not (daily or changed(current, previous)):
        return "Advice unchanged; no notification."
    title, body = build_message(current)
    if dry_run:
        return f"Dry run, would send:\n{title}\n{body}"
    if not topic:
        return "NTFY_TOPIC is not set; skipping notification."
    send(topic, title, body)
    return "Notification sent."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--advice", type=Path, default=Path("data/advice.json"))
    parser.add_argument("--previous", type=Path, help="advice.json from before this run")
    parser.add_argument("--dry-run", action="store_true", help="print the message, send nothing")
    args = parser.parse_args(argv)
    daily = os.environ.get("NTFY_DAILY", "") == "1"
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    print(run(args.advice, args.previous, topic, daily, args.dry_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
