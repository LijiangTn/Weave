"""
文件 Service
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from config.env import StorageConfig
from module_api.v1.dao.file_dao import FileDao
from module_api.v1.dao.message_dao import MessageDao
from module_api.v1.entity.do.file_do import File
from module_api.v1.entity.vo.message_vo import MessageType, UnifiedMessage
from utils.file_storage import relative_path, unique_path
from utils.log_util import logger
from workers.file_downloader import WeChatFileDownloader

class FileService:
    @classmethod
    async def get_by_id(cls, db: AsyncSession, file_id: str) -> File | None:
        return await FileDao.get_by_id(db, file_id)

    @classmethod
    async def list_recent(cls, db: AsyncSession, limit: int = 100) -> list[File]:
        return await FileDao.list_recent(db, limit=limit)

    @classmethod
    async def download_and_attach(
        cls,
        db: AsyncSession,
        unified: UnifiedMessage,
        raw: dict[str, Any],
        downloader: WeChatFileDownloader,
        storage: StorageConfig,
    ) -> File | None:
        if unified.type not in {MessageType.IMAGE, MessageType.FILE}:
            return None

        existing = await FileDao.get_by_source_msgid(
            db, unified.source, unified.source_message_id
        )
        if existing is not None:
            return existing

        original_name = unified.content.file_name or f'{unified.source_message_id}.bin'
        rel_path = relative_path(unified.source, original_name, date_subdir=storage.file_date_subdir)
        abs_path = unique_path(storage.storage_dir, rel_path)

        file_row = File(
            id=uuid.uuid4().hex,
            source=unified.source,
            source_message_id=unified.source_message_id,
            message_id=unified.id,
            original_name=original_name,
            mime_type=unified.content.mime_type,
            size=0,
            path=str(abs_path.relative_to(storage.storage_dir)),
            storage_backend='local',
            status='pending',
        )
        db.add(file_row)
        await db.flush()

        result = await downloader.download(unified.type, raw)
        if not result.success:
            file_row.status = 'failed'
            file_row.error = result.error or 'unknown'
            logger.warning(
                f'[file] download failed source={unified.source} '
                f'msg={unified.source_message_id} error={result.error}'
            )
            return file_row

        try:
            abs_path.write_bytes(result.content or b'')
            file_row.size = len(result.content or b'')
            file_row.status = 'downloaded'
            file_row.error = None
        except OSError as exc:
            file_row.status = 'failed'
            file_row.error = f'write failed: {exc}'
            logger.warning(f'[file] write failed: {exc}')

        await MessageDao.update_status(db, unified.id, status='downloaded', file_id=file_row.id)

        logger.info(
            f'[file] downloaded id={file_row.id} path={file_row.path} size={file_row.size}'
        )
        return file_row
