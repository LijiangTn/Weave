"""
消息相关 Pydantic 模型

包含：
- 跨 connector 的 Unified Message 数据契约（MessageType / MessageContent / MessageParty / UnifiedMessage）
- 业务响应 MessageResponse
"""
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

################################# 请求体实例 #################################
class MessageType(str, Enum):
    TEXT = 'text'
    IMAGE = 'image'
    FILE = 'file'
    AUDIO = 'audio'
    VIDEO = 'video'
    LINK = 'link'
    SYSTEM = 'system'
    UNKNOWN = 'unknown'

class MessageContent(BaseModel):
    """
    消息内容（按 type 取相应字段）
    """

    text: str | None = Field(None, description='文本内容')
    file_name: str | None = Field(None, description='文件名')
    file_size: int | None = Field(None, description='文件大小（字节）')
    mime_type: str | None = Field(None, description='MIME 类型')
    file_id: str | None = Field(None, description='已落盘文件 ID')
    url: str | None = Field(None, description='链接 URL')

class MessageParty(BaseModel):
    """
    发送方 / 接收方描述
    """

    id: str = Field(..., description='用户标识')
    name: str | None = Field(None, description='显示名')
    type: str | None = Field(None, description='类型 user/bot/system')

class UnifiedMessage(BaseModel):
    """
    业务消息契约（跨 connector 标准）

    - id: 业务 ID（uuid4 hex），全局唯一，用于幂等关联
    - source: 来源标识（wechat / telegram / ...）
    - source_message_id: 来源侧的原始 ID；与 source 组成数据库唯一约束
    - event_id: 同步事件 ID（可空），用于追溯同步位置
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, description='业务 ID')
    source: str = Field(..., description='来源标识')
    source_message_id: str = Field(..., description='来源原始 ID')
    event_id: str | None = Field(None, description='同步事件 ID')
    type: MessageType = Field(..., description='消息类型')
    content: MessageContent = Field(default_factory=MessageContent, description='消息内容')
    sender: MessageParty | None = Field(None, description='发送方')
    receiver: MessageParty | None = Field(None, description='接收方')
    timestamp: int = Field(..., description='Unix 秒时间戳')
    metadata: dict[str, Any] = Field(default_factory=dict, description='扩展元数据')

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

################################# 响应体实例 #################################
class MessageResponse(BaseModel):
    """
    消息详情响应（ORM → VO）

    ORM 字段 *_json 存 JSON 字符串，这里在 model_validator(mode='before') 里手动反序列化。
    不用 @property 是因为 `metadata` 与 SQLAlchemy `Base.metadata` 冲突；
    也不用 from_attributes 直读 *_json 是因为响应需要结构化对象而非裸字符串。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description='业务 ID')
    source: str = Field(..., description='来源标识')
    source_message_id: str = Field(..., description='来源原始 ID')
    event_id: str | None = Field(None, description='同步事件 ID')
    type: MessageType = Field(..., description='消息类型')
    content: MessageContent = Field(..., description='消息内容')
    sender: MessageParty | None = Field(None, description='发送方')
    receiver: MessageParty | None = Field(None, description='接收方')
    timestamp: int = Field(..., description='Unix 秒时间戳')
    metadata: dict[str, Any] = Field(default_factory=dict, description='扩展元数据')
    status: str = Field(..., description='received/downloaded/failed')
    created_at: datetime = Field(..., description='入库时间')
    updated_at: datetime = Field(..., description='更新时间')

    @model_validator(mode='before')
    @classmethod
    def parse_orm(cls, data: Any) -> Any:
        # ORM Message 对象有 *_json 字段；dict 输入直接走默认字段映射
        if hasattr(data, 'content_json'):
            return {
                'id': data.id,
                'source': data.source,
                'source_message_id': data.source_message_id,
                'event_id': data.event_id,
                'type': data.type,
                'content': MessageContent.model_validate_json(data.content_json) if data.content_json else MessageContent(),
                'sender': MessageParty.model_validate_json(data.sender_json) if data.sender_json else None,
                'receiver': MessageParty.model_validate_json(data.receiver_json) if data.receiver_json else None,
                'timestamp': data.timestamp,
                'metadata': json.loads(data.metadata_json) if data.metadata_json else {},
                'status': data.status,
                'created_at': data.created_at,
                'updated_at': data.updated_at,
            }
        return data