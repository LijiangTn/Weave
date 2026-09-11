"""
消息存储服务
"""

import mimetypes
import time
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from module_api.v1.dao.compat_message_store_dao import CompatMessageStoreDao
from module_api.v1.entity.do.compat_message_do import CompatMessage
from module_api.v1.entity.vo.message_vo import MessageType, UnifiedMessage


class MessageStoreService:
    WEBHOOK_KEY = 'message_webhook_url'

    @classmethod
    async def persist_received_message(
        cls,
        db: AsyncSession,
        unified: UnifiedMessage,
        *,
        raw: dict[str, Any] | None = None,
    ) -> CompatMessage:
        text = unified.content.text or ''
        if not text and unified.type in {MessageType.IMAGE, MessageType.FILE}:
            label = unified.content.file_name or unified.source_message_id
            prefix = 'Image' if unified.type == MessageType.IMAGE else 'File'
            text = f'[{prefix}: {label}]'
        return await CompatMessageStoreDao.upsert_message(
            db,
            msg_id=unified.source_message_id,
            msg_type=unified.type.value,
            text=text,
            is_mine=False,
            timestamp=unified.timestamp,
            file_name=unified.content.file_name,
            file_size=unified.content.file_size,
            raw_data=raw,
            extra={
                'source': unified.source,
                'unified_id': unified.id,
                'sender': unified.sender.model_dump() if unified.sender else None,
                'receiver': unified.receiver.model_dump() if unified.receiver else None,
                'metadata': unified.metadata,
            },
        )

    @classmethod
    async def persist_sent_text(
        cls,
        db: AsyncSession,
        *,
        text: str,
        reply_to_message_id: str | None = None,
    ) -> dict[str, Any]:
        msg_id = f'sent_{int(time.time() * 1000)}'
        row = await CompatMessageStoreDao.upsert_message(
            db,
            msg_id=msg_id,
            msg_type='text',
            text=text,
            is_mine=True,
            timestamp=int(time.time()),
            reply_to_id=reply_to_message_id,
        )
        return {
            'ok': True,
            'result': {
                'message_id': row.msg_id,
                'date': row.timestamp,
                'text': text,
                'reply_to_message_id': reply_to_message_id,
            },
        }

    @classmethod
    async def persist_sent_file(
        cls,
        db: AsyncSession,
        *,
        file_path: str,
        reply_to_message_id: str | None = None,
    ) -> dict[str, Any]:
        path = Path(file_path)
        file_size = path.stat().st_size if path.exists() else 0
        msg_id = f'sent_{int(time.time() * 1000)}'
        row = await CompatMessageStoreDao.upsert_message(
            db,
            msg_id=msg_id,
            msg_type='file',
            text=f'[File: {path.name}]',
            is_mine=True,
            timestamp=int(time.time()),
            file_name=path.name,
            file_path=str(path),
            file_size=file_size,
            reply_to_id=reply_to_message_id,
        )
        await CompatMessageStoreDao.upsert_file(
            db,
            msg_id=msg_id,
            file_name=path.name,
            file_path=str(path),
            file_size=file_size,
            mime_type=mimetypes.guess_type(path.name)[0],
            downloaded=True,
        )
        return {
            'ok': True,
            'result': {
                'message_id': row.msg_id,
                'date': row.timestamp,
                'document': {
                    'file_name': path.name,
                    'file_size': file_size,
                },
                'reply_to_message_id': reply_to_message_id,
            },
        }

    @classmethod
    async def persist_downloaded_file(
        cls,
        db: AsyncSession,
        unified: UnifiedMessage,
        *,
        file_path: str,
        file_size: int = 0,
        mime_type: str | None = None,
    ) -> None:
        file_name = unified.content.file_name or Path(file_path).name
        file_mime = mime_type or unified.content.mime_type
        if not file_mime:
            file_mime, _ = mimetypes.guess_type(file_name)
        await CompatMessageStoreDao.upsert_message(
            db,
            msg_id=unified.source_message_id,
            msg_type=unified.type.value,
            text=f'[File: {file_name}]' if unified.type == MessageType.FILE else f'[Image: {file_name}]',
            is_mine=False,
            timestamp=unified.timestamp,
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            raw_data=unified.metadata.get('raw') if isinstance(unified.metadata, dict) else None,
            extra={
                'source': unified.source,
                'unified_id': unified.id,
                'metadata': unified.metadata,
            },
        )
        await CompatMessageStoreDao.upsert_file(
            db,
            msg_id=unified.source_message_id,
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            mime_type=file_mime,
            downloaded=True,
        )

    @classmethod
    async def get_updates(
        cls,
        db: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 100,
        msg_type: str | None = None,
        since: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = await CompatMessageStoreDao.get_updates(
            db,
            offset=offset,
            limit=limit,
            msg_type=msg_type,
            since=since,
        )
        return [cls._to_update(row) for row in rows]

    @classmethod
    async def get_latest_messages(cls, db: AsyncSession, limit: int = 50) -> list[dict[str, Any]]:
        rows = await CompatMessageStoreDao.get_latest(db, limit=limit)
        return [cls._to_stored_message(row) for row in rows]

    @classmethod
    async def get_file(cls, db: AsyncSession, msg_id: str) -> dict[str, Any] | None:
        row = await CompatMessageStoreDao.get_file_by_msg_id(db, msg_id)
        if row is None:
            return None
        return {
            'id': row.id,
            'msg_id': row.msg_id,
            'file_name': row.file_name,
            'file_path': row.file_path,
            'file_size': row.file_size or 0,
            'mime_type': row.mime_type,
            'md5': row.md5,
            'created_at': row.created_at,
            'downloaded': bool(row.downloaded),
        }

    @classmethod
    async def get_files(
        cls,
        db: AsyncSession,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        rows = await CompatMessageStoreDao.get_files(db, limit=limit, offset=offset)
        return [
            {
                'id': row.id,
                'msg_id': row.msg_id,
                'file_name': row.file_name,
                'file_path': row.file_path,
                'file_size': row.file_size or 0,
                'mime_type': row.mime_type,
                'md5': row.md5,
                'created_at': row.created_at,
                'downloaded': bool(row.downloaded),
            }
            for row in rows
        ]

    @classmethod
    async def query_messages(
        cls,
        db: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 50,
        msg_type: str | None = None,
        since: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = await CompatMessageStoreDao.get_updates(
            db,
            offset=offset,
            limit=limit,
            msg_type=msg_type,
            since=since,
        )
        return [cls._to_stored_message(row) for row in rows]

    @classmethod
    async def get_stats(cls, db: AsyncSession, *, db_path: str | None = None) -> dict[str, Any]:
        stats = await CompatMessageStoreDao.get_stats(db)
        if db_path is not None:
            stats['db_path'] = db_path
            try:
                stats['db_size_bytes'] = Path(db_path).stat().st_size
            except OSError:
                stats['db_size_bytes'] = 0
        return stats

    @classmethod
    async def set_webhook(cls, db: AsyncSession, url: str) -> None:
        await CompatMessageStoreDao.set_kv(db, cls.WEBHOOK_KEY, url.strip())

    @classmethod
    async def get_webhook(cls, db: AsyncSession) -> str:
        return str(await CompatMessageStoreDao.get_kv(db, cls.WEBHOOK_KEY, ''))

    @classmethod
    async def push_webhook_if_needed(cls, db: AsyncSession, row: CompatMessage) -> None:
        webhook_url = await cls.get_webhook(db)
        if not webhook_url:
            return
        payload = cls._to_update(row)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(webhook_url, json=payload)
        except Exception:
            return

    @staticmethod
    def _to_update(row: CompatMessage) -> dict[str, Any]:
        return {
            'update_id': row.id,
            'message': {
                'message_id': row.msg_id,
                'date': row.timestamp,
                'text': row.text or '',
                'type': row.type,
                'is_from_bot': bool(row.is_mine),
                'document': (
                    {
                        'file_name': row.file_name,
                        'file_path': row.file_path,
                        'file_size': row.file_size,
                    }
                    if row.file_name
                    else None
                ),
                'reply_to_message_id': row.reply_to_id,
            },
        }

    @staticmethod
    def _to_stored_message(row: CompatMessage) -> dict[str, Any]:
        return {
            'id': row.id,
            'msg_id': row.msg_id,
            'type': row.type,
            'text': row.text or '',
            'is_mine': bool(row.is_mine),
            'timestamp': row.timestamp,
            'file_name': row.file_name,
            'file_path': row.file_path,
            'file_size': row.file_size,
            'reply_to_id': row.reply_to_id,
            'raw_data': row.raw_data,
            'extra': row.extra,
        }
