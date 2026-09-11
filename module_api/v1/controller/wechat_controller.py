"""
微信扩展控制器
"""

from fastapi import APIRouter, Depends, Query

from module_api.v1.service.connector_service import get_wechat_connector
from module_api.v1.service.wechat_extension_service import WechatExtensionService
from utils.connector_runtime import BaseConnector

wechatController = APIRouter(prefix='/wechat', tags=['WeChat'])


@wechatController.post('/session/save')
async def save_session(connector: BaseConnector = Depends(get_wechat_connector)):
    return await WechatExtensionService.save_session(connector)


@wechatController.get('/trace/status')
async def trace_status(connector: BaseConnector = Depends(get_wechat_connector)):
    return await WechatExtensionService.get_trace_status(connector)


@wechatController.get('/trace/recent')
async def trace_recent(
    limit: int = Query(default=100, ge=1, le=1000),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    return await WechatExtensionService.read_recent_traces(connector, limit=limit)


@wechatController.post('/trace/clear')
async def trace_clear(connector: BaseConnector = Depends(get_wechat_connector)):
    return await WechatExtensionService.clear_traces(connector)
