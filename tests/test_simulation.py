from __future__ import annotations

import json

import pytest

from ligeron_protocol import generate_scenarios, run_simulation
from ligeron_protocol.reporting import write_dashboard, write_json_report, write_sample_events
from ligeron_protocol.cli import main


def test_scenario_generation_is_seeded() -> None:
    first = generate_scenarios(250, seed=42)
    second = generate_scenarios(250, seed=42)
    assert first == second


def test_fault_probability_validation() -> None:
    with pytest.raises(ValueError):
        generate_scenarios(0)
    with pytest.raises(ValueError):
        generate_scenarios(10, fault_probability=1.1)


def test_seeded_simulation_detects_all_injected_faults() -> None:
    scenarios = generate_scenarios(1_000, seed=7, fault_probability=0.2)
    summary, _ = run_simulation(scenarios, seed=7)
    assert summary.total_sessions == 1_000
    assert summary.detected_fault_sessions == summary.expected_fault_sessions
    assert summary.undetected_fault_sessions == 0
    assert summary.false_aborts == 0
    assert summary.safety_violations == 0


def test_all_normal_sessions_complete() -> None:
    scenarios = generate_scenarios(100, seed=1, fault_probability=0.0)
    summary, _ = run_simulation(scenarios, seed=1)
    assert summary.completed_sessions == 100
    assert summary.aborted_sessions == 0


def test_report_artifacts_are_written(tmp_path) -> None:
    scenarios = generate_scenarios(25, seed=9, fault_probability=0.2)
    summary, results = run_simulation(scenarios, seed=9)
    json_path = tmp_path / "summary.json"
    event_path = tmp_path / "events.jsonl"
    dashboard_path = tmp_path / "dashboard.html"

    write_json_report(summary, json_path)
    write_sample_events(results, event_path, sample_sessions=3)
    write_dashboard(summary, dashboard_path)

    payload = json.loads(json_path.read_text())
    assert payload["total_sessions"] == 25
    assert "software simulation only" in payload["scope_note"]
    assert event_path.read_text().strip()
    dashboard = dashboard_path.read_text()
    assert "Ligeron Protocol Simulator" in dashboard
    assert "do not establish physical-device performance" in dashboard


def test_cli_generates_complete_artifact_set(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "--sessions",
            "50",
            "--seed",
            "11",
            "--fault-probability",
            "0.25",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    assert (tmp_path / "simulation_summary.json").is_file()
    assert (tmp_path / "sample_events.jsonl").is_file()
    assert (tmp_path / "dashboard.html").is_file()
    stdout = capsys.readouterr().out
    assert '"total_sessions": 50' in stdout
