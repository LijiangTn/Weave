"""
消息 Service
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from module_api.v1.dao.message_dao import MessageDao
from module_api.v1.entity.do.message_do import Message
from module_api.v1.entity.vo.message_vo import UnifiedMessage
from utils.domain_events import MessageDuplicateEvent, MessageReceivedEvent
from utils.event_bus import event_bus
from utils.log_util import logger

class MessageService:
    @classmethod
    async def persist(
        cls, db: AsyncSession, message: UnifiedMessage
    ) -> Message | None:
        existing = await MessageDao.get_by_source_msgid(
            db, message.source, message.source_message_id
        )
        if existing is not None:
            await event_bus.publish(
                MessageDuplicateEvent(
                    source=message.source,
                    message_id=existing.id,
                    source_message_id=message.source_message_id,
                )
            )
            logger.debug(
                f'[message] duplicate skipped: source={message.source} '
                f'source_message_id={message.source_message_id}'
            )
            return None

        try:
            msg_do = await MessageDao.create(db, message)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            if MessageDao.is_duplicate_error(exc):
                existing = await MessageDao.get_by_source_msgid(
                    db, message.source, message.source_message_id
                )
                if existing is not None:
                    logger.debug(
                        f'[message] duplicate (race): source={message.source} '
                        f'source_message_id={message.source_message_id}'
                    )
                    return None
            logger.warning(f'[message] persist failed: {exc}')
            raise

        await event_bus.publish(
            MessageReceivedEvent(source=message.source, message_id=msg_do.id)
        )
        logger.info(
            f'[message] persisted: id={msg_do.id} type={msg_do.type} '
            f'source_msgid={msg_do.source_message_id}'
        )
        return msg_do

    @classmethod
    async def get_by_id(cls, db: AsyncSession, message_id: str) -> Message | None:
        return await MessageDao.get_by_id(db, message_id)

    @classmethod
    async def list_query(cls, db: AsyncSession, params: Any):
        return await MessageDao.list_query(db, params)
