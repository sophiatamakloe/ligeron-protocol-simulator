"""Append-only telemetry primitives."""

from __future__ import annotations

from .models import SessionEvent


class InMemoryEventStore:
    """A minimal append-only event store used by one simulated session."""

    def __init__(self) -> None:
        self._events: list[SessionEvent] = []

    def append(self, event: SessionEvent) -> None:
        if self._events and event.sequence <= self._events[-1].sequence:
            raise ValueError("event sequence must increase monotonically")
        self._events.append(event)

    @property
    def events(self) -> tuple[SessionEvent, ...]:
        return tuple(self._events)

