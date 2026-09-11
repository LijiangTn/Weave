"""
文件与存储服务
"""

import os
import time
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from config.env import StorageConfig
from module_api.v1.dao.compat_message_store_dao import CompatMessageStoreDao
from module_api.v1.service.message_store_service import MessageStoreService


class FileStoreService:
    @classmethod
    def scan_downloads(cls, *, limit: int, include_subdirs: bool) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        root_dir = Path(StorageConfig.storage_dir)
        if not root_dir.exists():
            return {'files': files, 'total': 0, 'base_url': '/static/'}
        if include_subdirs:
            for root, _, filenames in os.walk(root_dir):
                root_path = Path(root)
                for name in filenames:
                    if name.startswith('.'):
                        continue
                    file_path = root_path / name
                    try:
                        stat_info = file_path.stat()
                    except OSError:
                        continue
                    files.append(
                        {
                            'name': name,
                            'path': str(file_path.relative_to(root_dir)),
                            'size': stat_info.st_size,
                            'modified': stat_info.st_mtime,
                        }
                    )
        else:
            for file_path in root_dir.iterdir():
                if not file_path.is_file() or file_path.name.startswith('.'):
                    continue
                try:
                    stat_info = file_path.stat()
                except OSError:
                    continue
                files.append(
                    {
                        'name': file_path.name,
                        'path': file_path.name,
                        'size': stat_info.st_size,
                        'modified': stat_info.st_mtime,
                    }
                )
        files.sort(key=lambda item: item['modified'], reverse=True)
        return {'files': files[:limit], 'total': len(files), 'base_url': '/static/'}

    @classmethod
    async def files_metadata(cls, db: AsyncSession, *, limit: int, offset: int) -> dict[str, Any]:
        files = await MessageStoreService.get_files(db, limit=limit, offset=offset)
        return {'files': files, 'count': len(files)}

    @classmethod
    async def store_stats(cls, db: AsyncSession) -> dict[str, Any]:
        return await MessageStoreService.get_stats(db)

    @classmethod
    async def store_messages(
        cls,
        db: AsyncSession,
        *,
        limit: int,
        offset: int,
        msg_type: str | None,
        since: int | None,
    ) -> dict[str, Any]:
        messages = await MessageStoreService.query_messages(
            db,
            offset=offset,
            limit=limit,
            msg_type=msg_type,
            since=since,
        )
        return {'messages': messages, 'count': len(messages)}

    @classmethod
    async def delete_file(cls, db: AsyncSession, msg_id: str) -> dict[str, Any]:
        file_info = await MessageStoreService.get_file(db, msg_id)
        if not file_info:
            raise FileNotFoundError('File not found')
        path = MessageStoreService.resolve_file_path(file_info['file_path'])
        if path is not None and path.exists():
            path.unlink()
        return {'status': 'deleted', 'msg_id': msg_id}

    @classmethod
    async def cleanup_files(cls, db: AsyncSession, *, days: int) -> dict[str, Any]:
        files = await MessageStoreService.get_files(db, limit=100000, offset=0)
        cutoff = time.time() - days * 86400
        for item in files:
            if item['created_at'] >= cutoff:
                continue
            try:
                path = MessageStoreService.resolve_file_path(item['file_path'])
                if path is not None and path.exists():
                    path.unlink()
            except Exception:
                pass
        deleted_messages = await CompatMessageStoreDao.cleanup_old_messages(db, days=days)
        deleted_files = await CompatMessageStoreDao.cleanup_old_files(db, days=days)
        await db.commit()
        return {'deleted_messages': deleted_messages, 'deleted_files': deleted_files}
