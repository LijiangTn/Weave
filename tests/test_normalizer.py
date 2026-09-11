"""
微信 normalizer 测试
"""

from connectors.wechat.normalizer import WeChatNormalizer
from module_api.v1.entity.vo.message_vo import MessageType

def _text_raw(msg_id: str = '1001', text: str = 'hello') -> dict:
    return {
        'MsgId': msg_id,
        'MsgType': 1,
        'Content': text,
        'FromUserName': 'filehelper',
        'ToUserName': 'me',
        'CreateTime': 1700000000,
    }

def _image_raw(msg_id: str = '2002') -> dict:
    return {
        'MsgId': msg_id,
        'MsgType': 3,
        'FileName': 'pic.jpg',
        'FromUserName': 'filehelper',
        'ToUserName': 'me',
        'CreateTime': 1700000001,
    }

def _file_raw(msg_id: str = '3003') -> dict:
    return {
        'MsgId': msg_id,
        'MsgType': 49,
        'AppMsgType': 6,
        'FileName': 'doc.pdf',
        'FileSize': 12345,
        'FromUserName': 'filehelper',
        'ToUserName': 'me',
        'CreateTime': 1700000002,
    }

def test_normalize_text():
    n = WeChatNormalizer()
    m = n.normalize(_text_raw('1001', '&lt;hi&gt;'))
    assert m is not None
    assert m.type == MessageType.TEXT
    assert m.source_message_id == '1001'
    assert m.content.text == '<hi>'
    assert m.sender and m.sender.id == 'filehelper'

def test_normalize_text_decodes_unicode_escape():
    n = WeChatNormalizer()
    m = n.normalize(_text_raw('1002', r'\u54c8\u55bd'))
    assert m is not None
    assert m.content.text == '哈喽'

def test_normalize_image():
    n = WeChatNormalizer()
    m = n.normalize(_image_raw('2002'))
    assert m is not None and m.type == MessageType.IMAGE
    assert m.content.file_name == 'pic.jpg'
    assert m.content.mime_type == 'image/jpeg'

def test_normalize_file():
    n = WeChatNormalizer()
    m = n.normalize(_file_raw('3003'))
    assert m is not None and m.type == MessageType.FILE
    assert m.content.file_size == 12345

def test_normalize_skips_empty_msgid():
    assert WeChatNormalizer().normalize({'MsgType': 1}) is None
