"""Command line entry point: ``fuelprices fetch``, ``show`` and ``advise``."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from fuelprices import advice, calibrate, history, storage
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
    if args.shock_threshold is not None and args.shock_threshold <= 0:
        args.shock_threshold = None
    conn = history.connect(args.db)
    try:
        data = advice.export(conn, today, args.shock_threshold)
    finally:
        conn.close()
    print(f"Refuel advice for {today:%a %d %b %Y}")
    for a in data["advice"]:
        cents = a["expected_change_cents"]
        change = "" if cents is None else f" ({cents:+.1f} cent/L)"
        print(f"  {a['label']:<20} {a['headline']}{change}: {a['reason']}")
        if a["market_note"] and a["basis"] != "shock":
            print(f"  {'':<20} {a['market_note']}")
    for b in data["backtest"]:
        if b["windows"]:
            shock = "off" if b["shock_threshold"] is None else f"{b['shock_threshold']:.0%}"
            print(
                f"  backtest {b['product']} (shock flag {shock}): saved {b['saved']}, "
                f"same {b['same']}, lost {b['lost']} of {b['windows']} windows, "
                f"average {b['avg_saving_cents']:+.2f} cent/L versus a random day"
            )
        elif b["shock_threshold"] is None:
            print(f"  backtest {b['product']}: {b['note']}")
    if args.json:
        written = advice.write_json(args.json, data)
        print(f"{'wrote' if written else 'unchanged'} {args.json}")


def _calibrate(args: argparse.Namespace) -> None:
    conn = history.connect(args.db)
    try:
        calibrations = calibrate.calibrate_all(history.all_rows(conn))
    finally:
        conn.close()
    print(calibrate.report(calibrations))
    if args.json:
        written = calibrate.save(args.json, calibrations)
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
    advise.add_argument(
        "--shock-threshold",
        type=float,
        default=advice.SHOCK_THRESHOLD,
        help="market move (fraction) that counts as a shock; 0 or less turns the flag off",
    )
    advise.set_defaults(handler=_advise)

    cal = commands.add_parser("calibrate", help="fit the price-change rules to the stored history")
    cal.add_argument("--db", type=Path, default=history.DEFAULT_DB_PATH, help="SQLite history")
    cal.add_argument("--json", type=Path, help="also write the fit to this JSON file")
    cal.set_defaults(handler=_calibrate)

    args = parser.parse_args(argv)
    args.handler(args)


if __name__ == "__main__":
    main()
