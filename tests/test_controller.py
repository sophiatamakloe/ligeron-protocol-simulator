from __future__ import annotations

import pytest

from ligeron_protocol import (
    EventType,
    FaultType,
    Phase,
    ProtocolConfig,
    ProtocolController,
    SessionScenario,
    SessionStatus,
)


def run(fault: FaultType = FaultType.NONE):
    return ProtocolController().run(SessionScenario("test-session", fault=fault))


def test_normal_session_completes_with_safe_shutdown() -> None:
    result = run()
    assert result.status is SessionStatus.COMPLETE
    assert result.final_phase is Phase.COMPLETE
    assert result.abort_reason is None
    assert result.safety_violations == 0
    final = result.events[-1]
    assert final.event_type is EventType.SESSION_COMPLETED
    assert not final.metadata["rlt_on"]
    assert not final.metadata["uvb_on"]
    assert not final.metadata["delivery_on"]


@pytest.mark.parametrize(
    "fault,reason",
    [
        (FaultType.AUTHENTICATION_FAILURE, "authentication_failed"),
        (FaultType.RLT_SHUTDOWN_FAILURE, "rlt_shutdown_failure"),
        (FaultType.UVB_SHUTDOWN_FAILURE, "uvb_shutdown_failure"),
        (FaultType.DELIVERY_START_TIMEOUT, "delivery_start_timeout"),
        (FaultType.DELIVERY_SYSTEM_FAILURE, "delivery_system_failure"),
        (FaultType.EMERGENCY_STOP_RLT, "emergency_stop_during_rlt"),
        (FaultType.EMERGENCY_STOP_UVB, "emergency_stop_during_uvb"),
        (FaultType.EMERGENCY_STOP_DELIVERY, "emergency_stop_during_delivery"),
    ],
)
def test_injected_faults_abort_safely(fault: FaultType, reason: str) -> None:
    result = run(fault)
    assert result.status is SessionStatus.ABORTED
    assert result.abort_reason == reason
    assert result.fault_detected
    final = result.events[-1]
    assert final.event_type is EventType.SESSION_ABORTED
    assert not final.metadata["rlt_on"]
    assert not final.metadata["uvb_on"]
    assert not final.metadata["delivery_on"]


def test_rlt_shutdown_failure_never_starts_uvb() -> None:
    result = run(FaultType.RLT_SHUTDOWN_FAILURE)
    messages = [event.message for event in result.events]
    assert "UVB phase started." not in messages
    assert any(event.event_type is EventType.INTERLOCK_BLOCKED for event in result.events)


def test_uvb_shutdown_failure_never_starts_delivery() -> None:
    result = run(FaultType.UVB_SHUTDOWN_FAILURE)
    messages = [event.message for event in result.events]
    assert "Post-exposure delivery phase started." not in messages


def test_delivery_deadline_is_enforced() -> None:
    config = ProtocolConfig(max_delivery_start_delay_s=3.0)
    result = ProtocolController(config).run(
        SessionScenario("late-delivery", uvb_to_delivery_transition_s=3.001)
    )
    assert result.status is SessionStatus.ABORTED
    assert result.abort_reason == "delivery_start_timeout"


def test_event_sequence_and_time_are_monotonic() -> None:
    result = run()
    sequences = [event.sequence for event in result.events]
    times = [event.timestamp_s for event in result.events]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))
    assert times == sorted(times)


def test_no_event_snapshot_has_mutually_exclusive_outputs_active() -> None:
    result = run()
    for event in result.events:
        assert not (event.metadata["rlt_on"] and event.metadata["uvb_on"])
        assert not (event.metadata["uvb_on"] and event.metadata["delivery_on"])


def assert_invariant_guard_aborts_safely(
    controller: ProtocolController, expected_violation: str
) -> None:
    assert controller._enforce_invariants("forced-illegal-state") is False
    assert controller.phase is Phase.ABORTED
    assert controller._abort_reason == "safety_invariant_violation"
    assert not controller.actuators.rlt_on
    assert not controller.actuators.uvb_on
    assert not controller.actuators.delivery_on

    violations = [
        event.metadata["violation"]
        for event in controller.store.events
        if event.event_type is EventType.SAFETY_VIOLATION
    ]
    assert expected_violation in violations
    final = controller.store.events[-1]
    assert final.event_type is EventType.SESSION_ABORTED
    assert not final.metadata["rlt_on"]
    assert not final.metadata["uvb_on"]
    assert not final.metadata["delivery_on"]


def test_guard_catches_forced_rlt_uvb_overlap() -> None:
    controller = ProtocolController()
    controller.phase = Phase.RLT
    controller.actuators.rlt_on = True
    controller.actuators.uvb_on = True

    assert_invariant_guard_aborts_safely(
        controller, "rlt_uvb_mutual_exclusion"
    )


def test_guard_catches_forced_uvb_delivery_overlap() -> None:
    controller = ProtocolController()
    controller.phase = Phase.UVB_OFF
    controller.actuators.uvb_on = True
    controller.actuators.delivery_on = True

    assert_invariant_guard_aborts_safely(
        controller, "uvb_delivery_mutual_exclusion"
    )


def test_guard_catches_delivery_phase_before_uvb_is_off() -> None:
    controller = ProtocolController()
    controller.phase = Phase.DELIVERY
    controller.actuators.uvb_on = True

    assert_invariant_guard_aborts_safely(
        controller, "delivery_started_before_uvb_off"
    )


def test_invalid_configurations_are_rejected() -> None:
    with pytest.raises(ValueError):
        ProtocolConfig(uvb_duration_s=181.0)
    with pytest.raises(ValueError):
        ProtocolConfig(rlt_duration_s=0)
    with pytest.raises(ValueError):
        ProtocolConfig(uvb_to_delivery_transition_s=-1)


def test_events_are_exposed_as_immutable_tuple() -> None:
    result = run()
    assert isinstance(result.events, tuple)
    with pytest.raises(TypeError):
        result.events[0].metadata["rlt_on"] = False
