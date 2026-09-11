"""
文件元数据 + 落盘测试

使用 tmp_path 提供临时 storage_dir，验证 File 行创建与磁盘文件存在。
"""

import pytest

from config.env import StorageConfig
from module_api.v1.service.file_service import FileService
from module_api.v1.entity.vo.message_vo import MessageContent, MessageType, UnifiedMessage
from workers.file_downloader import DownloadResult, WeChatFileDownloader

class FakeDownloader(WeChatFileDownloader):
    def __init__(self, content: bytes, error: str | None = None) -> None:  # noqa: D401
        self._content = content
        self._error = error

    async def download(self, msg_type, raw):  # type: ignore[override]
        if self._error:
            return DownloadResult(success=False, error=self._error)
        return DownloadResult(success=True, content=self._content)

@pytest.fixture
def storage(tmp_path, monkeypatch):
    from config.env import StorageConfig as storage_cfg
    monkeypatch.setattr(storage_cfg, 'storage_dir', str(tmp_path))
    monkeypatch.setattr(storage_cfg, 'file_date_subdir', False)
    return storage_cfg

@pytest.mark.asyncio
async def test_download_and_attach_success(db_session, storage):
    unified = UnifiedMessage(
        source='wechat',
        source_message_id='f1',
        type=MessageType.IMAGE,
        content=MessageContent(file_name='pic.jpg', mime_type='image/jpeg'),
        timestamp=1700000000,
    )
    downloader = FakeDownloader(content=b'\x89PNG\r\n\x1a\n')

    f_row = await FileService.download_and_attach(
        db_session, unified, {}, downloader, storage
    )
    assert f_row is not None
    assert f_row.status == 'downloaded'
    assert f_row.size == 8

    from pathlib import Path
    saved = Path(storage.storage_dir) / f_row.path
    assert saved.exists()
    assert saved.read_bytes() == b'\x89PNG\r\n\x1a\n'

@pytest.mark.asyncio
async def test_download_and_attach_failure(db_session, storage):
    unified = UnifiedMessage(
        source='wechat',
        source_message_id='f2',
        type=MessageType.FILE,
        content=MessageContent(file_name='x.bin'),
        timestamp=1700000000,
    )
    downloader = FakeDownloader(content=b'', error='network error')

    f_row = await FileService.download_and_attach(
        db_session, unified, {}, downloader, storage
    )
    assert f_row is not None
    assert f_row.status == 'failed'
    assert 'network error' in (f_row.error or '')

@pytest.mark.asyncio
async def test_download_and_attach_skips_non_media(db_session, storage):
    unified = UnifiedMessage(
        source='wechat',
        source_message_id='f3',
        type=MessageType.TEXT,
        content=MessageContent(text='hi'),
        timestamp=1700000000,
    )
    f_row = await FileService.download_and_attach(
        db_session, unified, {}, FakeDownloader(content=b''), storage
    )
    assert f_row is None