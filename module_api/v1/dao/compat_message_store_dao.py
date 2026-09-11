"""
消息存储 DAO
"""

import json
import time
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from module_api.v1.entity.do.compat_file_do import CompatFile
from module_api.v1.entity.do.compat_kv_store_do import CompatKvStore
from module_api.v1.entity.do.compat_message_do import CompatMessage


class CompatMessageStoreDao:
    @classmethod
    async def upsert_message(
        cls,
        db: AsyncSession,
        *,
        msg_id: str,
        msg_type: str,
        text: str,
        is_mine: bool = False,
        timestamp: int | None = None,
        file_name: str | None = None,
        file_path: str | None = None,
        file_size: int | None = None,
        reply_to_id: str | None = None,
        raw_data: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> CompatMessage:
        row = await cls.get_message(db, msg_id)
        ts = timestamp or int(time.time())
        raw_json = json.dumps(raw_data, ensure_ascii=False) if raw_data else None
        extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
        if row is None:
            row = CompatMessage(
                msg_id=msg_id,
                type=msg_type,
                text=text,
                is_mine=1 if is_mine else 0,
                timestamp=ts,
                file_name=file_name,
                file_path=file_path,
                file_size=file_size,
                reply_to_id=reply_to_id,
                raw_data=raw_json,
                extra=extra_json,
            )
            db.add(row)
        else:
            row.type = msg_type
            row.text = text
            row.is_mine = 1 if is_mine else 0
            row.timestamp = ts
            row.file_name = file_name
            row.file_path = file_path
            row.file_size = file_size
            row.reply_to_id = reply_to_id
            row.raw_data = raw_json
            row.extra = extra_json
        await db.flush()
        return row

    @classmethod
    async def get_message(cls, db: AsyncSession, msg_id: str) -> CompatMessage | None:
        result = await db.execute(select(CompatMessage).where(CompatMessage.msg_id == msg_id))
        return result.scalar_one_or_none()

    @classmethod
    async def get_message_by_id(cls, db: AsyncSession, id_: int) -> CompatMessage | None:
        result = await db.execute(select(CompatMessage).where(CompatMessage.id == id_))
        return result.scalar_one_or_none()

    @classmethod
    async def get_updates(
        cls,
        db: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 100,
        msg_type: str | None = None,
        since: int | None = None,
    ) -> list[CompatMessage]:
        query = select(CompatMessage).where(CompatMessage.id > offset)
        if msg_type:
            query = query.where(CompatMessage.type == msg_type)
        if since:
            query = query.where(CompatMessage.timestamp >= since)
        query = query.order_by(CompatMessage.id.asc()).limit(min(limit, 1000))
        result = await db.execute(query)
        return list(result.scalars().all())

    @classmethod
    async def get_latest(cls, db: AsyncSession, limit: int = 50) -> list[CompatMessage]:
        result = await db.execute(
            select(CompatMessage).order_by(CompatMessage.id.desc()).limit(min(limit, 1000))
        )
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    @classmethod
    async def get_max_id(cls, db: AsyncSession) -> int:
        result = await db.execute(select(func.max(CompatMessage.id)))
        return int(result.scalar() or 0)

    @classmethod
    async def upsert_file(
        cls,
        db: AsyncSession,
        *,
        msg_id: str,
        file_name: str,
        file_path: str,
        file_size: int = 0,
        mime_type: str | None = None,
        md5: str | None = None,
        downloaded: bool = True,
    ) -> CompatFile:
        row = await cls.get_file_by_msg_id(db, msg_id)
        now = int(time.time())
        if row is None:
            row = CompatFile(
                msg_id=msg_id,
                file_name=file_name,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                md5=md5,
                created_at=now,
                downloaded=1 if downloaded else 0,
            )
            db.add(row)
        else:
            row.file_name = file_name
            row.file_path = file_path
            row.file_size = file_size
            row.mime_type = mime_type
            row.md5 = md5
            row.downloaded = 1 if downloaded else 0
        await db.flush()
        return row

    @classmethod
    async def get_files(cls, db: AsyncSession, *, limit: int = 100, offset: int = 0) -> list[CompatFile]:
        result = await db.execute(
            select(CompatFile)
            .order_by(CompatFile.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @classmethod
    async def get_file_by_msg_id(cls, db: AsyncSession, msg_id: str) -> CompatFile | None:
        result = await db.execute(select(CompatFile).where(CompatFile.msg_id == msg_id))
        return result.scalar_one_or_none()

    @classmethod
    async def set_kv(cls, db: AsyncSession, key: str, value: Any) -> None:
        row = await cls.get_kv_row(db, key)
        payload = json.dumps(value, ensure_ascii=False)
        now = int(time.time())
        if row is None:
            row = CompatKvStore(key=key, value=payload, updated_at=now)
            db.add(row)
        else:
            row.value = payload
            row.updated_at = now
        await db.flush()

    @classmethod
    async def get_kv(cls, db: AsyncSession, key: str, default: Any = None) -> Any:
        row = await cls.get_kv_row(db, key)
        if row is None or row.value is None:
            return default
        try:
            return json.loads(row.value)
        except Exception:
            return row.value

    @classmethod
    async def get_kv_row(cls, db: AsyncSession, key: str) -> CompatKvStore | None:
        result = await db.execute(select(CompatKvStore).where(CompatKvStore.key == key))
        return result.scalar_one_or_none()

    @classmethod
    async def cleanup_old_messages(cls, db: AsyncSession, *, days: int) -> int:
        cutoff = int(time.time()) - days * 86400
        result = await db.execute(delete(CompatMessage).where(CompatMessage.timestamp < cutoff))
        return result.rowcount or 0

    @classmethod
    async def cleanup_old_files(cls, db: AsyncSession, *, days: int) -> int:
        cutoff = int(time.time()) - days * 86400
        result = await db.execute(delete(CompatFile).where(CompatFile.created_at < cutoff))
        return result.rowcount or 0

    @classmethod
    async def get_stats(cls, db: AsyncSession) -> dict[str, Any]:
        msg_count = int((await db.execute(select(func.count()).select_from(CompatMessage))).scalar() or 0)
        file_count = int((await db.execute(select(func.count()).select_from(CompatFile))).scalar() or 0)
        max_id = await cls.get_max_id(db)
        today = int(time.time())
        today = today - (today % 86400)
        today_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(CompatMessage).where(CompatMessage.timestamp >= today)
                )
            ).scalar()
            or 0
        )
        return {
            'message_count': msg_count,
            'file_count': file_count,
            'max_update_id': max_id,
            'today_message_count': today_count,
        }
