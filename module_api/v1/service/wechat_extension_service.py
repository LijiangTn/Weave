"""
微信扩展服务
"""

from typing import Any

from module_api.v1.service.wechat_service import WechatService
from utils.connector_runtime import BaseConnector


class WechatExtensionService:
    @classmethod
    async def save_session(cls, connector: BaseConnector) -> dict[str, Any]:
        ok = await WechatService._require(connector).save_session()
        return {'ok': ok}

    @classmethod
    async def get_trace_status(cls, connector: BaseConnector) -> dict[str, Any]:
        return await WechatService.get_trace_status(connector)

    @classmethod
    async def read_recent_traces(cls, connector: BaseConnector, limit: int) -> dict[str, Any]:
        rows = await WechatService.read_recent_traces(connector, limit=limit)
        return {'count': len(rows), 'rows': rows}

    @classmethod
    async def clear_traces(cls, connector: BaseConnector) -> dict[str, Any]:
        await WechatService.clear_traces(connector)
        return {'status': 'cleared'}
