"""Slow terminal visualization of two Ligeron software-simulation sessions."""

from __future__ import annotations

import time

from ligeron_protocol.controller import ProtocolController
from ligeron_protocol.models import EventType, FaultType, Phase, SessionEvent, SessionScenario


def actuator_display(event: SessionEvent) -> str:
    if event.event_type in {
        EventType.SESSION_CREATED,
        EventType.AUTHENTICATION_SUCCEEDED,
        EventType.AUTHENTICATION_FAILED,
        EventType.SESSION_COMPLETED,
        EventType.SESSION_ABORTED,
    }:
        return "RLT=OFF  UVB=OFF  DELIVERY=OFF"
    if event.event_type is EventType.PHASE_COMPLETED:
        return "RLT=OFF  UVB=OFF  DELIVERY=OFF"
    states = {
        Phase.RLT: "RLT=ON   UVB=OFF  DELIVERY=OFF",
        Phase.UVB: "RLT=OFF  UVB=ON   DELIVERY=OFF",
        Phase.DELIVERY: "RLT=OFF  UVB=OFF  DELIVERY=ON",
    }
    return states.get(event.phase, "RLT=OFF  UVB=OFF  DELIVERY=OFF")


def show_session(title: str, scenario: SessionScenario) -> None:
    result = ProtocolController().run(scenario)
    print(f"\n{'=' * 76}\n{title}\n{'=' * 76}", flush=True)
    time.sleep(0.7)
    for event in result.events:
        print(
            f"T+{event.timestamp_s:07.3f}s | {event.event_type.value:<26} "
            f"| {actuator_display(event)}",
            flush=True,
        )
        print(f"              {event.message}", flush=True)
        time.sleep(0.65)
    print(
        f"\nRESULT: {result.status.value.upper()} | "
        f"reason={result.abort_reason or 'none'} | "
        f"safety_violations={result.safety_violations}",
        flush=True,
    )
    time.sleep(1.0)


if __name__ == "__main__":
    print("LIGERON PROTOCOL — LIVE SOFTWARE MODEL", flush=True)
    print("Compressed playback; timestamps are simulated protocol time.", flush=True)
    show_session(
        "SESSION A — NOMINAL SEQUENCE",
        SessionScenario(session_id="live-nominal"),
    )
    show_session(
        "SESSION B — UVB SHUTDOWN CONFIRMATION FAILURE",
        SessionScenario(
            session_id="live-uvb-interlock",
            fault=FaultType.UVB_SHUTDOWN_FAILURE,
        ),
    )
