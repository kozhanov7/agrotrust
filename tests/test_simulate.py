import pandas as pd
import pytest

from agrotrust_metrics import simulate as sim
from agrotrust_metrics.io import CAUSES, clean_events, clean_readings
from agrotrust_metrics.metrics import find_outages, packet_delivery_ratio
from agrotrust_metrics.simulate import simulate_fleet

IV = pd.Timedelta(minutes=10)


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_detected_outages_match_the_injected_truth(seed):
    """Validation against ground truth: every injected outage is found, with the right length."""
    readings, events = simulate_fleet(5, 30, IV, seed, loss_prob=0.0, jitter_s=0.0)
    truth = clean_events(events).sort_values(["node_id", "start"]).reset_index(drop=True)
    found = find_outages(clean_readings(readings), IV, min_missed=2)
    found = found.sort_values(["node_id", "start"]).reset_index(drop=True)
    assert len(truth) > 0
    assert len(found) == len(truth)
    assert (found["node_id"] == truth["node_id"]).all()
    error = (found["lost"] - (truth["end"] - truth["start"])).abs()
    assert (error <= IV).all()


def test_same_seed_gives_same_data():
    first = simulate_fleet(3, 5, seed=11)
    second = simulate_fleet(3, 5, seed=11)
    pd.testing.assert_frame_equal(first[0], second[0])
    pd.testing.assert_frame_equal(first[1], second[1])


def test_different_seed_gives_different_data():
    assert not simulate_fleet(3, 5, seed=1)[0].equals(simulate_fleet(3, 5, seed=2)[0])


def test_event_causes_are_known():
    _, events = simulate_fleet(5, 30, seed=9)
    assert set(events["cause"]) <= set(CAUSES)


def test_random_loss_is_seen_in_the_delivery_ratio():
    readings, _ = simulate_fleet(2, 30, seed=3, outage_rate=0.0, loss_prob=0.1)
    pdr = packet_delivery_ratio(clean_readings(readings))
    assert pdr.between(0.87, 0.93).all()


def test_node_side_outages_do_not_reduce_pdr(monkeypatch):
    monkeypatch.setattr(sim, "CAUSE_PROBABILITIES", {"power": 1.0})
    readings, events = simulate_fleet(3, 30, seed=7, outage_rate=1.0, loss_prob=0.0)
    assert len(events) > 0
    assert packet_delivery_ratio(clean_readings(readings)).min() == pytest.approx(1.0)


def test_link_side_outages_reduce_pdr(monkeypatch):
    monkeypatch.setattr(sim, "CAUSE_PROBABILITIES", {"radio": 1.0})
    readings, events = simulate_fleet(3, 30, seed=7, outage_rate=1.0, loss_prob=0.0)
    assert len(events) > 0
    assert packet_delivery_ratio(clean_readings(readings)).min() < 1.0


def test_short_run_can_have_no_outages():
    _, events = simulate_fleet(1, 0.05, seed=1, outage_rate=0.0)
    assert events.empty
