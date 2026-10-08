"""Reliability metrics computed from timestamped sensor readings.

Definitions (see also the README):

* A **gap** is a time between two consecutive readings of one node that is longer than
  ``tolerance`` sampling intervals. ``missed`` estimates how many readings are absent.
* An **outage** is a gap with at least ``min_missed`` missing readings. Shorter gaps are
  treated as ordinary packet loss and do not count as downtime.
* **Downtime** of an outage is the time without data: ``duration - interval``.
* **Availability** = uptime / observation time, with uptime = observation time - downtime.
* **MTBF** = uptime / number of outages, **MTTR** = downtime / number of outages.
* **Completeness** = share of sampling slots that hold at least one reading.
* **Packet delivery ratio** (PDR) = received frames / frames sent, from the frame counter.
"""

from __future__ import annotations

import math

import pandas as pd

from .io import CAUSES

GAP_COLUMNS = ["node_id", "start", "end", "duration", "lost", "missed"]
HOUR = pd.Timedelta(hours=1)


def _utc(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def _interval(value) -> pd.Timedelta:
    iv = pd.Timedelta(value)
    if iv <= pd.Timedelta(0):
        raise ValueError("interval must be positive")
    return iv


def observation_window(
    readings: pd.DataFrame, interval, start=None, end=None
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return the observation window ``[start, end)``.

    By default it runs from the first reading to one interval after the last reading.
    """
    iv = _interval(interval)
    if readings.empty and (start is None or end is None):
        raise ValueError("no readings and no explicit observation window")
    s = _utc(start) if start is not None else readings["timestamp"].min()
    e = _utc(end) if end is not None else readings["timestamp"].max() + iv
    if e <= s:
        raise ValueError("observation window must have a positive length")
    return s, e


def _clip(readings: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return readings[(readings["timestamp"] >= start) & (readings["timestamp"] < end)]


def _typed_gaps(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.astype(
        {
            "node_id": "object",
            "start": "datetime64[ns, UTC]",
            "end": "datetime64[ns, UTC]",
            "duration": "timedelta64[ns]",
            "lost": "timedelta64[ns]",
            "missed": "int64",
        }
    )


def detect_gaps(
    readings: pd.DataFrame, interval, tolerance: float = 1.5, start=None, end=None
) -> pd.DataFrame:
    """Find gaps between consecutive readings of each node.

    Without ``start`` and ``end`` only gaps between received readings are reported. With an
    explicit window, a node that begins late or stops early also produces boundary gaps.
    """
    iv = _interval(interval)
    if tolerance <= 1:
        raise ValueError("tolerance must be greater than 1")
    rows = []
    for node, group in readings.groupby("node_id", sort=True):
        times = group["timestamp"].sort_values().tolist()
        if start is not None:
            times.insert(0, _utc(start) - iv)
        if end is not None:
            times.append(_utc(end))
        for previous, following in zip(times, times[1:], strict=False):
            diff = following - previous
            if diff > tolerance * iv:
                rows.append((node, previous, following, diff, diff - iv, int(round(diff / iv)) - 1))
    return _typed_gaps(pd.DataFrame(rows, columns=GAP_COLUMNS))


def outages_from_gaps(gaps: pd.DataFrame, min_missed: int = 3) -> pd.DataFrame:
    """Keep the gaps that are long enough to count as outages."""
    return gaps[gaps["missed"] >= min_missed].reset_index(drop=True)


def find_outages(
    readings: pd.DataFrame,
    interval,
    min_missed: int = 3,
    tolerance: float = 1.5,
    start=None,
    end=None,
) -> pd.DataFrame:
    """Detect outages inside the observation window (gaps, then the ``min_missed`` filter)."""
    s, e = observation_window(readings, interval, start, end)
    gaps = detect_gaps(_clip(readings, s, e), interval, tolerance, s, e)
    return outages_from_gaps(gaps, min_missed)


def data_completeness(readings: pd.DataFrame, interval, start, end) -> pd.Series:
    """Share of sampling slots in ``[start, end)`` that contain at least one reading."""
    iv = _interval(interval)
    s, e = _utc(start), _utc(end)
    slots = math.ceil((e - s) / iv)
    sub = _clip(readings, s, e)
    slot_index = (sub["timestamp"] - s) // iv
    filled = slot_index.groupby(sub["node_id"]).nunique()
    nodes = sorted(readings["node_id"].unique())
    return (filled.reindex(nodes, fill_value=0) / slots).clip(upper=1.0).rename("completeness")


def packet_delivery_ratio(readings: pd.DataFrame) -> pd.Series:
    """Received frames divided by frames sent, estimated from the LoRaWAN frame counter.

    A decrease of the counter is treated as a reset (or wrap-around) and starts a new
    segment, so frames lost at the very start or end of a segment cannot be seen.
    """
    if "fcnt" not in readings.columns or readings["fcnt"].isna().any():
        raise ValueError("packet delivery ratio needs a complete 'fcnt' column")
    result = {}
    for node, group in readings.groupby("node_id", sort=True):
        counter = group.sort_values("timestamp")["fcnt"].astype(int).reset_index(drop=True)
        segment = (counter.diff() < 0).cumsum()
        received = expected = 0
        for _, part in counter.groupby(segment):
            received += part.nunique()
            expected += part.max() - part.min() + 1
        result[node] = received / expected
    return pd.Series(result, name="pdr", dtype=float)


def summarize(
    readings: pd.DataFrame,
    interval,
    start=None,
    end=None,
    min_missed: int = 3,
    tolerance: float = 1.5,
) -> pd.DataFrame:
    """Per-node reliability table: completeness, PDR, outages, availability, MTBF, MTTR."""
    iv = _interval(interval)
    s, e = observation_window(readings, iv, start, end)
    readings = _clip(readings, s, e)
    total = e - s
    outages = outages_from_gaps(detect_gaps(readings, iv, tolerance, s, e), min_missed)
    completeness = data_completeness(readings, iv, s, e)
    has_counter = "fcnt" in readings.columns and not readings["fcnt"].isna().any()
    pdr = packet_delivery_ratio(readings) if has_counter else None
    rows = []
    for node in sorted(readings["node_id"].unique()):
        own = outages[outages["node_id"] == node]
        down = min(pd.Timedelta(own["lost"].sum()), total)
        up = total - down
        count = len(own)
        rows.append(
            {
                "node_id": node,
                "readings": int((readings["node_id"] == node).sum()),
                "completeness": completeness[node],
                "pdr": pdr[node] if pdr is not None else math.nan,
                "outages": count,
                "downtime_h": down / HOUR,
                "uptime_h": up / HOUR,
                "availability": up / total,
                "mtbf_h": up / HOUR / count if count else math.inf,
                "mttr_h": down / HOUR / count if count else math.nan,
            }
        )
    return pd.DataFrame(rows).set_index("node_id")


def overall(table: pd.DataFrame) -> pd.Series:
    """Fleet-level figures from a :func:`summarize` table (MTBF and MTTR are pooled)."""
    outages = int(table["outages"].sum())
    up, down = table["uptime_h"].sum(), table["downtime_h"].sum()
    return pd.Series(
        {
            "nodes": len(table),
            "availability": up / (up + down),
            "completeness": table["completeness"].mean(),
            "pdr": table["pdr"].mean(),
            "outages": outages,
            "mtbf_h": up / outages if outages else math.inf,
            "mttr_h": down / outages if outages else math.nan,
            "worst_node": table["availability"].idxmin(),
            "worst_availability": table["availability"].min(),
        },
        dtype=object,
    )


def attach_causes(outages: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Label each detected outage with the cause of the first logged event that overlaps it.

    Outages without an overlapping event on the same node are labelled ``unknown``.
    """
    labelled = outages.copy()
    causes = []
    for row in labelled.itertuples():
        match = events[
            (events["node_id"] == row.node_id)
            & (events["start"] < row.end)
            & (events["end"] > row.start)
        ]
        causes.append(match.sort_values("start").iloc[0]["cause"] if len(match) else "unknown")
    labelled["cause"] = causes
    return labelled


def failures_by_cause(outages: pd.DataFrame) -> pd.DataFrame:
    """Count, downtime and share of downtime per failure cause (security is one row)."""
    if "cause" not in outages.columns:
        raise ValueError("outages must have a 'cause' column; call attach_causes first")
    table = outages.groupby("cause").agg(
        count=("node_id", "size"), downtime_h=("lost", lambda s: s.sum() / HOUR)
    )
    table = table.reindex(CAUSES, fill_value=0).astype({"count": int})
    total = table["downtime_h"].sum()
    table["share"] = table["downtime_h"] / total if total > 0 else 0.0
    return table
