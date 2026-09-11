"""
文件 Pydantic 模型
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

################################# 请求体实例 #################################

################################# 响应体实例 #################################
class FileResponse(BaseModel):
    """
    文件元信息响应
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description='文件 ID')
    source: str = Field(..., description='来源')
    source_message_id: str = Field(..., description='来源消息 ID')
    message_id: str | None = Field(None, description='关联消息 ID')
    original_name: str = Field(..., description='原始文件名')
    mime_type: str | None = Field(None, description='MIME 类型')
    size: int = Field(..., description='文件大小（字节）')
    path: str = Field(..., description='存储路径（相对 storage_dir）')
    storage_backend: str = Field(..., description='存储后端')
    status: str = Field(..., description='pending/downloaded/failed')
    error: str | None = Field(None, description='失败原因')
    created_at: datetime = Field(..., description='创建时间')
    updated_at: datetime = Field(..., description='更新时间')