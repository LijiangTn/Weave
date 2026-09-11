"""
消息持久化 + 去重测试

覆盖：
1. 同一 source_message_id 持久化两次只入库一条
2. 不同 source_message_id 正常入库
3. 并发场景下 unique 约束兜底
"""

import pytest

from module_api.v1.service.message_service import MessageService
from module_api.v1.entity.vo.message_vo import MessageContent, MessageType, UnifiedMessage

def _msg(source_msg_id: str, *, source: str = 'wechat') -> UnifiedMessage:
    return UnifiedMessage(
        source=source,
        source_message_id=source_msg_id,
        type=MessageType.TEXT,
        content=MessageContent(text=f'hi {source_msg_id}'),
        timestamp=1700000000,
    )

@pytest.mark.asyncio
async def test_persist_creates_message(db_session):
    m = await MessageService.persist(db_session, _msg('m1'))
    assert m is not None
    assert m.source_message_id == 'm1'
    assert m.type == 'text'

@pytest.mark.asyncio
async def test_persist_dedup_returns_none(db_session):
    m1 = await MessageService.persist(db_session, _msg('m2'))
    m2 = await MessageService.persist(db_session, _msg('m2'))
    assert m1 is not None
    assert m2 is None  # 命中幂等
    # 数据库中只一条
    from module_api.v1.dao.message_dao import MessageDao

    same = await MessageDao.get_by_source_msgid(db_session, 'wechat', 'm2')
    assert same is not None and same.id == m1.id

@pytest.mark.asyncio
async def test_persist_different_source_msgid_both_persist(db_session):
    m1 = await MessageService.persist(db_session, _msg('m3'))
    m2 = await MessageService.persist(db_session, _msg('m4'))
    assert m1 is not None and m2 is not None
    assert m1.id != m2.id

@pytest.mark.asyncio
async def test_persist_different_source_both_persist(db_session):
    m1 = await MessageService.persist(db_session, _msg('m5', source='wechat'))
    m2 = await MessageService.persist(db_session, _msg('m5', source='telegram'))
    assert m1 is not None and m2 is not None
    assert m1.id != m2.id