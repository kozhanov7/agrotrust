import runpy
import sys

import pandas as pd
import pytest

from agrotrust_metrics.cli import main
from agrotrust_metrics.io import clean_events, clean_readings
from agrotrust_metrics.metrics import attach_causes, failures_by_cause, find_outages
from agrotrust_metrics.plot import plot_causes, plot_timeline
from agrotrust_metrics.simulate import simulate_fleet


def test_simulate_summarize_plot_end_to_end(tmp_path, capsys):
    data = tmp_path / "data"
    assert (
        main(["simulate", "--nodes", "3", "--days", "10", "--seed", "3", "--out", str(data)]) == 0
    )
    readings, events = data / "readings.csv", data / "events.csv"
    assert readings.exists() and events.exists()

    table = tmp_path / "summary.csv"
    assert main(["summarize", str(readings), "--events", str(events), "--out", str(table)]) == 0
    text = capsys.readouterr().out
    assert "availability" in text and "security" in text
    assert table.exists()

    figure, causes = tmp_path / "timeline.png", tmp_path / "causes.png"
    args = ["plot", str(readings), "--events", str(events), "--out", str(figure)]
    assert main([*args, "--causes-out", str(causes)]) == 0
    assert figure.stat().st_size > 1000
    assert causes.stat().st_size > 1000


def test_plot_without_events_uses_unknown_cause(tmp_path):
    data = tmp_path / "data"
    main(["simulate", "--nodes", "2", "--days", "5", "--out", str(data)])
    figure = tmp_path / "t.png"
    assert main(["plot", str(data / "readings.csv"), "--out", str(figure)]) == 0
    assert figure.exists()


def test_missing_file_gives_exit_code_2(tmp_path, capsys):
    assert main(["summarize", str(tmp_path / "missing.csv")]) == 2
    assert "error" in capsys.readouterr().err


def test_bad_events_file_gives_exit_code_2(tmp_path, capsys):
    data = tmp_path / "data"
    main(["simulate", "--nodes", "2", "--days", "5", "--out", str(data)])
    bad = tmp_path / "bad.csv"
    bad.write_text("start,end,node_id,cause\n2026-12-01,2026-12-02,N01,gremlins\n")
    assert main(["summarize", str(data / "readings.csv"), "--events", str(bad)]) == 2
    assert "unknown failure cause" in capsys.readouterr().err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "agrometrics" in capsys.readouterr().out


def test_subcommand_is_required():
    with pytest.raises(SystemExit):
        main([])


def test_plot_functions_return_figures(tmp_path):
    readings, events = simulate_fleet(4, 20, seed=5)
    readings = clean_readings(readings)
    outages = find_outages(readings, pd.Timedelta(minutes=10))
    outages = attach_causes(outages, clean_events(events))
    path = tmp_path / "causes.png"
    plot_causes(failures_by_cause(outages), path)
    assert path.stat().st_size > 1000
    assert plot_timeline(readings, pd.Timedelta(minutes=10), outages) is not None


def test_module_entry_point(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["agrotrust_metrics", "--version"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("agrotrust_metrics", run_name="__main__")
    assert exc.value.code == 0
    assert "agrometrics" in capsys.readouterr().out
