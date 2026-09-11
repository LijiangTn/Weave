"""
消息 ORM
"""
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Index, String, Text, UniqueConstraint

from config.database import Base


class Message(Base):
    __tablename__ = 'message'

    id = Column(String(36), primary_key=True)
    source = Column(String(32), nullable=False)
    source_message_id = Column(String(64), nullable=False)
    event_id = Column(String(36), nullable=True)
    type = Column(String(16), nullable=False)
    content_json = Column(Text, nullable=False)
    sender_json = Column(Text, nullable=True)
    receiver_json = Column(Text, nullable=True)
    timestamp = Column(BigInteger, nullable=False)
    metadata_json = Column(Text, nullable=True)
    status = Column(String(16), default='received')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('source', 'source_message_id', name='uq_message_source_msgid'),
        Index('ix_message_source_timestamp', 'source', 'timestamp'),
        Index('ix_message_type', 'type'),
    )