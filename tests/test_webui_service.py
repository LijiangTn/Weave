"""
WebUI 服务测试
"""

import pytest

from module_api.v1.service.webui_service import WebUIService


@pytest.mark.asyncio
async def test_webui_status_payload(monkeypatch):
    async def fake_check_login_status(connector, poll=True):
        return True

    async def fake_get_login_status(connector):
        return {
            'logged_in': True,
            'status': 'logged_in',
            'code': 200,
            'has_uuid': False,
            'uuid_age_seconds': None,
            'entry_host': 'szfilehelper.weixin.qq.com',
        }

    monkeypatch.setattr(
        'module_api.v1.service.webui_service.WechatService.check_login_status',
        fake_check_login_status,
    )
    monkeypatch.setattr(
        'module_api.v1.service.webui_service.WechatService.get_login_status',
        fake_get_login_status,
    )

    payload = await WebUIService.get_status_payload(type('C', (), {'is_logged_in': False})(), poll_login=True)
    assert payload['logged_in'] is True
    assert payload['login_status'] == 'logged_in'
    assert payload['plugins_count'] == 3


def test_webui_page_contains_app_name():
    html = WebUIService.render_page()
    assert '<html' in html.lower()
    assert '/bot/sendMessage' in html
