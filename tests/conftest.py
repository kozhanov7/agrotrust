import pandas as pd
import pytest

from agrotrust_metrics.io import clean_readings

T0 = pd.Timestamp("2026-12-01", tz="UTC")


def build_readings(minutes, node="A", fcnt=None):
    """Readings of one node at the given minutes after T0."""
    df = pd.DataFrame(
        {"timestamp": [T0 + pd.Timedelta(minutes=m) for m in minutes], "node_id": node}
    )
    if fcnt is not None:
        df["fcnt"] = list(fcnt)
    return clean_readings(df)


@pytest.fixture
def t0():
    return T0


@pytest.fixture
def make_readings():
    return build_readings
