"""
WebUI 控制器
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from module_api.v1.service.connector_service import get_wechat_connector
from module_api.v1.service.webui_service import WebUIService
from utils.connector_runtime import BaseConnector

webuiController = APIRouter(tags=['WebUI'])


@webuiController.get('/webui/qr')
async def webui_qr(connector: BaseConnector = Depends(get_wechat_connector)):
    return await WebUIService.get_qr_payload(connector)


@webuiController.get('/webui/status')
async def webui_status(
    poll_login: bool = Query(default=False),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    return await WebUIService.get_status_payload(connector, poll_login=poll_login)


@webuiController.get('/webui')
async def webui_page():
    return HTMLResponse(content=WebUIService.render_page(), status_code=200)
