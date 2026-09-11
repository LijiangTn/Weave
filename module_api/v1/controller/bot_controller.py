"""
Telegram Bot API 控制器
"""

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from config.get_db import get_db
from module_api.v1.entity.vo.compat_vo import (
    CopyMessagePayload,
    SendDocumentPayload,
    SendMessagePayload,
    SendPhotoPayload,
    error_result,
)
from module_api.v1.service.bot_api_service import BotApiService
from module_api.v1.service.connector_service import get_wechat_connector
from utils.connector_runtime import BaseConnector

botController = APIRouter(prefix='/bot', tags=['Telegram Bot API'])


@botController.get('/getUpdates')
async def get_updates(
    offset: int = Query(default=0),
    limit: int = Query(default=100, ge=1, le=100),
    timeout: int = Query(default=0),
    allowed_updates: list[str] | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    del timeout, allowed_updates
    return await BotApiService.get_updates(db, offset=offset, limit=limit)


@botController.get('/getMe')
async def get_me(connector: BaseConnector = Depends(get_wechat_connector)):
    return BotApiService.get_me(connector)


@botController.get('/getChat')
async def get_chat(
    chat_id: str | int | None = Query(default=None),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    del chat_id
    return BotApiService.get_chat(connector)


@botController.get('/getFile')
async def get_file(file_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    return await BotApiService.get_file(db, file_id)


@botController.post('/setWebhook')
async def set_webhook(
    url: str = '',
    certificate: str | None = None,
    ip_address: str | None = None,
    max_connections: int = 40,
    allowed_updates: list[str] | None = None,
    drop_pending_updates: bool = False,
    secret_token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    del certificate, ip_address, max_connections, allowed_updates, drop_pending_updates, secret_token
    return await BotApiService.set_webhook(db, url)


@botController.post('/deleteWebhook')
async def delete_webhook(
    drop_pending_updates: bool = False,
    db: AsyncSession = Depends(get_db),
):
    del drop_pending_updates
    return await BotApiService.delete_webhook(db)


@botController.get('/getWebhookInfo')
async def get_webhook_info(db: AsyncSession = Depends(get_db)):
    return await BotApiService.get_webhook_info(db)


@botController.post('/sendMessage')
async def send_message(
    payload: SendMessagePayload,
    db: AsyncSession = Depends(get_db),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    return await BotApiService.send_text(
        db,
        connector,
        text=payload.text,
        reply_to_message_id=str(payload.reply_to_message_id) if payload.reply_to_message_id else None,
    )


@botController.post('/sendDocument')
async def send_document(
    payload: SendDocumentPayload,
    db: AsyncSession = Depends(get_db),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    file_path = payload.document or payload.file_path
    if not file_path:
        return error_result(400, 'Bad Request: document is required')
    return await BotApiService.send_file(
        db,
        connector,
        file_path=file_path,
        reply_to_message_id=str(payload.reply_to_message_id) if payload.reply_to_message_id else None,
        caption=payload.caption,
    )


@botController.post('/sendDocument/upload')
async def send_document_upload(
    document: UploadFile = File(...),
    chat_id: str | None = Form(default=None),
    caption: str | None = Form(default=None),
    reply_to_message_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    del chat_id
    return await BotApiService.send_uploaded_file(
        db,
        connector,
        filename=document.filename,
        file_obj=document.file,
        reply_to_message_id=reply_to_message_id,
        caption=caption,
    )


@botController.post('/sendPhoto')
async def send_photo(
    payload: SendPhotoPayload,
    db: AsyncSession = Depends(get_db),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    file_path = payload.photo or payload.file_path
    if not file_path:
        return error_result(400, 'Bad Request: photo is required')
    return await BotApiService.send_file(
        db,
        connector,
        file_path=file_path,
        reply_to_message_id=str(payload.reply_to_message_id) if payload.reply_to_message_id else None,
        caption=payload.caption,
    )


@botController.post('/sendPhoto/upload')
async def send_photo_upload(
    photo: UploadFile = File(...),
    chat_id: str | None = Form(default=None),
    caption: str | None = Form(default=None),
    reply_to_message_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    del chat_id
    return await BotApiService.send_uploaded_file(
        db,
        connector,
        filename=photo.filename,
        file_obj=photo.file,
        reply_to_message_id=reply_to_message_id,
        caption=caption,
        default_suffix='.jpg',
    )


@botController.post('/copyMessage')
async def copy_message(
    payload: CopyMessagePayload,
    db: AsyncSession = Depends(get_db),
    connector: BaseConnector = Depends(get_wechat_connector),
):
    return await BotApiService.copy_message(
        db,
        connector,
        message_id=str(payload.message_id),
    )
