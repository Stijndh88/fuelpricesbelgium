"""Command line entry point: ``fuelprices fetch`` and ``fuelprices show``."""

from __future__ import annotations

import argparse
from pathlib import Path

from fuelprices import storage
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="fuelprices", description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY, help="price history CSV")
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser("fetch", help="download today's official prices into the history")
    fetch.add_argument("--html", type=Path, help="parse a saved copy of the page instead")
    fetch.set_defaults(handler=_fetch)

    show = commands.add_parser("show", help="print the latest known price per product")
    show.set_defaults(handler=_show)

    args = parser.parse_args(argv)
    args.handler(args)


if __name__ == "__main__":
    main()
