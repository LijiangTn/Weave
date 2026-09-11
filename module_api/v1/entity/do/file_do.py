"""
文件 ORM
"""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Index, String, Text

from config.database import Base

class File(Base):
    __tablename__ = 'file'

    id = Column(String(36), primary_key=True)
    source = Column(String(32), nullable=False)
    source_message_id = Column(String(64), nullable=False)
    message_id = Column(String(36), nullable=True)
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(128), nullable=True)
    size = Column(BigInteger, default=0)
    path = Column(String(512), nullable=False)
    storage_backend = Column(String(16), default='local')
    status = Column(String(16), default='pending')
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_file_source_msgid', 'source', 'source_message_id'),
        Index('ix_file_status', 'status'),
    )