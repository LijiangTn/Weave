"""
根接口服务
"""

import shutil
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from config.env import AppConfig
from config.database import ASYNC_SQLALCHEMY_DATABASE_URL
from module_api.v1.service.framework_service import FrameworkService
from module_api.v1.service.message_store_service import MessageStoreService
from module_api.v1.service.wechat_service import WechatService
from utils.connector_runtime import BaseConnector


class RootService:
    @classmethod
    async def get_root_status(cls, db: AsyncSession, connector: BaseConnector) -> dict[str, Any]:
        is_logged_in = await WechatService.check_login_status(connector, poll=False)
        login = await WechatService.get_login_status(connector)
        status = connector.get_status()
        stats = await MessageStoreService.get_stats(
            db,
            db_path=ASYNC_SQLALCHEMY_DATABASE_URL if 'sqlite' in ASYNC_SQLALCHEMY_DATABASE_URL else None,
        )
        stats['webhook_url'] = await MessageStoreService.get_webhook(db)
        framework_state = await FrameworkService.get_state(connector, stats)
        return {
            'service': AppConfig.app_name,
            'version': AppConfig.app_version,
            'backend': 'direct-protocol',
            'logged_in': is_logged_in,
            'login': login,
            'framework': framework_state,
            'stability': {
                'reconnect_attempts': status.reconnect_attempts,
                'last_heartbeat': status.last_heartbeat,
                'total_messages': stats.get('message_count', 0),
                'recent_errors': 1 if status.last_error else 0,
            },
        }

    @classmethod
    async def get_login_status(cls, connector: BaseConnector, *, auto_poll: bool = True) -> dict[str, Any]:
        if auto_poll:
            await WechatService.check_login_status(connector, poll=True)
        return await WechatService.get_login_status(connector)

    @classmethod
    async def list_messages(cls, connector: BaseConnector, limit: int) -> dict[str, Any]:
        rows = await WechatService.get_latest_messages(connector, limit=limit)
        return {'ok': True, 'result': rows}

    @classmethod
    async def save_session(cls, connector: BaseConnector) -> dict[str, Any]:
        ok = await WechatService._require(connector).save_session()
        return {'ok': ok}

    @classmethod
    async def send_text(cls, connector: BaseConnector, content: str) -> dict[str, Any]:
        if not await WechatService.check_login_status(connector, poll=False):
            raise PermissionError('Unauthorized')
        ok = await WechatService.send_text(connector, content)
        if not ok:
            raise RuntimeError('send_text failed')
        return {'ok': True, 'result': {'text': content}}

    @classmethod
    async def upload_file(cls, connector: BaseConnector, filename: str | None, file_obj: Any) -> dict[str, Any]:
        if not await WechatService.check_login_status(connector, poll=False):
            raise PermissionError('Unauthorized')
        suffix = Path(filename or 'file').suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file_obj, tmp)
            tmp_path = tmp.name
        try:
            ok = await WechatService.send_file(connector, tmp_path)
            if not ok:
                raise RuntimeError('send_file failed')
            return {'status': 'sent', 'filename': filename}
        finally:
            Path(tmp_path).unlink(missing_ok=True)
