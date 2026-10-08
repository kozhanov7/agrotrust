"""Reading and validating the CSV files used by the package.

Two tables are used:

* **readings**: one row per received uplink, columns ``timestamp`` and ``node_id``
  (required), ``fcnt`` (LoRaWAN frame counter, optional) and any measured values.
* **events**: one row per logged failure, columns ``start``, ``end``, ``node_id``
  and ``cause``. The cause is one of :data:`CAUSES`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

#: Failure causes. Security events are one cause among others, as in dependability
#: research, where an attack is treated as a fault like any other.
CAUSES = ("hardware", "power", "radio", "software", "security", "unknown")
READING_COLUMNS = ("timestamp", "node_id")
EVENT_COLUMNS = ("start", "end", "node_id", "cause")


def _require(df: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{name} data is missing required column(s): {', '.join(missing)}")


def clean_readings(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalise a table of readings.

    Timestamps become timezone-aware UTC, ``node_id`` becomes text, exact duplicates of
    (node, timestamp) are dropped and rows are sorted by node and time.
    """
    _require(df, READING_COLUMNS, "readings")
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    out["node_id"] = out["node_id"].astype(str)
    out = out.drop_duplicates(subset=["node_id", "timestamp"])
    return out.sort_values(["node_id", "timestamp"]).reset_index(drop=True)


def clean_events(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalise a table of failure events."""
    _require(df, EVENT_COLUMNS, "events")
    out = df.copy()
    for column in ("start", "end"):
        out[column] = pd.to_datetime(out[column], utc=True)
    out["node_id"] = out["node_id"].astype(str)
    out["cause"] = out["cause"].astype(str).str.strip().str.lower()
    unknown = sorted(set(out["cause"]) - set(CAUSES))
    if unknown:
        raise ValueError(
            f"unknown failure cause(s): {', '.join(unknown)}; allowed: {', '.join(CAUSES)}"
        )
    if (out["end"] < out["start"]).any():
        raise ValueError("an event ends before it starts")
    return out.reset_index(drop=True)


def load_readings(path: str | Path) -> pd.DataFrame:
    """Read and clean a readings CSV file."""
    return clean_readings(pd.read_csv(path))


def load_events(path: str | Path) -> pd.DataFrame:
    """Read and clean a failure events CSV file."""
    return clean_events(pd.read_csv(path))
