"""
消息存储 ORM
"""

from sqlalchemy import Column, Index, Integer, String, Text

from config.database import Base


class CompatMessage(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    msg_id = Column(String(128), unique=True, nullable=False)
    type = Column(String(32), nullable=False)
    text = Column(Text, nullable=True)
    is_mine = Column(Integer, default=0)
    timestamp = Column(Integer, nullable=False)
    file_name = Column(String(255), nullable=True)
    file_path = Column(String(1024), nullable=True)
    file_size = Column(Integer, nullable=True)
    reply_to_id = Column(String(128), nullable=True)
    raw_data = Column(Text, nullable=True)
    extra = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_messages_msg_id', 'msg_id'),
        Index('idx_messages_timestamp', 'timestamp'),
        Index('idx_messages_type', 'type'),
    )
