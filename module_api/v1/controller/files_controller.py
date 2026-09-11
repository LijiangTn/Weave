"""
文件与存储控制器
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.get_db import get_db
from module_api.v1.service.file_store_service import FileStoreService

filesController = APIRouter(tags=['Files'])


@filesController.get('/downloads')
async def downloads(
    limit: int = Query(default=100, ge=1, le=1000),
    include_subdirs: bool = Query(default=True),
):
    return FileStoreService.scan_downloads(limit=limit, include_subdirs=include_subdirs)


@filesController.get('/files/metadata')
async def files_metadata(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await FileStoreService.files_metadata(db, limit=limit, offset=offset)


@filesController.get('/store/stats')
async def store_stats(db: AsyncSession = Depends(get_db)):
    return await FileStoreService.store_stats(db)


@filesController.get('/store/messages')
async def store_messages(
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    msg_type: str | None = Query(default=None),
    since: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await FileStoreService.store_messages(
        db,
        limit=limit,
        offset=offset,
        msg_type=msg_type,
        since=since,
    )


@filesController.delete('/files/{msg_id}')
async def delete_file(msg_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await FileStoreService.delete_file(db, msg_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail='File not found')
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Delete failed: {exc}')


@filesController.post('/files/cleanup')
async def cleanup_files(
    days: int = Query(default=30, ge=1),
    db: AsyncSession = Depends(get_db),
):
    return await FileStoreService.cleanup_files(db, days=days)
