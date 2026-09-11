"""
Telegram Bot API 服务
"""

import shutil
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from module_api.v1.dao.compat_message_store_dao import CompatMessageStoreDao
from module_api.v1.entity.vo.compat_vo import error_result
from module_api.v1.service.message_store_service import MessageStoreService
from module_api.v1.service.wechat_service import WechatService
from utils.connector_runtime import BaseConnector


class BotApiService:
    @classmethod
    def get_me(cls, connector: BaseConnector) -> dict[str, Any]:
        wc = WechatService._require(connector)
        uin = wc.protocol.session.uin
        return {
            'ok': True,
            'result': {
                'id': int(uin) if uin and str(uin).isdigit() else 0,
                'is_bot': True,
                'first_name': '文件传输助手',
                'username': 'filehelper',
                'can_join_groups': False,
                'can_read_all_group_messages': False,
                'supports_inline_queries': False,
            },
        }

    @classmethod
    def get_chat(cls, connector: BaseConnector) -> dict[str, Any]:
        wc = WechatService._require(connector)
        uin = wc.protocol.session.uin
        return {
            'ok': True,
            'result': {
                'id': int(uin) if uin and str(uin).isdigit() else 0,
                'type': 'private',
                'first_name': '文件传输助手',
                'username': 'filehelper',
            },
        }

    @classmethod
    async def get_updates(cls, db: AsyncSession, offset: int, limit: int) -> dict[str, Any]:
        rows = await MessageStoreService.get_updates(db, offset=offset, limit=limit)
        return {'ok': True, 'result': rows}

    @classmethod
    async def get_file(cls, db: AsyncSession, file_id: str) -> dict[str, Any]:
        file_info = await MessageStoreService.get_file(db, file_id)
        if not file_info:
            return error_result(400, 'Bad Request: file not found')
        return {
            'ok': True,
            'result': {
                'file_id': file_info['msg_id'],
                'file_unique_id': file_info['msg_id'],
                'file_size': file_info['file_size'],
                'file_path': file_info['file_path'],
            },
        }

    @classmethod
    async def set_webhook(cls, db: AsyncSession, url: str) -> dict[str, Any]:
        await MessageStoreService.set_webhook(db, url)
        await db.commit()
        return {'ok': True, 'result': True, 'description': 'Webhook was set'}

    @classmethod
    async def delete_webhook(cls, db: AsyncSession) -> dict[str, Any]:
        await MessageStoreService.set_webhook(db, '')
        await db.commit()
        return {'ok': True, 'result': True}

    @classmethod
    async def get_webhook_info(cls, db: AsyncSession) -> dict[str, Any]:
        url = await MessageStoreService.get_webhook(db)
        return {
            'ok': True,
            'result': {
                'url': url,
                'has_custom_certificate': False,
                'pending_update_count': 0,
                'max_connections': 40,
                'ip_address': None,
            },
        }

    @classmethod
    async def send_text(
        cls,
        db: AsyncSession,
        connector: BaseConnector,
        *,
        text: str,
        reply_to_message_id: str | None = None,
    ) -> dict[str, Any]:
        if not await WechatService.check_login_status(connector, poll=False):
            return error_result(401, 'Unauthorized')
        ok = await WechatService.send_text(connector, text)
        if not ok:
            return error_result(500, 'send_text failed')
        result = await MessageStoreService.persist_sent_text(
            db,
            text=text,
            reply_to_message_id=reply_to_message_id,
        )
        await db.commit()
        return result

    @classmethod
    async def send_file(
        cls,
        db: AsyncSession,
        connector: BaseConnector,
        *,
        file_path: str,
        reply_to_message_id: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        if not await WechatService.check_login_status(connector, poll=False):
            return error_result(401, 'Unauthorized')
        ok = await WechatService.send_file(connector, file_path)
        if not ok:
            return error_result(500, 'send_file failed')
        result = await MessageStoreService.persist_sent_file(
            db,
            file_path=file_path,
            reply_to_message_id=reply_to_message_id,
        )
        if caption:
            await WechatService.send_text(connector, caption)
            await MessageStoreService.persist_sent_text(db, text=caption)
        await db.commit()
        return result

    @classmethod
    async def send_uploaded_file(
        cls,
        db: AsyncSession,
        connector: BaseConnector,
        *,
        filename: str | None,
        file_obj: Any,
        reply_to_message_id: str | None = None,
        caption: str | None = None,
        default_suffix: str = '',
    ) -> dict[str, Any]:
        suffix = Path(filename or f'upload{default_suffix}').suffix or default_suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file_obj, tmp)
            tmp_path = tmp.name
        try:
            return await cls.send_file(
                db,
                connector,
                file_path=tmp_path,
                reply_to_message_id=reply_to_message_id,
                caption=caption,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @classmethod
    async def copy_message(
        cls,
        db: AsyncSession,
        connector: BaseConnector,
        *,
        message_id: str,
    ) -> dict[str, Any]:
        if not await WechatService.check_login_status(connector, poll=False):
            return error_result(401, 'Unauthorized')
        row = await CompatMessageStoreDao.get_message(db, message_id)
        if row is None:
            return error_result(400, 'Bad Request: message not found')
        if row.type == 'text' and row.text:
            return await cls.send_text(db, connector, text=row.text)
        if row.file_path:
            return await cls.send_file(db, connector, file_path=row.file_path)
        return error_result(400, 'Bad Request: message has no content')
