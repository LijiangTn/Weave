"""
根接口控制器
"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from config.get_db import get_db
from module_api.v1.entity.vo.compat_vo import RootSendPayload
from module_api.v1.service.connector_service import get_wechat_connector
from module_api.v1.service.root_service import RootService
from module_api.v1.service.wechat_service import WechatService
from utils.connector_runtime import BaseConnector

rootController = APIRouter(tags=['Root'])


@rootController.get(path='/', summary='服务状态')
async def root_status(
    db: AsyncSession = Depends(get_db),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    return await RootService.get_root_status(db, connector)


@rootController.get(path='/qr', summary='二维码')
async def get_qr(connector: BaseConnector = Depends(get_wechat_connector)):
    try:
        png_bytes = await WechatService.get_qr(connector)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if not png_bytes:
        return Response(content='Already logged in', media_type='text/plain')
    return Response(content=png_bytes, media_type='image/png')


@rootController.get(path='/login/status', summary='登录状态')
async def login_status(
    auto_poll: bool = Query(default=True),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    return await RootService.get_login_status(connector, auto_poll=auto_poll)


@rootController.get(path='/messages', summary='最近消息')
async def messages(
    limit: int = 10,
    connector: BaseConnector = Depends(get_wechat_connector),
):
    return await RootService.list_messages(connector, limit)


@rootController.post(path='/save_session', summary='保存会话')
async def save_session(connector: BaseConnector = Depends(get_wechat_connector)):
    return await RootService.save_session(connector)


@rootController.post(path='/send', summary='发送文本')
async def send(
    payload: RootSendPayload,
    connector: BaseConnector = Depends(get_wechat_connector),
):
    try:
        return await RootService.send_text(connector, payload.content)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@rootController.post(path='/upload', summary='上传并发送文件')
async def upload(
    file: UploadFile = File(...),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    try:
        return await RootService.upload_file(connector, file.filename, file.file)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
