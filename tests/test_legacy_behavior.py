"""
接口行为兼容测试
"""

import pytest

from module_api.v1.service.bot_api_service import BotApiService
from module_api.v1.service.root_service import RootService


@pytest.mark.asyncio
async def test_root_login_status_respects_auto_poll(monkeypatch):
    calls: list[bool] = []

    async def fake_check_login_status(connector, poll=True):
        calls.append(poll)
        return True

    async def fake_get_login_status(connector):
        return {'logged_in': True, 'code': 200, 'status': 'logged_in'}

    monkeypatch.setattr(
        'module_api.v1.service.root_service.WechatService.check_login_status',
        fake_check_login_status,
    )
    monkeypatch.setattr(
        'module_api.v1.service.root_service.WechatService.get_login_status',
        fake_get_login_status,
    )

    result = await RootService.get_login_status(object(), auto_poll=True)
    assert result['status'] == 'logged_in'
    assert calls == [True]


@pytest.mark.asyncio
async def test_root_messages_use_connector_cache(monkeypatch):
    async def fake_get_latest_messages(connector, limit=10):
        return [{'id': 'm1', 'type': 'text', 'text': 'hello', 'is_mine': False}]

    monkeypatch.setattr(
        'module_api.v1.service.root_service.WechatService.get_latest_messages',
        fake_get_latest_messages,
    )

    result = await RootService.list_messages(object(), 10)
    assert result == {
        'ok': True,
        'result': [{'id': 'm1', 'type': 'text', 'text': 'hello', 'is_mine': False}],
    }


@pytest.mark.asyncio
async def test_bot_send_message_returns_unauthorized_when_not_logged_in(db_session, monkeypatch):
    async def fake_check_login_status(connector, poll=True):
        return False

    monkeypatch.setattr(
        'module_api.v1.service.bot_api_service.WechatService.check_login_status',
        fake_check_login_status,
    )

    result = await BotApiService.send_text(db_session, object(), text='hi')
    assert result == {'ok': False, 'error_code': 401, 'description': 'Unauthorized'}


@pytest.mark.asyncio
async def test_root_send_raises_permission_error_when_not_logged_in(monkeypatch):
    async def fake_check_login_status(connector, poll=True):
        return False

    monkeypatch.setattr(
        'module_api.v1.service.root_service.WechatService.check_login_status',
        fake_check_login_status,
    )

    with pytest.raises(PermissionError, match='Unauthorized'):
        await RootService.send_text(object(), 'hi')
