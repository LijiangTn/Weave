"""
健康检查 DAO
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class HealthDao:
    @classmethod
    async def ping(cls, db: AsyncSession) -> None:
        await db.execute(text('SELECT 1'))