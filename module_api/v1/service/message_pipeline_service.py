"""
消息处理管道服务
"""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from config.database import AsyncSessionLocal
from config.env import StorageConfig
from module_api.v1.entity.vo.message_vo import MessageType, UnifiedMessage
from module_api.v1.service.file_service import FileService
from module_api.v1.service.message_service import MessageService
from module_api.v1.service.message_store_service import MessageStoreService
from workers.file_downloader import WeChatFileDownloader


class MessagePipelineService:
    @classmethod
    async def handle_incoming_message(
        cls,
        unified: UnifiedMessage,
        downloader: WeChatFileDownloader,
    ) -> None:
        async with AsyncSessionLocal() as session_db:
            await cls._persist_and_dispatch(session_db, unified, downloader)

    @classmethod
    async def _persist_and_dispatch(
        cls,
        db: AsyncSession,
        unified: UnifiedMessage,
        downloader: WeChatFileDownloader,
    ) -> None:
        try:
            saved = await MessageService.persist(db, unified)
            if saved is None:
                return
            raw = unified.metadata.get('raw', {}) if isinstance(unified.metadata, dict) else {}
            stored_message = await MessageStoreService.persist_received_message(
                db,
                unified,
                raw=raw,
            )
            await MessageStoreService.push_webhook_if_needed(db, stored_message)
            if unified.type in {MessageType.IMAGE, MessageType.FILE}:
                stored_file = await FileService.download_and_attach(
                    db,
                    unified,
                    raw,
                    downloader,
                    StorageConfig,
                )
                if stored_file is not None and stored_file.status == 'downloaded':
                    absolute_path = str(Path(StorageConfig.storage_dir) / stored_file.path)
                    await MessageStoreService.persist_downloaded_file(
                        db,
                        unified,
                        file_path=absolute_path,
                        file_size=int(stored_file.size or 0),
                        mime_type=stored_file.mime_type,
                    )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
