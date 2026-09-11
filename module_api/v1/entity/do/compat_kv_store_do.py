"""
键值表 ORM
"""

from sqlalchemy import Column, Integer, String, Text

from config.database import Base


class CompatKvStore(Base):
    __tablename__ = 'kv_store'

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(Integer, nullable=True)
