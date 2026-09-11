"""
连接器同步状态持久化模型

每个连接器（如 wechat）通过 (source, key) 维度在 sync_state 表保存运行期状态，
用以替代原来的 state.json 文件。多副本部署时可水平扩展，避免文件锁竞争。
"""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import Base

################################# 同步状态 ORM 模型 #################################
class SyncState(Base):
    """
    同步状态键值表

    - source: 连接器来源标识，如 "wechat"
    - key: 状态键名，如 "session" / "synckey" / "uuid"
    - value: JSON 序列化的值
    """

    __tablename__ = 'sync_state'

    source = Column(String(32), primary_key=True)
    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

################################# 同步状态仓库 #################################
class SyncStateRepo:
    """
    同步状态仓库（按 source 隔离）
    """

    def __init__(self, db: AsyncSession, source: str) -> None:
        self.db = db
        self.source = source

    async def get_json(self, key: str, default: dict[str, Any] | None = None) -> dict[str, Any] | None:
        row = await self._get(key)
        if row is None or row.value is None:
            return default
        try:
            return json.loads(row.value)
        except json.JSONDecodeError:
            return default

    async def set_json(self, key: str, value: dict[str, Any]) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        existing = await self._get(key)
        if existing is None:
            self.db.add(SyncState(source=self.source, key=key, value=payload))
        else:
            existing.value = payload
            existing.updated_at = datetime.utcnow()
        await self.db.commit()

    async def delete(self, key: str) -> None:
        existing = await self._get(key)
        if existing is not None:
            await self.db.delete(existing)
            await self.db.commit()

    async def all_keys(self) -> list[str]:
        from sqlalchemy import select

        result = await self.db.execute(
            select(SyncState.key).where(SyncState.source == self.source)
        )
        return [row[0] for row in result.all()]

    async def _get(self, key: str) -> SyncState | None:
        from sqlalchemy import select

        result = await self.db.execute(
            select(SyncState).where(SyncState.source == self.source, SyncState.key == key)
        )
        return result.scalar_one_or_none()