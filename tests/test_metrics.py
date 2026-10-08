import math

import pandas as pd
import pytest

from agrotrust_metrics.io import clean_events, clean_readings
from agrotrust_metrics.metrics import (
    attach_causes,
    data_completeness,
    detect_gaps,
    failures_by_cause,
    find_outages,
    observation_window,
    outages_from_gaps,
    overall,
    packet_delivery_ratio,
    summarize,
)
from agrotrust_metrics.simulate import simulate_fleet

IV = pd.Timedelta(minutes=10)


def minutes(n):
    return pd.Timedelta(minutes=n)


# ---- gaps and outages -----------------------------------------------------------------


def test_detect_gaps_finds_one_gap(make_readings):
    gaps = detect_gaps(make_readings([0, 10, 20, 80, 90]), IV)
    assert len(gaps) == 1
    gap = gaps.iloc[0]
    assert gap["missed"] == 5
    assert gap["duration"] == minutes(60)
    assert gap["lost"] == minutes(50)


def test_small_timing_noise_is_not_a_gap(make_readings):
    assert detect_gaps(make_readings([0, 10, 21, 29, 40]), IV).empty


def test_one_missed_reading_is_a_gap_but_not_an_outage(make_readings):
    gaps = detect_gaps(make_readings([0, 10, 30, 40]), IV)
    assert gaps["missed"].tolist() == [1]
    assert outages_from_gaps(gaps, min_missed=3).empty


def test_boundary_gaps_need_an_explicit_window(make_readings, t0):
    readings = make_readings([30, 40, 50])
    assert detect_gaps(readings, IV).empty
    gaps = detect_gaps(readings, IV, start=t0, end=t0 + minutes(100))
    assert gaps["missed"].tolist() == [3, 4]


@pytest.mark.parametrize("tolerance", [1.0, 0.5])
def test_tolerance_must_exceed_one(make_readings, tolerance):
    with pytest.raises(ValueError, match="tolerance"):
        detect_gaps(make_readings([0, 10]), IV, tolerance=tolerance)


def test_interval_must_be_positive(make_readings):
    with pytest.raises(ValueError, match="interval"):
        detect_gaps(make_readings([0, 10]), pd.Timedelta(0))


def test_observation_window_defaults_and_errors(make_readings, t0):
    readings = make_readings([0, 10, 20])
    assert observation_window(readings, IV) == (t0, t0 + minutes(30))
    with pytest.raises(ValueError, match="positive length"):
        observation_window(readings, IV, start=t0 + minutes(50), end=t0 + minutes(40))
    with pytest.raises(ValueError, match="no readings"):
        observation_window(readings.iloc[0:0], IV)


# ---- completeness and delivery ratio --------------------------------------------------


def test_completeness_counts_filled_slots(make_readings, t0):
    readings = make_readings(range(0, 80, 10))  # 8 of 10 slots
    result = data_completeness(readings, IV, t0, t0 + minutes(100))
    assert result["A"] == pytest.approx(0.8)


def test_completeness_counts_a_slot_once(make_readings, t0):
    readings = make_readings([0, 1, 2, 10])
    assert data_completeness(readings, IV, t0, t0 + minutes(20))["A"] == pytest.approx(1.0)


def test_completeness_is_robust_to_jitter(make_readings):
    # first reading arrives late, later ones early: flooring to slots would lose a slot
    readings = make_readings([0.5, 10.1, 20.4, 29.9, 40.2])
    start = readings["timestamp"].min()
    assert data_completeness(readings, IV, start, start + minutes(50))["A"] == pytest.approx(1.0)


def test_completeness_on_simulated_data_matches_losses():
    readings, _ = simulate_fleet(3, 20, seed=4, outage_rate=0.0, loss_prob=0.05)
    table = summarize(clean_readings(readings), IV)
    assert table["completeness"].between(0.93, 0.97).all()


def test_pdr_from_frame_counter(make_readings):
    readings = make_readings([0, 10, 20, 30], fcnt=[1, 2, 4, 5])
    assert packet_delivery_ratio(readings)["A"] == pytest.approx(0.8)


def test_pdr_counter_reset_starts_a_new_segment(make_readings):
    readings = make_readings([0, 10, 20, 30, 40], fcnt=[1, 2, 3, 1, 2])
    assert packet_delivery_ratio(readings)["A"] == pytest.approx(1.0)


def test_pdr_needs_the_counter(make_readings):
    with pytest.raises(ValueError, match="fcnt"):
        packet_delivery_ratio(make_readings([0, 10]))


# ---- summary --------------------------------------------------------------------------


def test_summarize_known_outage(make_readings, t0):
    readings = make_readings([0, 10, 20, 80, 90], fcnt=[0, 1, 2, 3, 4])
    row = summarize(readings, IV, end=t0 + minutes(100)).loc["A"]
    assert row["outages"] == 1
    assert row["downtime_h"] == pytest.approx(50 / 60)
    assert row["availability"] == pytest.approx(0.5)
    assert row["mtbf_h"] == pytest.approx(50 / 60)
    assert row["mttr_h"] == pytest.approx(50 / 60)
    assert row["completeness"] == pytest.approx(0.5)
    assert row["pdr"] == pytest.approx(1.0)


def test_summarize_without_outages(make_readings, t0):
    row = summarize(make_readings(range(0, 100, 10)), IV, end=t0 + minutes(100)).loc["A"]
    assert row["availability"] == pytest.approx(1.0)
    assert math.isinf(row["mtbf_h"])
    assert math.isnan(row["mttr_h"])
    assert math.isnan(row["pdr"])  # no frame counter in the data


def test_short_gap_does_not_reduce_availability(make_readings, t0):
    readings = make_readings([0, 10, 30, 40, 50, 60, 70, 80, 90])
    row = summarize(readings, IV, end=t0 + minutes(100)).loc["A"]
    assert row["outages"] == 0
    assert row["availability"] == pytest.approx(1.0)


def test_overall_pools_nodes(make_readings, t0):
    both = pd.concat(
        [make_readings([0, 10, 20, 80, 90]), make_readings(range(0, 100, 10), node="B")],
        ignore_index=True,
    )
    fleet = overall(summarize(both, IV, end=t0 + minutes(100)))
    assert fleet["nodes"] == 2
    assert fleet["availability"] == pytest.approx(0.75)
    assert fleet["outages"] == 1
    assert fleet["mtbf_h"] == pytest.approx(2.5)
    assert fleet["worst_node"] == "A"


# ---- causes ---------------------------------------------------------------------------


def _events(node, start, end, cause):
    return clean_events(
        pd.DataFrame({"start": [start], "end": [end], "node_id": [node], "cause": [cause]})
    )


def test_attach_causes_uses_the_overlapping_event(make_readings, t0):
    outages = find_outages(make_readings([0, 10, 20, 80, 90]), IV, end=t0 + minutes(100))
    events = _events("A", t0 + minutes(30), t0 + minutes(70), "Power")
    assert attach_causes(outages, events)["cause"].tolist() == ["power"]


def test_outage_without_event_is_unknown(make_readings, t0):
    outages = find_outages(make_readings([0, 10, 20, 80, 90]), IV, end=t0 + minutes(100))
    events = _events("B", t0 + minutes(30), t0 + minutes(70), "radio")
    assert attach_causes(outages, events)["cause"].tolist() == ["unknown"]


def test_failures_by_cause_shares():
    outages = pd.DataFrame(
        {
            "node_id": ["A", "B"],
            "cause": ["security", "radio"],
            "lost": [pd.Timedelta(hours=1), pd.Timedelta(hours=3)],
        }
    )
    table = failures_by_cause(outages)
    assert table.loc["security", "share"] == pytest.approx(0.25)
    assert table.loc["radio", "downtime_h"] == pytest.approx(3.0)
    assert table["share"].sum() == pytest.approx(1.0)
    assert table.loc["hardware", "count"] == 0


def test_failures_by_cause_needs_labels():
    with pytest.raises(ValueError, match="cause"):
        failures_by_cause(pd.DataFrame({"node_id": ["A"]}))
