"""
接口请求与返回模型
"""

from typing import Any

from pydantic import BaseModel, Field


class SendMessagePayload(BaseModel):
    text: str = Field(min_length=1)
    chat_id: str | int | None = None
    reply_to_message_id: str | int | None = None
    parse_mode: str | None = None
    disable_notification: bool = False


class SendDocumentPayload(BaseModel):
    document: str | None = None
    file_path: str | None = None
    chat_id: str | int | None = None
    reply_to_message_id: str | int | None = None
    caption: str | None = None


class SendPhotoPayload(BaseModel):
    photo: str | None = None
    file_path: str | None = None
    chat_id: str | int | None = None
    reply_to_message_id: str | int | None = None
    caption: str | None = None


class CopyMessagePayload(BaseModel):
    chat_id: str | int | None = None
    from_chat_id: str | int | None = None
    message_id: str | int


class RootSendPayload(BaseModel):
    content: str


class ChatModePayload(BaseModel):
    enabled: bool


class TaskCreatePayload(BaseModel):
    time_hm: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    command: str = Field(min_length=1)
    description: str = ''


class TaskEnabledPayload(BaseModel):
    enabled: bool


class ExecutePayload(BaseModel):
    command: str = Field(min_length=1)
    send_back: bool = False


def ok_result(result: Any) -> dict[str, Any]:
    return {'ok': True, 'result': result}


def error_result(error_code: int, description: str) -> dict[str, Any]:
    return {'ok': False, 'error_code': error_code, 'description': description}
