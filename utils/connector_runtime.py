"""
通用连接器抽象
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from utils.log_util import logger


class ConnectorState(str, Enum):
    STOPPED = 'stopped'
    STARTING = 'starting'
    WAITING_QR = 'waiting_qr'
    QR_READY = 'qr_ready'
    LOGGING_IN = 'logging_in'
    CONNECTED = 'connected'
    RECONNECTING = 'reconnecting'
    DISCONNECTED = 'disconnected'
    ERROR = 'ERROR'


@dataclass
class ConnectorRuntimeStatus:
    source: str
    state: str
    is_logged_in: bool = False
    last_error: str | None = None
    reconnect_attempts: int = 0
    last_heartbeat: float = 0.0
    last_message_at: float = 0.0
    extra: dict[str, str] = field(default_factory=dict)


class BaseConnector(ABC):
    source: str = ''

    def __init__(self) -> None:
        self._state = ConnectorState.STOPPED
        self._last_error: str | None = None
        self._reconnect_attempts = 0
        self._last_heartbeat = 0.0
        self._last_message_at = 0.0
        self._is_logged_in = False

    @property
    def state(self) -> ConnectorState:
        return self._state

    @property
    def is_logged_in(self) -> bool:
        return self._is_logged_in

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def reconnect_attempts(self) -> int:
        return self._reconnect_attempts

    @abstractmethod
    async def start(self) -> None:
        """初始化连接器。"""

    @abstractmethod
    async def stop(self) -> None:
        """停止连接器。"""

    def get_status(self) -> ConnectorRuntimeStatus:
        return ConnectorRuntimeStatus(
            source=self.source,
            state=self._state.value,
            is_logged_in=self._is_logged_in,
            last_error=self._last_error,
            reconnect_attempts=self._reconnect_attempts,
            last_heartbeat=self._last_heartbeat,
            last_message_at=self._last_message_at,
        )

    def _set_state(self, state: ConnectorState) -> None:
        if state != self._state:
            logger.info(f'[{self.source}] state: {self._state.value} -> {state.value}')
            self._state = state

    def _record_error(self, err: str) -> None:
        self._last_error = err
        logger.warning(f'[{self.source}] error: {err}')

    def _touch_heartbeat(self) -> None:
        self._last_heartbeat = time.time()

    def _touch_message(self) -> None:
        self._last_message_at = time.time()
