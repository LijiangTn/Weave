import pytest

from connectors.wechat.protocol import WeChatProtocol


class _DummyResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {'BaseResponse': {'Ret': 0}, 'MsgID': '123'}


class _DummyClient:
    def __init__(self):
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append({'url': url, **kwargs})
        return _DummyResponse()


@pytest.mark.asyncio
async def test_send_text_posts_utf8_json_body():
    protocol = WeChatProtocol(
        entry_host='szfilehelper.weixin.qq.com',
        mmweb_appid='wx_webfilehelper',
        to_user_name='filehelper',
    )
    protocol.client = _DummyClient()
    protocol.session.skey = 'skey'
    protocol.session.sid = 'sid'
    protocol.session.uin = '123'
    protocol.session.pass_ticket = 'ticket'
    protocol.session.user_name = 'me'
    protocol.session.device_id = 'device'

    ok = await protocol.send_text('哈喽')

    assert ok is True
    assert len(protocol.client.calls) == 1
    call = protocol.client.calls[0]
    assert call['headers']['Content-Type'] == 'application/json; charset=utf-8'
    assert 'json' not in call
    assert 'content' in call
    assert '哈喽'.encode('utf-8') in call['content']
    assert b'\\u54c8\\u55bd' not in call['content']
