"""realtime.model — события для открытых вкладок."""

from app.realtime.model.event import (
    CLOSE_FORBIDDEN,
    CLOSE_GOING_AWAY,
    CLOSE_MESSAGE_TOO_BIG,
    CLOSE_NOT_AUTHENTICATED,
    MAX_CONNECTIONS_PER_USER,
    MAX_INCOMING_BYTES,
    PING,
    PONG_MESSAGE,
    REVERIFY_INTERVAL_S,
    WIRE_VERSION,
    Audience,
    ContestEvent,
    EventType,
    PlannedEvent,
)

__all__ = [
    "CLOSE_FORBIDDEN",
    "CLOSE_GOING_AWAY",
    "CLOSE_MESSAGE_TOO_BIG",
    "CLOSE_NOT_AUTHENTICATED",
    "MAX_CONNECTIONS_PER_USER",
    "MAX_INCOMING_BYTES",
    "PING",
    "PONG_MESSAGE",
    "REVERIFY_INTERVAL_S",
    "WIRE_VERSION",
    "Audience",
    "ContestEvent",
    "EventType",
    "PlannedEvent",
]
