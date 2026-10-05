"""Domain models for the Ligeron protocol-control simulator.

The values in :class:`ProtocolConfig` are software-simulation inputs, not
medical recommendations or validated hardware settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class Phase(str, Enum):
    CREATED = "created"
    AUTHENTICATION = "authentication"
    RLT = "rlt"
    RLT_OFF = "rlt_off"
    UVB = "uvb"
    UVB_OFF = "uvb_off"
    DELIVERY = "delivery"
    COMPLETE = "complete"
    ABORTED = "aborted"


class SessionStatus(str, Enum):
    COMPLETE = "complete"
    ABORTED = "aborted"


class EventType(str, Enum):
    SESSION_CREATED = "session_created"
    AUTHENTICATION_SUCCEEDED = "authentication_succeeded"
    AUTHENTICATION_FAILED = "authentication_failed"
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    INTERLOCK_BLOCKED = "interlock_blocked"
    FAULT_DETECTED = "fault_detected"
    EMERGENCY_STOP = "emergency_stop"
    SAFETY_VIOLATION = "safety_violation"
    SESSION_COMPLETED = "session_completed"
    SESSION_ABORTED = "session_aborted"


class FaultType(str, Enum):
    NONE = "none"
    AUTHENTICATION_FAILURE = "authentication_failure"
    RLT_SHUTDOWN_FAILURE = "rlt_shutdown_failure"
    UVB_SHUTDOWN_FAILURE = "uvb_shutdown_failure"
    DELIVERY_START_TIMEOUT = "delivery_start_timeout"
    DELIVERY_SYSTEM_FAILURE = "delivery_system_failure"
    EMERGENCY_STOP_RLT = "emergency_stop_rlt"
    EMERGENCY_STOP_UVB = "emergency_stop_uvb"
    EMERGENCY_STOP_DELIVERY = "emergency_stop_delivery"


@dataclass(frozen=True, slots=True)
class ProtocolConfig:
    """Configurable timings for software-control testing only."""

    rlt_duration_s: float = 600.0
    uvb_duration_s: float = 60.0
    delivery_duration_s: float = 30.0
    rlt_to_uvb_transition_s: float = 1.0
    uvb_to_delivery_transition_s: float = 2.0
    max_uvb_duration_s: float = 180.0
    max_delivery_start_delay_s: float = 3.0

    def __post_init__(self) -> None:
        positive = {
            "rlt_duration_s": self.rlt_duration_s,
            "uvb_duration_s": self.uvb_duration_s,
            "delivery_duration_s": self.delivery_duration_s,
            "max_uvb_duration_s": self.max_uvb_duration_s,
            "max_delivery_start_delay_s": self.max_delivery_start_delay_s,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.rlt_to_uvb_transition_s < 0 or self.uvb_to_delivery_transition_s < 0:
            raise ValueError("transition durations cannot be negative")
        if self.uvb_duration_s > self.max_uvb_duration_s:
            raise ValueError("uvb_duration_s exceeds configured software safety maximum")


@dataclass(frozen=True, slots=True)
class SessionScenario:
    session_id: str
    fault: FaultType = FaultType.NONE
    rlt_to_uvb_transition_s: float | None = None
    uvb_to_delivery_transition_s: float | None = None

    @property
    def expects_fault(self) -> bool:
        return self.fault is not FaultType.NONE


@dataclass(frozen=True, slots=True)
class SessionEvent:
    sequence: int
    session_id: str
    timestamp_s: float
    phase: Phase
    event_type: EventType
    message: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "session_id": self.session_id,
            "timestamp_s": round(self.timestamp_s, 6),
            "phase": self.phase.value,
            "event_type": self.event_type.value,
            "message": self.message,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SessionResult:
    session_id: str
    status: SessionStatus
    final_phase: Phase
    simulated_duration_s: float
    events: tuple[SessionEvent, ...]
    abort_reason: str | None
    expected_fault: bool
    fault_detected: bool
    safety_violations: int
    processing_time_ms: float = 0.0

    def with_processing_time(self, processing_time_ms: float) -> "SessionResult":
        return SessionResult(
            session_id=self.session_id,
            status=self.status,
            final_phase=self.final_phase,
            simulated_duration_s=self.simulated_duration_s,
            events=self.events,
            abort_reason=self.abort_reason,
            expected_fault=self.expected_fault,
            fault_detected=self.fault_detected,
            safety_violations=self.safety_violations,
            processing_time_ms=processing_time_ms,
        )

