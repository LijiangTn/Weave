"""
消息 DAO
"""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from module_api.v1.entity.do.message_do import Message
from module_api.v1.entity.vo.message_vo import UnifiedMessage

class MessageDao:
    @classmethod
    async def get_by_id(cls, db: AsyncSession, message_id: str) -> Message | None:
        result = await db.execute(select(Message).where(Message.id == message_id))
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_source_msgid(
        cls, db: AsyncSession, source: str, source_message_id: str
    ) -> Message | None:
        result = await db.execute(
            select(Message).where(
                Message.source == source, Message.source_message_id == source_message_id
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    async def create(cls, db: AsyncSession, message: UnifiedMessage) -> Message:
        msg_do = Message(
            id=message.id,
            source=message.source,
            source_message_id=message.source_message_id,
            event_id=message.event_id,
            type=message.type.value,
            content_json=json.dumps(message.content.model_dump(), ensure_ascii=False),
            sender_json=json.dumps(message.sender.model_dump(), ensure_ascii=False)
            if message.sender
            else None,
            receiver_json=json.dumps(message.receiver.model_dump(), ensure_ascii=False)
            if message.receiver
            else None,
            timestamp=message.timestamp,
            metadata_json=json.dumps(message.metadata, ensure_ascii=False),
            status='received',
        )
        db.add(msg_do)
        await db.flush()
        return msg_do

    @classmethod
    async def list_query(cls, db: AsyncSession, params: Any):
        query = select(Message)
        if params is not None:
            query = params.filter(query)
            query = params.sort(query)
        else:
            query = query.order_by(Message.timestamp.desc())
        return query

    @classmethod
    async def update_status(
        cls, db: AsyncSession, message_id: str, status: str, file_id: str | None = None
    ) -> None:
        msg = await cls.get_by_id(db, message_id)
        if msg is None:
            return
        msg.status = status
        if file_id is not None:
            content = json.loads(msg.content_json or '{}')
            content['file_id'] = file_id
            msg.content_json = json.dumps(content, ensure_ascii=False)
        await db.commit()

    @classmethod
    def is_duplicate_error(cls, exc: IntegrityError) -> bool:
        msg = str(exc.orig).lower()
        return 'unique' in msg or 'duplicate' in msg