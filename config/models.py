"""
模型注册文件
在这里导入所有的数据库模型，确保 SQLAlchemy 能够发现它们
"""

# 导入所有模型类，确保它们注册到 Base.metadata
from module_api.v1.entity.do.message_do import Message
from module_api.v1.entity.do.file_do import File
from module_api.v1.entity.do.compat_message_do import CompatMessage
from module_api.v1.entity.do.compat_file_do import CompatFile
from module_api.v1.entity.do.compat_kv_store_do import CompatKvStore
from connectors.wechat.sync_state import SyncState

__all__ = [
    'SyncState',
    'Message',
    'File',
    'CompatMessage',
    'CompatFile',
    'CompatKvStore',
    # 添加更多模型到这里
]
