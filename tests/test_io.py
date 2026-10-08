import pandas as pd
import pytest

from agrotrust_metrics.io import CAUSES, clean_events, clean_readings, load_events, load_readings


def test_clean_readings_sorts_dedupes_and_sets_utc():
    df = pd.DataFrame(
        {
            "timestamp": ["2026-12-01 00:10:00", "2026-12-01 00:00:00", "2026-12-01 00:00:00"],
            "node_id": [1, 1, 1],
        }
    )
    out = clean_readings(df)
    assert len(out) == 2
    assert out["timestamp"].is_monotonic_increasing
    assert str(out["timestamp"].dt.tz) == "UTC"
    assert out["node_id"].tolist() == ["1", "1"]


def test_readings_need_required_columns():
    with pytest.raises(ValueError, match="node_id"):
        clean_readings(pd.DataFrame({"timestamp": ["2026-12-01"]}))


def _events(cause="power", start="2026-12-01 01:00", end="2026-12-01 02:00"):
    return pd.DataFrame({"start": [start], "end": [end], "node_id": ["A"], "cause": [cause]})


def test_clean_events_normalises_cause():
    assert clean_events(_events(cause=" Power "))["cause"].tolist() == ["power"]


def test_unknown_cause_is_rejected():
    with pytest.raises(ValueError, match="unknown failure cause"):
        clean_events(_events(cause="gremlins"))


def test_event_cannot_end_before_it_starts():
    with pytest.raises(ValueError, match="ends before"):
        clean_events(_events(start="2026-12-01 03:00", end="2026-12-01 02:00"))


def test_security_is_one_of_the_causes():
    assert "security" in CAUSES


def test_load_functions_read_csv(tmp_path):
    readings = tmp_path / "r.csv"
    readings.write_text("timestamp,node_id\n2026-12-01 00:00:00,A\n")
    events = tmp_path / "e.csv"
    events.write_text("start,end,node_id,cause\n2026-12-01 01:00,2026-12-01 02:00,A,radio\n")
    assert len(load_readings(readings)) == 1
    assert load_events(events)["cause"].tolist() == ["radio"]
