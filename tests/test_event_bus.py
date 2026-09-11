"""
EventBus 内存实现冒烟测试
"""

import asyncio

from utils.domain_events import ConnectorStateEvent
from utils.event_bus import InMemoryEventBus

async def _h(e):
    _h.calls.append(e)

async def test_publish_and_subscribe():
    bus = InMemoryEventBus()
    _h.calls = []
    await bus.subscribe('connector.state_changed', _h)

    await bus.publish(ConnectorStateEvent(source='wechat', state='connected'))
    await asyncio.sleep(0)
    assert len(_h.calls) == 1
    assert _h.calls[0].source == 'wechat'

async def test_wildcard_subscribe():
    bus = InMemoryEventBus()
    received: list[str] = []

    async def h(e):
        received.append(e.type)

    await bus.subscribe('*', h)
    await bus.publish(ConnectorStateEvent(source='wechat', state='connected'))
    await asyncio.sleep(0)
    assert received == ['connector.state_changed']
