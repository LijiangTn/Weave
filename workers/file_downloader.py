"""
微信文件下载器

封装 WeChatProtocol.download_image / download_file 两种入口，
返回字节流供 FileService 落盘。
"""

from dataclasses import dataclass
from typing import Any

from connectors.wechat.protocol import WeChatProtocol
from module_api.v1.entity.vo.message_vo import MessageType

@dataclass
class DownloadResult:
    success: bool
    content: bytes | None = None
    error: str | None = None

class WeChatFileDownloader:
    def __init__(self, protocol: WeChatProtocol) -> None:
        self.protocol = protocol

    async def download(self, msg_type: MessageType, raw: dict[str, Any]) -> DownloadResult:
        try:
            if msg_type == MessageType.IMAGE:
                content = await self.protocol.download_image(raw)
            elif msg_type == MessageType.FILE:
                content = await self.protocol.download_file(raw)
            else:
                return DownloadResult(success=False, error='unsupported message type')
            if content is None:
                return DownloadResult(success=False, error='empty response')
            return DownloadResult(success=True, content=content)
        except Exception as exc:
            return DownloadResult(success=False, error=str(exc))