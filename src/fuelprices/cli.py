"""Command line entry point: ``fuelprices fetch``, ``show`` and ``advise``."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from fuelprices import advice, history, storage
from fuelprices.sources import fod

DEFAULT_HISTORY = Path("data/max_prices.csv")


def _fetch(args: argparse.Namespace) -> None:
    records = fod.parse(args.html.read_text(encoding="utf-8")) if args.html else fod.fetch_prices()
    history = storage.update_history(args.history, records)
    for r in records:
        print(f"{r.valid_from}  {r.product.label:<36} {r.price_eur_per_litre:.4f} EUR/l")
    print(f"{len(history)} rows in {args.history}")


def _show(args: argparse.Namespace) -> None:
    latest = {}
    for r in storage.load_history(args.history):
        latest[r.product] = r
    if not latest:
        print(f"no prices in {args.history} yet; run `fuelprices fetch` first")
    for r in latest.values():
        print(f"{r.valid_from}  {r.product.label:<36} {r.price_eur_per_litre:.4f} EUR/l")


def _advise(args: argparse.Namespace) -> None:
    today = args.date or date.today()
    conn = history.connect(args.db)
    try:
        data = advice.export(conn, today)
    finally:
        conn.close()
    print(f"Refuel advice for {today:%a %d %b %Y}")
    for a in data["advice"]:
        cents = a["expected_change_cents"]
        change = "" if cents is None else f" ({cents:+.1f} cent/L)"
        print(f"  {a['label']:<20} {a['headline']}{change}: {a['reason']}")
    for b in data["backtest"]:
        if b["windows"]:
            print(
                f"  backtest {b['product']}: saved {b['saved']}, same {b['same']}, "
                f"lost {b['lost']} of {b['windows']} windows, "
                f"average {b['avg_saving_cents']:+.2f} cent/L versus a random day"
            )
        else:
            print(f"  backtest {b['product']}: {b['note']}")
    if args.json:
        written = advice.write_json(args.json, data)
        print(f"{'wrote' if written else 'unchanged'} {args.json}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="fuelprices", description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY, help="price history CSV")
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser("fetch", help="download today's official prices into the history")
    fetch.add_argument("--html", type=Path, help="parse a saved copy of the page instead")
    fetch.set_defaults(handler=_fetch)

    show = commands.add_parser("show", help="print the latest known price per product")
    show.set_defaults(handler=_show)

    advise = commands.add_parser("advise", help="fill up today, wait, or no difference")
    advise.add_argument("--db", type=Path, default=history.DEFAULT_DB_PATH, help="SQLite history")
    advise.add_argument("--json", type=Path, help="also write the advice to this JSON file")
    advise.add_argument("--date", type=date.fromisoformat, help="advise as of this day")
    advise.set_defaults(handler=_advise)

    args = parser.parse_args(argv)
    args.handler(args)


if __name__ == "__main__":
    main()
