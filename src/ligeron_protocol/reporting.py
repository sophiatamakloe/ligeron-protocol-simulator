"""Artifact writers for reproducible simulation results."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .models import SessionResult
from .simulation import SimulationSummary


def write_json_report(summary: SimulationSummary, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_sample_events(
    results: tuple[SessionResult, ...],
    destination: Path,
    *,
    sample_sessions: int = 5,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    selected: list[SessionResult] = []
    seen_reasons: set[str] = set()
    for result in results:
        if not selected and result.abort_reason is None:
            selected.append(result)
            continue
        if (
            result.abort_reason is not None
            and result.abort_reason not in seen_reasons
            and len(selected) < sample_sessions
        ):
            selected.append(result)
            seen_reasons.add(result.abort_reason)
        if len(selected) >= sample_sessions:
            break
    if len(selected) < sample_sessions:
        selected_ids = {result.session_id for result in selected}
        selected.extend(
            result
            for result in results
            if result.session_id not in selected_ids
        )
        selected = selected[:sample_sessions]
    with destination.open("w", encoding="utf-8") as handle:
        for result in selected:
            for event in result.events:
                handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")


def write_dashboard(summary: SimulationSummary, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = summary.to_dict()
    cards = [
        ("Synthetic sessions", f"{summary.total_sessions:,}"),
        ("Completed", f"{summary.completed_sessions:,}"),
        ("Expected faults", f"{summary.expected_fault_sessions:,}"),
        ("Faults detected", f"{summary.detected_fault_sessions:,}"),
        ("Safety violations", f"{summary.safety_violations:,}"),
        ("False aborts", f"{summary.false_aborts:,}"),
        ("p95 processing", f"{summary.processing_p95_ms:.4f} ms"),
        ("Wall time", f"{summary.wall_time_s:.4f} s"),
    ]
    card_html = "".join(
        f'<section class="card"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div></section>'
        for label, value in cards
    )
    fault_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{count:,}</td></tr>"
        for name, count in summary.fault_distribution.items()
    )
    abort_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{count:,}</td></tr>"
        for name, count in summary.abort_reasons.items()
    )
    raw_json = html.escape(json.dumps(data, indent=2, sort_keys=True))
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ligeron Protocol Simulator Results</title>
<style>
:root {{ color-scheme: dark; --bg:#08111f; --panel:#101d31; --ink:#f4f7fb; --muted:#9fb0c8; --accent:#80e6c3; --line:#263852; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font:16px/1.45 system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--ink); }}
main {{ width:min(1100px,92vw); margin:48px auto 80px; }}
h1 {{ margin:0 0 8px; font-size:clamp(2rem,5vw,3.4rem); letter-spacing:-.04em; }}
.subtitle {{ color:var(--muted); max-width:780px; margin-bottom:32px; }}
.warning {{ border:1px solid #725f23; background:#241f10; padding:16px 18px; border-radius:12px; margin:24px 0 32px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:14px; }}
.card, .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:20px; }}
.label {{ color:var(--muted); font-size:.84rem; text-transform:uppercase; letter-spacing:.08em; }}
.value {{ color:var(--accent); font-size:1.75rem; font-weight:750; margin-top:7px; }}
.panels {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-top:24px; }}
table {{ width:100%; border-collapse:collapse; }}
th,td {{ text-align:left; padding:9px 6px; border-bottom:1px solid var(--line); }}
th {{ color:var(--muted); }}
details {{ margin-top:24px; }}
pre {{ overflow:auto; background:#050a12; padding:18px; border-radius:12px; color:#cde2ff; }}
@media (max-width:760px) {{ .panels {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body><main>
<h1>Ligeron Protocol Simulator</h1>
<p class="subtitle">Seeded run {summary.seed}. Deterministic protocol logic with injected authentication, shutdown, transition, delivery, and emergency-stop faults.</p>
<div class="warning"><strong>Scope boundary:</strong> These are Python software-simulation metrics. They do not establish physical-device performance, medically safe exposure settings, biological outcomes, or production capacity.</div>
<div class="grid">{card_html}</div>
<div class="panels">
<section class="panel"><h2>Injected faults</h2><table><thead><tr><th>Fault</th><th>Sessions</th></tr></thead><tbody>{fault_rows}</tbody></table></section>
<section class="panel"><h2>Abort reasons</h2><table><thead><tr><th>Reason</th><th>Sessions</th></tr></thead><tbody>{abort_rows}</tbody></table></section>
</div>
<details><summary>Raw summary JSON</summary><pre>{raw_json}</pre></details>
</main></body></html>"""
    destination.write_text(document, encoding="utf-8")
