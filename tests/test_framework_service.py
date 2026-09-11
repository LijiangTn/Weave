"""
框架运行时测试
"""

import pytest

from module_api.v1.service.framework_service import FrameworkService


def test_framework_task_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(FrameworkService, '_task_file', tmp_path / 'framework_tasks.json')
    FrameworkService._tasks = {}

    task = FrameworkService.add_task('09:30', 'ping', 'demo')
    task_id = task['task_id']
    assert FrameworkService.list_tasks()[0]['task_id'] == task_id

    assert FrameworkService.set_task_enabled(task_id, False) is True
    assert FrameworkService.list_tasks()[0]['enabled'] is False

    assert FrameworkService.delete_task(task_id) is True
    assert FrameworkService.list_tasks() == []


@pytest.mark.asyncio
async def test_framework_execute_ping():
    result = await FrameworkService.execute_command_text('ping', object())
    assert result == 'Pong!'


@pytest.mark.asyncio
async def test_framework_execute_plugins_returns_legacy_style_text():
    result = await FrameworkService.execute_command_text('/plugins', object())
    assert '已加载: 3 个插件' in result
    assert '插件列表: builtin, framework_api, webui' in result


@pytest.mark.asyncio
async def test_framework_debug_snapshot_contains_runtime_info(monkeypatch):
    async def fake_get_login_status(connector):
        return {'logged_in': False, 'status': 'need_qr'}

    async def fake_get_trace_status(connector):
        return {'enabled': True, 'file': 'trace.jsonl'}

    async def fake_read_recent_traces(connector, limit=20):
        return [{'id': '1'}]

    monkeypatch.setattr(
        'module_api.v1.service.framework_service.WechatService.get_login_status',
        fake_get_login_status,
    )
    monkeypatch.setattr(
        'module_api.v1.service.framework_service.WechatService.get_trace_status',
        fake_get_trace_status,
    )
    monkeypatch.setattr(
        'module_api.v1.service.framework_service.WechatService.read_recent_traces',
        fake_read_recent_traces,
    )

    payload = await FrameworkService.get_debug_snapshot(object())
    assert payload['mode'] == 'direct_protocol'
    assert payload['recent_traces'] == [{'id': '1'}]
