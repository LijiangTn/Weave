"""
通用事件定义
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def _new_event_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Event:
    id: str = field(default_factory=_new_event_id)
    type: str = ''
    source: str = ''
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'type': self.type,
            'source': self.source,
            'timestamp': self.timestamp,
        }


@dataclass
class ConnectorStateEvent(Event):
    type: str = 'connector.state_changed'
    state: str = ''
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({'state': self.state, 'detail': self.detail})
        return base


@dataclass
class MessageReceivedEvent(Event):
    type: str = 'message.received'
    message_id: str = ''

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({'message_id': self.message_id})
        return base


@dataclass
class MessageDuplicateEvent(Event):
    type: str = 'message.duplicate'
    message_id: str = ''
    source_message_id: str = ''

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {'message_id': self.message_id, 'source_message_id': self.source_message_id}
        )
        return base
