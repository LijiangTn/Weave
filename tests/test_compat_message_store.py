"""
消息存储测试
"""

import pytest

from module_api.v1.entity.vo.message_vo import MessageContent, MessageType, UnifiedMessage
from module_api.v1.service.message_store_service import MessageStoreService


def _msg(source_msg_id: str, *, msg_type: MessageType = MessageType.TEXT) -> UnifiedMessage:
    content = MessageContent(text=f'hi {source_msg_id}')
    if msg_type == MessageType.FILE:
        content = MessageContent(file_name='demo.pdf', file_size=123)
    return UnifiedMessage(
        source='wechat',
        source_message_id=source_msg_id,
        type=msg_type,
        content=content,
        timestamp=1700000000,
        metadata={'raw': {'MsgId': source_msg_id}},
    )


@pytest.mark.asyncio
async def test_compat_persist_and_get_updates(db_session):
    await MessageStoreService.persist_received_message(
        db_session,
        _msg('compat-1'),
        raw={'MsgId': 'compat-1'},
    )
    await db_session.commit()

    updates = await MessageStoreService.get_updates(db_session, offset=0, limit=10)
    assert len(updates) == 1
    assert updates[0]['message']['message_id'] == 'compat-1'
    assert updates[0]['message']['text'] == 'hi compat-1'
    assert updates[0]['message']['is_from_bot'] is False


@pytest.mark.asyncio
async def test_compat_persist_downloaded_file(db_session, tmp_path):
    unified = _msg('compat-file', msg_type=MessageType.FILE)
    await MessageStoreService.persist_received_message(db_session, unified, raw={'MsgId': 'compat-file'})
    await MessageStoreService.persist_downloaded_file(
        db_session,
        unified,
        file_path=str(tmp_path / 'demo.pdf'),
        file_size=123,
        mime_type='application/pdf',
    )
    await db_session.commit()

    file_info = await MessageStoreService.get_file(db_session, 'compat-file')
    assert file_info is not None
    assert file_info['file_name'] == 'demo.pdf'
    assert file_info['file_size'] == 123


@pytest.mark.asyncio
async def test_compat_webhook_roundtrip(db_session):
    await MessageStoreService.set_webhook(db_session, 'http://localhost:9000/hook')
    await db_session.commit()

    assert await MessageStoreService.get_webhook(db_session) == 'http://localhost:9000/hook'
