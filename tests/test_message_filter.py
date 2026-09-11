"""
过滤器单元测试：Filter 类只解析 query，不直接走 DB。
"""

from module_api.v1.filter.message_filter import MessageFilter

def test_filter_defaults():
    f = MessageFilter()
    assert f.order_by == ['-timestamp']
    assert f.source is None

def test_filter_parses_query():
    f = MessageFilter(source='wechat', type='text', timestamp__gte=100, timestamp__lte=200)
    assert f.source == 'wechat'
    assert f.timestamp__gte == 100