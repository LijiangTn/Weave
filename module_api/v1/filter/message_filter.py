"""
消息过滤器
"""

from typing import Optional

from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import Field

from module_api.v1.entity.do.message_do import Message

class MessageFilter(Filter):
    source: Optional[str] = Field(None, description='来源')
    type: Optional[str] = Field(None, description='消息类型')
    timestamp__gte: Optional[int] = Field(None, description='时间戳起（Unix 秒）')
    timestamp__lte: Optional[int] = Field(None, description='时间戳止')
    order_by: list[str] = Field(default=['-timestamp'], description='排序字段')

    class Constants(Filter.Constants):
        model = Message
        ordering_field_name = 'order_by'