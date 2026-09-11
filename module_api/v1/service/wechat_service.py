"""
微信模块 Service
"""

from typing import Any

from connectors.wechat.connector import WeChatConnector
from exceptions.exception import ServiceException
from utils.connector_runtime import BaseConnector, ConnectorState


class WechatService:
    @staticmethod
    def _require(connector: BaseConnector) -> WeChatConnector:
        if not isinstance(connector, WeChatConnector):
            raise ServiceException(message='connector is not wechat')
        return connector

    @classmethod
    async def get_qr(cls, connector: BaseConnector) -> bytes:
        wc = cls._require(connector)
        # 拿二维码时若 worker 未启动，顺手拉起；否则扫码后没人轮询
        if wc.state.value in {'stopped', 'disconnected', 'ERROR'}:
            await wc.start()
        return await wc.get_qr()

    @classmethod
    async def get_login_status(cls, connector: BaseConnector) -> dict[str, Any]:
        return await cls._require(connector).get_login_status()

    @classmethod
    async def check_login_status(cls, connector: BaseConnector, poll: bool = True) -> bool:
        return await cls._require(connector).check_login_status(poll=poll)

    @classmethod
    async def get_latest_messages(cls, connector: BaseConnector, limit: int = 10) -> list[dict[str, Any]]:
        return await cls._require(connector).get_latest_messages(limit=limit)

    @classmethod
    async def connect(cls, connector: BaseConnector) -> dict[str, Any]:
        wc = cls._require(connector)

        if wc.state in {ConnectorState.CONNECTED}:
            return {'state': wc.state.value, 'already_connected': True}
        await wc.start()
        return {'state': wc.state.value, 'already_connected': False}

    @classmethod
    async def disconnect(cls, connector: BaseConnector) -> dict[str, Any]:
        wc = cls._require(connector)
        await wc.stop()
        return {'state': wc.state.value}

    @classmethod
    async def get_status(cls, connector: BaseConnector) -> dict[str, Any]:
        status = connector.get_status()
        return {
            'source': status.source,
            'state': status.state,
            'is_logged_in': status.is_logged_in,
            'last_error': status.last_error,
            'reconnect_attempts': status.reconnect_attempts,
            'last_heartbeat': status.last_heartbeat,
            'last_message_at': status.last_message_at,
        }

    @classmethod
    async def send_text(cls, connector: BaseConnector, message: str) -> bool:
        return await cls._require(connector).send_text(message)

    @classmethod
    async def send_file(cls, connector: BaseConnector, file_path: str) -> bool:
        return await cls._require(connector).send_file(file_path)

    @classmethod
    async def get_trace_status(cls, connector: BaseConnector) -> dict[str, Any]:
        return cls._require(connector).get_trace_status()

    @classmethod
    async def read_recent_traces(cls, connector: BaseConnector, limit: int = 100) -> list[dict[str, Any]]:
        return await cls._require(connector).read_recent_traces(limit=limit)

    @classmethod
    async def clear_traces(cls, connector: BaseConnector) -> bool:
        return await cls._require(connector).clear_traces()

    @classmethod
    def get_framework_state(cls, connector: BaseConnector) -> dict[str, Any]:
        return cls._require(connector).framework_state()
