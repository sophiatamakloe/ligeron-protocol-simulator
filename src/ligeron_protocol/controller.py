"""Deterministic protocol controller and safety interlocks."""

from __future__ import annotations

from dataclasses import dataclass

from .models import (
    EventType,
    FaultType,
    Phase,
    ProtocolConfig,
    SessionEvent,
    SessionResult,
    SessionScenario,
    SessionStatus,
)
from .telemetry import InMemoryEventStore


@dataclass(slots=True)
class _ActuatorState:
    rlt_on: bool = False
    uvb_on: bool = False
    delivery_on: bool = False

    def safe_shutdown(self) -> None:
        self.rlt_on = False
        self.uvb_on = False
        self.delivery_on = False

    def snapshot(self) -> dict[str, bool]:
        return {
            "rlt_on": self.rlt_on,
            "uvb_on": self.uvb_on,
            "delivery_on": self.delivery_on,
        }


class ProtocolController:
    """Runs one synthetic session through real protocol-control logic.

    The controller advances a simulated clock; it never energizes hardware and
    does not model biological effects.
    """

    def __init__(self, config: ProtocolConfig | None = None) -> None:
        self.config = config or ProtocolConfig()
        self.phase = Phase.CREATED
        self.clock_s = 0.0
        self.actuators = _ActuatorState()
        self.store = InMemoryEventStore()
        self._sequence = 0
        self._abort_reason: str | None = None

    def run(self, scenario: SessionScenario) -> SessionResult:
        self._reset()
        self._record(
            scenario.session_id,
            EventType.SESSION_CREATED,
            "Session created using software-simulation configuration.",
        )

        self.phase = Phase.AUTHENTICATION
        if scenario.fault is FaultType.AUTHENTICATION_FAILURE:
            self._record(
                scenario.session_id,
                EventType.AUTHENTICATION_FAILED,
                "Authentication failed; activation blocked.",
            )
            self._abort(scenario.session_id, "authentication_failed")
            return self._result(scenario)

        self._record(
            scenario.session_id,
            EventType.AUTHENTICATION_SUCCEEDED,
            "Authentication succeeded.",
        )

        self._start_rlt(scenario.session_id)
        if scenario.fault is FaultType.EMERGENCY_STOP_RLT:
            self._emergency_stop(scenario.session_id, "emergency_stop_during_rlt")
            return self._result(scenario)
        self._advance(self.config.rlt_duration_s)
        if not self._stop_rlt(
            scenario.session_id,
            shutdown_ok=scenario.fault is not FaultType.RLT_SHUTDOWN_FAILURE,
        ):
            return self._result(scenario)

        self._advance(
            self.config.rlt_to_uvb_transition_s
            if scenario.rlt_to_uvb_transition_s is None
            else scenario.rlt_to_uvb_transition_s
        )
        if not self._start_uvb(scenario.session_id):
            return self._result(scenario)
        if scenario.fault is FaultType.EMERGENCY_STOP_UVB:
            self._emergency_stop(scenario.session_id, "emergency_stop_during_uvb")
            return self._result(scenario)
        self._advance(self.config.uvb_duration_s)
        if not self._stop_uvb(
            scenario.session_id,
            shutdown_ok=scenario.fault is not FaultType.UVB_SHUTDOWN_FAILURE,
        ):
            return self._result(scenario)

        delivery_delay = (
            self.config.uvb_to_delivery_transition_s
            if scenario.uvb_to_delivery_transition_s is None
            else scenario.uvb_to_delivery_transition_s
        )
        if scenario.fault is FaultType.DELIVERY_START_TIMEOUT:
            delivery_delay = max(
                delivery_delay,
                self.config.max_delivery_start_delay_s + 0.001,
            )
        self._advance(delivery_delay)
        if not self._start_delivery(scenario.session_id, delivery_delay):
            return self._result(scenario)
        if scenario.fault is FaultType.EMERGENCY_STOP_DELIVERY:
            self._emergency_stop(scenario.session_id, "emergency_stop_during_delivery")
            return self._result(scenario)
        if scenario.fault is FaultType.DELIVERY_SYSTEM_FAILURE:
            self._record(
                scenario.session_id,
                EventType.FAULT_DETECTED,
                "Delivery subsystem fault detected.",
            )
            self._abort(scenario.session_id, "delivery_system_failure")
            return self._result(scenario)

        self._advance(self.config.delivery_duration_s)
        self.actuators.delivery_on = False
        self._record(
            scenario.session_id,
            EventType.PHASE_COMPLETED,
            "Delivery phase completed.",
        )
        self.phase = Phase.COMPLETE
        self._record(
            scenario.session_id,
            EventType.SESSION_COMPLETED,
            "Session completed with all actuators off.",
        )
        return self._result(scenario)

    def _reset(self) -> None:
        self.phase = Phase.CREATED
        self.clock_s = 0.0
        self.actuators = _ActuatorState()
        self.store = InMemoryEventStore()
        self._sequence = 0
        self._abort_reason = None

    def _advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("simulated time cannot move backward")
        self.clock_s += seconds

    def _start_rlt(self, session_id: str) -> None:
        self.phase = Phase.RLT
        self.actuators.rlt_on = True
        self._record(session_id, EventType.PHASE_STARTED, "RLT phase started.")
        self._enforce_invariants(session_id)

    def _stop_rlt(self, session_id: str, *, shutdown_ok: bool) -> bool:
        if shutdown_ok:
            self.actuators.rlt_on = False
            self.phase = Phase.RLT_OFF
            self._record(session_id, EventType.PHASE_COMPLETED, "RLT confirmed off.")
            return True
        self._record(
            session_id,
            EventType.FAULT_DETECTED,
            "RLT shutdown confirmation failed.",
        )
        self._record(
            session_id,
            EventType.INTERLOCK_BLOCKED,
            "UVB start blocked because RLT remained active.",
        )
        self._abort(session_id, "rlt_shutdown_failure")
        return False

    def _start_uvb(self, session_id: str) -> bool:
        if self.phase is not Phase.RLT_OFF or self.actuators.rlt_on:
            self._record(
                session_id,
                EventType.INTERLOCK_BLOCKED,
                "UVB start blocked by RLT/UVB mutual-exclusion interlock.",
            )
            self._abort(session_id, "uvb_start_interlock")
            return False
        self.phase = Phase.UVB
        self.actuators.uvb_on = True
        self._record(session_id, EventType.PHASE_STARTED, "UVB phase started.")
        return self._enforce_invariants(session_id)

    def _stop_uvb(self, session_id: str, *, shutdown_ok: bool) -> bool:
        if shutdown_ok:
            self.actuators.uvb_on = False
            self.phase = Phase.UVB_OFF
            self._record(session_id, EventType.PHASE_COMPLETED, "UVB confirmed off.")
            return True
        self._record(
            session_id,
            EventType.FAULT_DETECTED,
            "UVB shutdown confirmation failed.",
        )
        self._record(
            session_id,
            EventType.INTERLOCK_BLOCKED,
            "Delivery start blocked because UVB remained active.",
        )
        self._abort(session_id, "uvb_shutdown_failure")
        return False

    def _start_delivery(self, session_id: str, delay_s: float) -> bool:
        if delay_s > self.config.max_delivery_start_delay_s:
            self._record(
                session_id,
                EventType.FAULT_DETECTED,
                "Delivery start exceeded configured transition deadline.",
                {"delay_s": delay_s},
            )
            self._abort(session_id, "delivery_start_timeout")
            return False
        if self.phase is not Phase.UVB_OFF or self.actuators.uvb_on:
            self._record(
                session_id,
                EventType.INTERLOCK_BLOCKED,
                "Delivery start blocked because UVB-off confirmation was absent.",
            )
            self._abort(session_id, "delivery_start_interlock")
            return False
        self.phase = Phase.DELIVERY
        self.actuators.delivery_on = True
        self._record(
            session_id,
            EventType.PHASE_STARTED,
            "Post-exposure delivery phase started.",
            {"transition_delay_s": delay_s},
        )
        return self._enforce_invariants(session_id)

    def _emergency_stop(self, session_id: str, reason: str) -> None:
        self._record(session_id, EventType.EMERGENCY_STOP, "Emergency stop requested.")
        self._abort(session_id, reason)

    def _enforce_invariants(self, session_id: str) -> bool:
        violations: list[str] = []
        if self.actuators.rlt_on and self.actuators.uvb_on:
            violations.append("rlt_uvb_mutual_exclusion")
        if self.actuators.delivery_on and self.actuators.uvb_on:
            violations.append("uvb_delivery_mutual_exclusion")
        if self.phase is Phase.UVB and self.actuators.rlt_on:
            violations.append("uvb_started_before_rlt_off")
        if self.phase is Phase.DELIVERY and self.actuators.uvb_on:
            violations.append("delivery_started_before_uvb_off")
        if not violations:
            return True
        for violation in violations:
            self._record(
                session_id,
                EventType.SAFETY_VIOLATION,
                f"Safety invariant violated: {violation}.",
                {"violation": violation},
            )
        self._abort(session_id, "safety_invariant_violation")
        return False

    def _abort(self, session_id: str, reason: str) -> None:
        self.actuators.safe_shutdown()
        self.phase = Phase.ABORTED
        self._abort_reason = reason
        self._record(
            session_id,
            EventType.SESSION_ABORTED,
            f"Session aborted: {reason}.",
            {"reason": reason},
        )

    def _record(
        self,
        session_id: str,
        event_type: EventType,
        message: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._sequence += 1
        merged_metadata = {
            **self.actuators.snapshot(),
            **(metadata or {}),
        }
        self.store.append(
            SessionEvent(
                sequence=self._sequence,
                session_id=session_id,
                timestamp_s=self.clock_s,
                phase=self.phase,
                event_type=event_type,
                message=message,
                metadata=merged_metadata,
            )
        )

    def _result(self, scenario: SessionScenario) -> SessionResult:
        events = self.store.events
        status = (
            SessionStatus.COMPLETE
            if self.phase is Phase.COMPLETE
            else SessionStatus.ABORTED
        )
        safety_violations = sum(
            event.event_type is EventType.SAFETY_VIOLATION for event in events
        )
        fault_detected = (
            scenario.expects_fault
            and status is SessionStatus.ABORTED
            and any(
                event.event_type
                in {
                    EventType.AUTHENTICATION_FAILED,
                    EventType.FAULT_DETECTED,
                    EventType.INTERLOCK_BLOCKED,
                    EventType.EMERGENCY_STOP,
                }
                for event in events
            )
        )
        return SessionResult(
            session_id=scenario.session_id,
            status=status,
            final_phase=self.phase,
            simulated_duration_s=self.clock_s,
            events=events,
            abort_reason=self._abort_reason,
            expected_fault=scenario.expects_fault,
            fault_detected=fault_detected,
            safety_violations=safety_violations,
        )

