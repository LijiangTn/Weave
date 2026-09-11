"""
文件 DAO
"""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from module_api.v1.entity.do.file_do import File

class FileDao:
    @classmethod
    async def get_by_id(cls, db: AsyncSession, file_id: str) -> File | None:
        result = await db.execute(select(File).where(File.id == file_id))
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_source_msgid(
        cls, db: AsyncSession, source: str, source_message_id: str
    ) -> File | None:
        result = await db.execute(
            select(File).where(
                File.source == source, File.source_message_id == source_message_id
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    async def create(cls, db: AsyncSession, file: File) -> File:
        db.add(file)
        await db.flush()
        return file

    @classmethod
    async def update_status(
        cls,
        db: AsyncSession,
        file_id: str,
        *,
        status: str | None = None,
        size: int | None = None,
        error: str | None = None,
        path: str | None = None,
    ) -> None:
        f = await cls.get_by_id(db, file_id)
        if f is None:
            return
        if status is not None:
            f.status = status
        if size is not None:
            f.size = size
        if error is not None:
            f.error = error
        if path is not None:
            f.path = path
        await db.commit()

    @classmethod
    async def list_recent(cls, db: AsyncSession, limit: int = 100) -> list[File]:
        result = await db.execute(select(File).order_by(desc(File.created_at)).limit(limit))
        return list(result.scalars().all())