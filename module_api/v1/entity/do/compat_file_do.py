"""
文件元数据 ORM
"""

from sqlalchemy import Column, Index, Integer, String

from config.database import Base


class CompatFile(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True, autoincrement=True)
    msg_id = Column(String(128), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(255), nullable=True)
    md5 = Column(String(64), nullable=True)
    created_at = Column(Integer, nullable=False)
    downloaded = Column(Integer, default=1)

    __table_args__ = (
        Index('idx_files_msg_id', 'msg_id'),
        Index('idx_files_created_at', 'created_at'),
    )
