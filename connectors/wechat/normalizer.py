"""
微信原始消息 → UnifiedMessage

参照 wx-filehelper-api 的 _normalize_messages，仅做结构化映射；
过滤逻辑（来源 user 非 filehelper）由 connector 层负责。
"""

import html
import re
import time

from module_api.v1.entity.vo.message_vo import MessageContent, MessageParty, MessageType, UnifiedMessage
from module_api.v1.entity.vo.normalizer_vo import BaseNormalizer

_UNICODE_ESCAPE_RE = re.compile(r'\\u[0-9a-fA-F]{4}')

################################# 微信原始消息归一化 #################################
class WeChatNormalizer(BaseNormalizer):
    source = 'wechat'

    ################################# 类型映射与字段填充 #################################
    def normalize(self, raw: dict) -> UnifiedMessage | None:
        msg_id = str(raw.get('MsgId', ''))
        if not msg_id:
            return None

        msg_type = raw.get('MsgType')
        app_msg_type = raw.get('AppMsgType')

        # 类型映射
        if msg_type == 1:
            mtype = MessageType.TEXT
        elif msg_type == 3:
            mtype = MessageType.IMAGE
        elif msg_type == 34:
            mtype = MessageType.AUDIO
        elif msg_type == 43:
            mtype = MessageType.VIDEO
        elif msg_type == 49:
            mtype = MessageType.FILE if app_msg_type == 6 else MessageType.LINK
        elif msg_type == 10002:
            mtype = MessageType.SYSTEM
        else:
            mtype = MessageType.UNKNOWN

        content = MessageContent()
        if mtype == MessageType.TEXT:
            content.text = self._decode_text_content(raw.get('Content', ''))
        elif mtype == MessageType.IMAGE:
            name = raw.get('FileName') or f'img_{msg_id}.jpg'
            content.file_name = name
            content.mime_type = 'image/jpeg'
            content.file_size = int(raw.get('ImgHeight', 0)) and None  # 图片大小由下载后填写
        elif mtype == MessageType.FILE:
            content.file_name = raw.get('FileName') or f'file_{msg_id}'
            try:
                content.file_size = int(raw.get('FileSize') or 0)
            except (TypeError, ValueError):
                content.file_size = None
        elif mtype == MessageType.LINK:
            content.url = raw.get('Url')

        try:
            timestamp = int(raw.get('CreateTime') or time.time())
        except (TypeError, ValueError):
            timestamp = int(time.time())

        sender = MessageParty(
            id=str(raw.get('FromUserName', '')),
            type='user',
        )
        receiver = MessageParty(
            id=str(raw.get('ToUserName', '')),
            type='user',
        )

        metadata = {
            'msg_type': msg_type,
            'app_msg_type': app_msg_type,
            'raw': {k: v for k, v in raw.items() if k not in {'Content', 'Url'}},
        }

        return UnifiedMessage(
            source=self.source,
            source_message_id=msg_id,
            type=mtype,
            content=content,
            sender=sender,
            receiver=receiver,
            timestamp=timestamp,
            metadata=metadata,
        )

    ################################# 文本解码工具 #################################
    @staticmethod
    def _decode_text_content(value: object) -> str:
        text = html.unescape(str(value or ''))
        if not _UNICODE_ESCAPE_RE.search(text):
            return text
        try:
            return text.encode('utf-8').decode('unicode_escape')
        except Exception:
            return text
