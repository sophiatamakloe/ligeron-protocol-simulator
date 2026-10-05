"""Seeded scenario generation and simulation metrics."""

from __future__ import annotations

import math
import random
import statistics
import time
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Iterable

from .controller import ProtocolController
from .models import FaultType, ProtocolConfig, SessionResult, SessionScenario, SessionStatus


FAULTS = tuple(fault for fault in FaultType if fault is not FaultType.NONE)


@dataclass(frozen=True, slots=True)
class SimulationSummary:
    seed: int
    total_sessions: int
    completed_sessions: int
    aborted_sessions: int
    expected_fault_sessions: int
    detected_fault_sessions: int
    undetected_fault_sessions: int
    false_aborts: int
    safety_violations: int
    total_events: int
    wall_time_s: float
    sessions_per_second: float
    events_per_second: float
    processing_p50_ms: float
    processing_p95_ms: float
    processing_p99_ms: float
    fault_distribution: dict[str, int]
    abort_reasons: dict[str, int]

    @property
    def fault_detection_rate(self) -> float:
        if not self.expected_fault_sessions:
            return 1.0
        return self.detected_fault_sessions / self.expected_fault_sessions

    @property
    def completion_rate(self) -> float:
        if not self.total_sessions:
            return 0.0
        return self.completed_sessions / self.total_sessions

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["fault_detection_rate"] = self.fault_detection_rate
        payload["completion_rate"] = self.completion_rate
        payload["scope_note"] = (
            "Metrics describe deterministic Python software simulation only; "
            "they do not measure physical hardware, clinical outcomes, or production capacity."
        )
        return payload


def generate_scenarios(
    total_sessions: int,
    *,
    seed: int = 20261005,
    fault_probability: float = 0.08,
) -> list[SessionScenario]:
    if total_sessions <= 0:
        raise ValueError("total_sessions must be positive")
    if not 0.0 <= fault_probability <= 1.0:
        raise ValueError("fault_probability must be between 0 and 1")
    rng = random.Random(seed)
    scenarios: list[SessionScenario] = []
    for index in range(total_sessions):
        fault = FaultType.NONE
        if rng.random() < fault_probability:
            fault = rng.choice(FAULTS)
        scenarios.append(
            SessionScenario(
                session_id=f"session-{index + 1:06d}",
                fault=fault,
            )
        )
    return scenarios


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[rank]


def run_simulation(
    scenarios: Iterable[SessionScenario],
    *,
    config: ProtocolConfig | None = None,
    seed: int = 20261005,
) -> tuple[SimulationSummary, tuple[SessionResult, ...]]:
    scenario_list = list(scenarios)
    if not scenario_list:
        raise ValueError("at least one scenario is required")

    results: list[SessionResult] = []
    started = time.perf_counter()
    for scenario in scenario_list:
        controller = ProtocolController(config)
        session_started = time.perf_counter_ns()
        result = controller.run(scenario)
        elapsed_ms = (time.perf_counter_ns() - session_started) / 1_000_000
        results.append(result.with_processing_time(elapsed_ms))
    wall_time_s = time.perf_counter() - started

    processing_times = [result.processing_time_ms for result in results]
    expected_faults = [result for result in results if result.expected_fault]
    detected_faults = [result for result in expected_faults if result.fault_detected]
    false_aborts = sum(
        result.status is SessionStatus.ABORTED and not result.expected_fault
        for result in results
    )
    fault_distribution = Counter(
        scenario.fault.value for scenario in scenario_list if scenario.expects_fault
    )
    abort_reasons = Counter(
        result.abort_reason for result in results if result.abort_reason is not None
    )
    total_events = sum(len(result.events) for result in results)

    summary = SimulationSummary(
        seed=seed,
        total_sessions=len(results),
        completed_sessions=sum(
            result.status is SessionStatus.COMPLETE for result in results
        ),
        aborted_sessions=sum(
            result.status is SessionStatus.ABORTED for result in results
        ),
        expected_fault_sessions=len(expected_faults),
        detected_fault_sessions=len(detected_faults),
        undetected_fault_sessions=len(expected_faults) - len(detected_faults),
        false_aborts=false_aborts,
        safety_violations=sum(result.safety_violations for result in results),
        total_events=total_events,
        wall_time_s=wall_time_s,
        sessions_per_second=len(results) / wall_time_s if wall_time_s else 0.0,
        events_per_second=total_events / wall_time_s if wall_time_s else 0.0,
        processing_p50_ms=statistics.median(processing_times),
        processing_p95_ms=_percentile(processing_times, 0.95),
        processing_p99_ms=_percentile(processing_times, 0.99),
        fault_distribution=dict(sorted(fault_distribution.items())),
        abort_reasons=dict(sorted(abort_reasons.items())),
    )
    return summary, tuple(results)

