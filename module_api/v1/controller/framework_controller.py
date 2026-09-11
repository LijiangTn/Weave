"""
框架与插件控制器
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from config.get_db import get_db
from module_api.v1.entity.vo.compat_vo import (
    ChatModePayload,
    ExecutePayload,
    TaskCreatePayload,
    TaskEnabledPayload,
)
from module_api.v1.service.connector_service import get_wechat_connector
from module_api.v1.service.framework_service import FrameworkService
from module_api.v1.service.wechat_extension_service import WechatExtensionService
from module_api.v1.service.wechat_service import WechatService
from utils.connector_runtime import BaseConnector

frameworkController = APIRouter(tags=['Framework'])


@frameworkController.get('/framework/state')
async def framework_state(
    db: AsyncSession = Depends(get_db),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    stats = await FrameworkService.get_message_store_stats(db)
    return await FrameworkService.get_state(connector, stats)


@frameworkController.post('/framework/chat_mode')
async def framework_set_chat_mode(payload: ChatModePayload):
    FrameworkService.set_chat_mode(payload.enabled)
    return {'status': 'ok', 'enabled': payload.enabled}


@frameworkController.post('/framework/execute')
async def framework_execute(
    payload: ExecutePayload,
    connector: BaseConnector = Depends(get_wechat_connector),
):
    result = await FrameworkService.execute_command_text(payload.command, connector, source='api_execute')
    if payload.send_back and result and await WechatService.check_login_status(connector, poll=False):
        await WechatService.send_text(connector, result)
    return {'status': 'ok', 'command': payload.command, 'result': result}


@frameworkController.get('/framework/tasks')
async def framework_tasks():
    return {'tasks': FrameworkService.list_tasks()}


@frameworkController.post('/framework/tasks')
async def framework_add_task(payload: TaskCreatePayload):
    try:
        task = FrameworkService.add_task(
            time_hm=payload.time_hm,
            command_text=payload.command,
            description=payload.description,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {'status': 'ok', 'task': task}


@frameworkController.delete('/framework/tasks/{task_id}')
async def framework_delete_task(task_id: str):
    ok = FrameworkService.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail='task not found')
    return {'status': 'deleted', 'task_id': task_id}


@frameworkController.post('/framework/tasks/{task_id}/enabled')
async def framework_set_task_enabled(task_id: str, payload: TaskEnabledPayload):
    ok = FrameworkService.set_task_enabled(task_id, payload.enabled)
    if not ok:
        raise HTTPException(status_code=404, detail='task not found')
    return {'status': 'ok', 'task_id': task_id, 'enabled': payload.enabled}


@frameworkController.post('/framework/tasks/{task_id}/run')
async def framework_run_task(
    task_id: str,
    connector: BaseConnector = Depends(get_wechat_connector),
):
    ok = await FrameworkService.run_task_now(connector, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail='task not found')
    return {'status': 'ok', 'task_id': task_id, 'trigger': 'manual'}


@frameworkController.get('/plugins')
async def list_plugins():
    return FrameworkService.list_plugins()


@frameworkController.post('/plugins/reload')
async def reload_plugins():
    return FrameworkService.reload_plugins()


@frameworkController.get('/health')
async def health_check(connector: BaseConnector = Depends(get_wechat_connector)):
    return await FrameworkService.health_check(connector)


@frameworkController.get('/stability')
async def stability_status(connector: BaseConnector = Depends(get_wechat_connector)):
    return FrameworkService.stability_status(connector)


@frameworkController.get('/trace/status')
async def trace_status(connector: BaseConnector = Depends(get_wechat_connector)):
    return await WechatExtensionService.get_trace_status(connector)


@frameworkController.get('/trace/recent')
async def trace_recent(
    limit: int = 100,
    connector: BaseConnector = Depends(get_wechat_connector),
):
    return await WechatExtensionService.read_recent_traces(connector, limit)


@frameworkController.post('/trace/clear')
async def trace_clear(connector: BaseConnector = Depends(get_wechat_connector)):
    return await WechatExtensionService.clear_traces(connector)


@frameworkController.get('/debug_html')
async def debug_html(connector: BaseConnector = Depends(get_wechat_connector)):
    payload = await FrameworkService.get_debug_snapshot(connector)
    return Response(
        content=json.dumps(payload, ensure_ascii=False),
        media_type='application/json',
    )
