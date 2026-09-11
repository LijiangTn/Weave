"""
测试 fixtures：内存 SQLite 异步会话，规避对真实 MySQL/PG 的依赖。
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import config.models  # noqa: F401  注册所有 ORM
from config.database import Base

@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    await engine.dispose()