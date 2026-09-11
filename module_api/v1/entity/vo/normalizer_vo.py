"""
Normalizer 协议（数据契约层）

每个 connector 提供一个 Normalizer，把 source 原始消息转换为 UnifiedMessage。
返回 None 表示该消息不属于本 connector 处理范围（应跳过）。
"""

from abc import ABC, abstractmethod

from module_api.v1.entity.vo.message_vo import UnifiedMessage

class BaseNormalizer(ABC):
    """所有 Normalizer 必须实现 normalize。"""

    source: str = ''

    @abstractmethod
    def normalize(self, raw: dict) -> UnifiedMessage | None:
        """raw 为 connector 给出的原始消息 dict；返回 None 表示丢弃。"""