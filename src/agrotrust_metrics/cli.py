"""Command-line interface: ``agrometrics simulate | summarize | plot``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from . import __version__
from .io import load_events, load_readings
from .metrics import attach_causes, failures_by_cause, find_outages, overall, summarize
from .plot import plot_causes, plot_timeline
from .simulate import simulate_fleet


def _interval(args: argparse.Namespace) -> pd.Timedelta:
    return pd.Timedelta(minutes=args.interval)


def cmd_simulate(args: argparse.Namespace) -> int:
    readings, events = simulate_fleet(args.nodes, args.days, _interval(args), args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    readings.to_csv(out / "readings.csv", index=False)
    events.to_csv(out / "events.csv", index=False)
    print(f"wrote {len(readings)} readings and {len(events)} injected outages to {out}")
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    readings = load_readings(args.readings)
    interval = _interval(args)
    table = summarize(readings, interval, min_missed=args.min_missed)
    print(table.round(4).to_string())
    print()
    for key, value in overall(table).items():
        print(f"{key:>18}: {value:.4f}" if isinstance(value, float) else f"{key:>18}: {value}")
    if args.events:
        outages = find_outages(readings, interval, args.min_missed)
        outages = attach_causes(outages, load_events(args.events))
        print()
        print(failures_by_cause(outages).round(3).to_string())
    if args.out:
        table.to_csv(args.out)
    return 0


def cmd_plot(args: argparse.Namespace) -> int:
    readings = load_readings(args.readings)
    interval = _interval(args)
    outages = find_outages(readings, interval, args.min_missed)
    if args.events:
        outages = attach_causes(outages, load_events(args.events))
        if args.causes_out:
            plot_causes(failures_by_cause(outages), args.causes_out)
    plot_timeline(readings, interval, outages, args.out)
    print(f"wrote {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agrometrics",
        description="Reliability metrics for IoT agricultural monitoring data.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--interval", type=float, default=10.0, help="sampling interval, minutes")

    sim = sub.add_parser("simulate", help="write synthetic readings and true outages")
    common(sim)
    sim.add_argument("--nodes", type=int, default=14)
    sim.add_argument("--days", type=float, default=30)
    sim.add_argument("--seed", type=int, default=42)
    sim.add_argument("--out", default="data", help="output directory")
    sim.set_defaults(func=cmd_simulate)

    summ = sub.add_parser("summarize", help="print reliability metrics")
    common(summ)
    summ.add_argument("readings", help="readings CSV")
    summ.add_argument("--events", help="failure events CSV, adds a table by cause")
    summ.add_argument(
        "--min-missed", type=int, default=3, help="missed readings that make an outage"
    )
    summ.add_argument("--out", help="write the per-node table to this CSV")
    summ.set_defaults(func=cmd_summarize)

    plot = sub.add_parser("plot", help="draw the outage timeline")
    common(plot)
    plot.add_argument("readings", help="readings CSV")
    plot.add_argument("--events", help="failure events CSV, colours outages by cause")
    plot.add_argument("--min-missed", type=int, default=3)
    plot.add_argument("--out", default="timeline.png")
    plot.add_argument("--causes-out", help="also draw downtime by cause (needs --events)")
    plot.set_defaults(func=cmd_plot)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
