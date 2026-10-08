"""Static figures: an outage timeline per node and downtime by cause."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from .metrics import observation_window

CAUSE_COLORS = {
    "radio": "#4a78a8",
    "power": "#d9822b",
    "hardware": "#c0504d",
    "software": "#8e6bb0",
    "security": "#23405f",
    "unknown": "#8a8f96",
}
UP_COLOR = "#cfe3d3"


def _num(ts) -> float:
    return mdates.date2num(pd.Timestamp(ts).to_pydatetime(warn=False))


def plot_timeline(
    readings: pd.DataFrame, interval, outages: pd.DataFrame, path: str | Path | None = None
) -> Figure:
    """Draw one bar per node: green while up, coloured by cause during outages."""
    start, end = observation_window(readings, interval)
    nodes = sorted(readings["node_id"].unique())
    fig = Figure(figsize=(8.0, 0.3 * len(nodes) + 1.5))
    ax = fig.subplots()
    x0, x1 = _num(start), _num(end)
    for row, node in enumerate(nodes):
        y = len(nodes) - row - 1
        ax.broken_barh([(x0, x1 - x0)], (y - 0.35, 0.7), facecolors=UP_COLOR)
        for outage in outages[outages["node_id"] == node].itertuples():
            colour = CAUSE_COLORS.get(getattr(outage, "cause", "unknown"), CAUSE_COLORS["unknown"])
            width = _num(outage.end) - _num(outage.start)
            ax.broken_barh([(_num(outage.start), width)], (y - 0.35, 0.7), facecolors=colour)
    ax.set_yticks(range(len(nodes)), labels=nodes[::-1], fontsize=7)
    ax.set_xlim(x0, x1)
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.tick_params(axis="x", labelsize=8)
    shown = sorted(set(outages["cause"])) if "cause" in outages.columns else ["unknown"]
    handles = [Patch(color=UP_COLOR, label="up")]
    handles += [Patch(color=CAUSE_COLORS[c], label=c) for c in shown if c in CAUSE_COLORS]
    ax.legend(
        handles=handles,
        ncol=len(handles),
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
        frameon=False,
        fontsize=8,
    )
    ax.set_title("Detected outages per node", fontsize=10)
    if path is not None:
        fig.savefig(path, dpi=200, bbox_inches="tight")
    return fig


def plot_causes(table: pd.DataFrame, path: str | Path | None = None) -> Figure:
    """Horizontal bars of downtime hours per failure cause."""
    shown = table[table["downtime_h"] > 0]
    fig = Figure(figsize=(5.0, 2.4))
    ax = fig.subplots()
    colors = [CAUSE_COLORS.get(c, CAUSE_COLORS["unknown"]) for c in shown.index]
    ax.barh(list(shown.index), shown["downtime_h"], color=colors)
    ax.set_xlabel("downtime, hours")
    ax.invert_yaxis()
    if path is not None:
        fig.savefig(path, dpi=200, bbox_inches="tight")
    return fig
