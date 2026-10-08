"""Check outage detection against the injected ground truth of the simulator.

Run:  python examples/validate_detection.py --seeds 20

For each seed a 14-node, 30-day fleet is simulated with 1% random packet loss and up to
30 s of timing jitter. A true outage counts as found when a detected outage on the same
node overlaps it. Only true outages that span at least ``min_missed`` sampling slots are
expected to be found, because shorter ones are indistinguishable from packet loss.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from agrotrust_metrics.io import clean_events, clean_readings
from agrotrust_metrics.metrics import find_outages
from agrotrust_metrics.simulate import simulate_fleet

IV = pd.Timedelta(minutes=10)


def overlaps(a: pd.DataFrame, b_row) -> pd.Series:
    return (a["node_id"] == b_row.node_id) & (a["start"] < b_row.end) & (a["end"] > b_row.start)


def run(seed: int, min_missed: int) -> dict:
    readings, events = simulate_fleet(14, 30, IV, seed)
    truth = clean_events(events)
    found = find_outages(clean_readings(readings), IV, min_missed=min_missed)
    expected = truth[(truth["end"] - truth["start"]) >= min_missed * IV]
    hits = sum(overlaps(found, row).any() for row in expected.itertuples())
    true_pos = sum(overlaps(truth, row).any() for row in found.itertuples())
    errors = []
    for row in expected.itertuples():
        match = found[overlaps(found, row)]
        if len(match) == 1:
            errors.append(
                abs((match["lost"].iloc[0] - (row.end - row.start)) / pd.Timedelta(minutes=1))
            )
    return {
        "recall": hits / len(expected) if len(expected) else 1.0,
        "precision": true_pos / len(found) if len(found) else 1.0,
        "median_error_min": float(np.median(errors)) if errors else 0.0,
        "expected": len(expected),
        "found": len(found),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--min-missed", type=int, default=3)
    args = parser.parse_args()
    rows = pd.DataFrame([run(s, args.min_missed) for s in range(args.seeds)])
    print(rows.describe().loc[["mean", "min", "max"]].round(3).to_string())


if __name__ == "__main__":
    main()
