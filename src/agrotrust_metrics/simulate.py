"""Synthetic monitoring data with a known ground truth.

Used for tests, demonstrations and for validating the detection logic: the injected
outages are returned next to the readings, so the metrics can be compared with the truth.

Two kinds of outages are modelled. *Node-side* outages (power, hardware, software) silence
the node, so its frame counter does not advance. *Link-side* outages (radio, security)
leave the node transmitting, so the counter advances but nothing is received. The frame
counter therefore shows which kind happened.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

NODE_SIDE = frozenset({"hardware", "power", "software"})
CAUSE_PROBABILITIES = {
    "radio": 0.40,
    "power": 0.25,
    "hardware": 0.20,
    "software": 0.10,
    "security": 0.05,
}
EVENT_COLUMNS = ["node_id", "start", "end", "cause"]


def _sample_outages(rng, total_s, interval_s, rate_per_day, median_min, sigma):
    """Non-overlapping outages (start, end, cause) in seconds from the start of the run."""
    count = rng.poisson(rate_per_day * total_s / 86400)
    starts = np.sort(rng.uniform(0, total_s, count))
    durations = np.maximum(rng.lognormal(np.log(median_min * 60), sigma, count), 2.5 * interval_s)
    merged: list[list[float]] = []
    for begin, length in zip(starts, durations, strict=True):
        if merged and begin < merged[-1][1] + 2 * interval_s:
            merged[-1][1] = max(merged[-1][1], begin + length)
        else:
            merged.append([begin, begin + length])
    edge = 3 * interval_s
    kept = [(a, b) for a, b in merged if a >= edge and b <= total_s - edge]
    causes = rng.choice(
        list(CAUSE_PROBABILITIES), size=len(kept), p=list(CAUSE_PROBABILITIES.values())
    )
    return [(a, b, str(c)) for (a, b), c in zip(kept, causes, strict=True)]


def simulate_node(
    node_id: str,
    start,
    days: float,
    interval,
    rng: np.random.Generator,
    *,
    outage_rate: float = 0.3,
    median_outage_min: float = 60.0,
    sigma: float = 1.0,
    loss_prob: float = 0.01,
    jitter_s: float = 30.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate one node. Returns ``(readings, events)`` where events are the true outages."""
    interval_s = pd.Timedelta(interval).total_seconds()
    t0 = pd.Timestamp(start)
    t0 = t0.tz_localize("UTC") if t0.tzinfo is None else t0.tz_convert("UTC")
    total_s = days * 86400
    sent = int(total_s // interval_s)
    offsets = np.arange(sent) * interval_s
    outages = _sample_outages(rng, total_s, interval_s, outage_rate, median_outage_min, sigma)

    silent = np.zeros(sent, dtype=bool)
    blocked = np.zeros(sent, dtype=bool)
    for begin, finish, cause in outages:
        mask = (offsets >= begin) & (offsets < finish)
        (silent if cause in NODE_SIDE else blocked)[mask] = True

    counter = np.cumsum(~silent) - 1
    random_loss = rng.random(sent) < loss_prob
    delivered = np.flatnonzero(~silent & ~blocked & ~random_loss)
    jitter = rng.uniform(0, jitter_s, delivered.size) if jitter_s > 0 else np.zeros(delivered.size)
    value = 30 + 5 * np.sin(2 * np.pi * offsets[delivered] / 86400)
    value = value + rng.normal(0, 0.5, delivered.size)
    readings = pd.DataFrame(
        {
            "timestamp": t0 + pd.to_timedelta(offsets[delivered] + jitter, unit="s"),
            "node_id": node_id,
            "fcnt": counter[delivered],
            "value": value.round(2),
        }
    )
    events = pd.DataFrame(
        [
            (node_id, t0 + pd.Timedelta(seconds=a), t0 + pd.Timedelta(seconds=b), c)
            for a, b, c in outages
        ],
        columns=EVENT_COLUMNS,
    )
    return readings, events


def _concat(frames: list[pd.DataFrame], columns: list[str] | None = None) -> pd.DataFrame:
    full = [f for f in frames if not f.empty]
    if not full:
        return pd.DataFrame(columns=columns)
    return pd.concat(full, ignore_index=True)


def simulate_fleet(
    n_nodes: int = 14,
    days: float = 30,
    interval="10min",
    seed: int = 42,
    start="2026-12-01",
    **node_options,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate several nodes with one seeded generator (same seed, same data)."""
    rng = np.random.default_rng(seed)
    parts = [
        simulate_node(f"N{i:02d}", start, days, interval, rng, **node_options)
        for i in range(1, n_nodes + 1)
    ]
    readings = _concat([p[0] for p in parts])
    events = _concat([p[1] for p in parts], EVENT_COLUMNS)
    return readings, events
