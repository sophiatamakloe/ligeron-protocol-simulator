"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .reporting import write_dashboard, write_json_report, write_sample_events
from .simulation import generate_scenarios, run_simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Ligeron protocol-control software simulation."
    )
    parser.add_argument("--sessions", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20261005)
    parser.add_argument("--fault-probability", type=float, default=0.08)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scenarios = generate_scenarios(
        args.sessions,
        seed=args.seed,
        fault_probability=args.fault_probability,
    )
    summary, results = run_simulation(scenarios, seed=args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json_report(summary, args.output_dir / "simulation_summary.json")
    write_sample_events(results, args.output_dir / "sample_events.jsonl")
    write_dashboard(summary, args.output_dir / "dashboard.html")
    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
    return 0 if not summary.undetected_fault_sessions and not summary.safety_violations else 1


if __name__ == "__main__":
    raise SystemExit(main())

