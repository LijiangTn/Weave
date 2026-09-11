"""
WeChatConnector

把 WeChatProtocol（HTTP 协议）+ WeChatSessionStore（DB 持久化）+ WeChatSyncWorker（后台循环）
粘合成对外的 BaseConnector。
"""

import time
from collections import deque
from typing import Any, Awaitable, Callable

from config.env import AppConfig
from config.env import StorageConfig, WechatConfig
from connectors.wechat.normalizer import WeChatNormalizer
from connectors.wechat.protocol import WeChatProtocol
from connectors.wechat.session import WeChatSessionStore
from connectors.wechat.sync_state import SyncStateRepo
from connectors.wechat.sync_worker import WeChatSyncCallbacks, WeChatSyncWorker
from module_api.v1.entity.vo.message_vo import UnifiedMessage
from utils.connector_runtime import BaseConnector, ConnectorState
from utils.domain_events import ConnectorStateEvent, MessageReceivedEvent
from utils.event_bus import event_bus
from utils.log_util import logger

MessageHandler = Callable[[UnifiedMessage], Awaitable[None]]

################################# 对外 Connector 聚合层 #################################
class WeChatConnector(BaseConnector):
    source = 'wechat'

    def __init__(
        self,
        *,
        config: WechatConfig,
        storage: StorageConfig,
        sync_state_repo: SyncStateRepo,
        normalizer: WeChatNormalizer | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.storage = storage
        self.session_store = WeChatSessionStore(sync_state_repo)
        self.normalizer: WeChatNormalizer = normalizer or WeChatNormalizer()

        self.protocol = WeChatProtocol(
            entry_host=config.wechat_entry_host,
            mmweb_appid=config.wechat_mmweb_appid,
            to_user_name=config.wechat_to_user_name,
            lang=config.wechat_lang,
        )
        self.sync_worker: WeChatSyncWorker | None = None
        self._last_login_message = 'init'
        self._has_session_loaded = False
        # ponytail: bounded deque + set dedup; upgrade to Redis Set for multi-process
        self._seen_msg_ids: deque[str] = deque(maxlen=5000)
        self._seen_msg_set: set[str] = set()
        self._message_cache: deque[dict[str, Any]] = deque(maxlen=200)
        self._on_message: MessageHandler | None = None

    def set_message_handler(self, handler: MessageHandler) -> None:
        self._on_message = handler

    ################################# 生命周期与登录查询 #################################
    async def start(self) -> None:
        """启动 connector：加载历史 session、创建后台 worker。"""
        if self.state not in {ConnectorState.STOPPED, ConnectorState.DISCONNECTED, ConnectorState.ERROR}:
            return
        self._set_state(ConnectorState.STARTING)

        await self.protocol.open()

        if not self._has_session_loaded:
            stored = await self.session_store.load()
            if stored is not None and stored.device_id:
                self.protocol.bind_session(stored)
                self.protocol.restore_cookies(stored.cookies)
                self._has_session_loaded = True
                logger.info(f'[wechat] session restored (has_auth={stored.has_auth()})')

        if not self.protocol.session.device_id:
            from connectors.wechat.protocol import gen_device_id

            self.protocol.session.device_id = gen_device_id()
            await self.session_store.save(self.protocol.session)

        callbacks = WeChatSyncCallbacks(
            on_state=self._on_state_change,
            on_login_success=self._on_login_success,
            on_login_expired=self._on_login_expired,
            on_heartbeat=self._on_heartbeat,
            on_message=self._on_raw_message,
        )
        self.sync_worker = WeChatSyncWorker(
            protocol=self.protocol,
            session_store=self.session_store,
            callbacks=callbacks,
            config=self.config,
        )
        self.sync_worker.start()

        if self.protocol.session.has_auth():
            self._set_state(ConnectorState.CONNECTED)
            self._is_logged_in = True
        else:
            self._set_state(ConnectorState.WAITING_QR)

    async def stop(self) -> None:
        if self.sync_worker is not None:
            await self.sync_worker.stop()
            self.sync_worker = None
        if self.protocol.client is not None:
            self.protocol.session.cookies = self.protocol.capture_cookies()
            try:
                await self.session_store.save(self.protocol.session)
            except Exception as exc:
                logger.warning(f'[wechat] save session on stop failed: {exc}')
        await self.protocol.close()
        self._is_logged_in = False
        self._set_state(ConnectorState.STOPPED)

    async def get_qr(self) -> bytes:
        await self._ensure_protocol_ready()
        try:
            png = await self.protocol.get_login_qr()
        except Exception as exc:
            self._record_error(f'get_qr failed: {exc}')
            raise
        if png:
            self._set_state(ConnectorState.QR_READY)
        return png

    async def get_login_status(self) -> dict[str, Any]:
        await self._ensure_protocol_ready()
        logged = self.protocol.session.has_auth()
        trace = self.protocol.get_trace_status()
        return {
            'logged_in': self._is_logged_in,
            'code': 200 if self._is_logged_in else 0,
            'status': self._last_login_message,
            'has_auth': logged,
            'state': self.state.value,
            'message': self._last_login_message,
            'has_uuid': bool(self.protocol.session.uuid),
            'uuid': self.protocol.session.uuid,
            'uuid_age_seconds': (
                int(time.time() - self.protocol.session.uuid_ts)
                if self.protocol.session.uuid_ts
                else None
            ),
            'entry_host': self.protocol.entry_host,
            'login_host': self.protocol.login_host,
            'trace_enabled': trace.get('enabled', False),
            'trace_file': trace.get('file', ''),
            'last_error': self.last_error,
        }

    async def check_login_status(self, poll: bool = True) -> bool:
        await self._ensure_protocol_ready()
        logged_in = self.protocol.session.has_auth()
        self._is_logged_in = logged_in
        if logged_in:
            if self._last_login_message in {'init', 'waiting for qr', 'qr_ready', 'login_expired'}:
                self._last_login_message = 'logged_in' if poll else 'logged_in_cached'
            if self.state != ConnectorState.CONNECTED:
                self._set_state(ConnectorState.CONNECTED)
            return True
        if not self.protocol.session.uuid:
            self._last_login_message = 'need_qr'
        return False

    ################################# 消息缓存与发送接口 #################################
    async def get_latest_messages(self, limit: int = 10) -> list[dict[str, Any]]:
        if not self.is_logged_in:
            if not await self.check_login_status(poll=True):
                return []
        elif not self.protocol.session.has_auth():
            self._is_logged_in = False
            return []
        if limit <= 0:
            return []
        return list(self._message_cache)[-limit:]

    async def save_session(self) -> bool:
        await self._ensure_protocol_ready()
        self.protocol.session.cookies = self.protocol.capture_cookies()
        await self.session_store.save(self.protocol.session)
        return True

    async def send_text(self, message: str) -> bool:
        await self._ensure_protocol_ready()
        if not self.protocol.session.has_auth():
            return False
        return await self.protocol.send_text(message)

    async def send_file(self, file_path: str) -> bool:
        await self._ensure_protocol_ready()
        if not self.protocol.session.has_auth():
            return False
        return await self.protocol.send_file(file_path)

    ################################# Trace 透传 #################################
    def get_trace_status(self) -> dict[str, Any]:
        return self.protocol.get_trace_status()

    async def read_recent_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        await self._ensure_protocol_ready()
        return await self.protocol.read_recent_traces(limit=limit)

    async def clear_traces(self) -> bool:
        await self._ensure_protocol_ready()
        return await self.protocol.clear_traces()

    ################################# 内部辅助与 worker 回调 #################################
    async def _ensure_protocol_ready(self) -> None:
        if self.protocol.client is None:
            await self.protocol.open()
            if not self._has_session_loaded:
                stored = await self.session_store.load()
                if stored is not None and stored.device_id:
                    self.protocol.bind_session(stored)
                    self.protocol.restore_cookies(stored.cookies)
                self._has_session_loaded = True

    # ---------- callbacks ----------

    async def _on_state_change(self, state: ConnectorState, message: str | None) -> None:
        if message:
            self._last_login_message = message
        self._set_state(state)
        await event_bus.publish(
            ConnectorStateEvent(source=self.source, state=state.value, detail={'message': message or ''})
        )

    async def _on_login_success(self) -> None:
        self._is_logged_in = True
        self._last_login_message = 'logged_in'
        self._set_state(ConnectorState.CONNECTED)
        await event_bus.publish(
            ConnectorStateEvent(source=self.source, state=ConnectorState.CONNECTED.value)
        )

    async def _on_login_expired(self) -> None:
        self._is_logged_in = False
        self._last_login_message = 'login_expired'
        self._record_error('login expired')
        self._set_state(ConnectorState.RECONNECTING)
        await event_bus.publish(
            ConnectorStateEvent(
                source=self.source,
                state=ConnectorState.RECONNECTING.value,
                detail={'reason': 'login_expired'},
            )
        )

    def _on_heartbeat(self) -> None:
        self._touch_heartbeat()

    async def _on_raw_message(self, raw: dict[str, Any]) -> None:
        """归一化 + 业务回调 + EventBus 广播"""
        self._touch_message()
        msg_id = str(raw.get('MsgId') or '')
        if not msg_id:
            return

        # 内存去重（第二道防线在 DB UniqueConstraint）
        if msg_id in self._seen_msg_set:
            return
        self._seen_msg_set.add(msg_id)
        self._seen_msg_ids.append(msg_id)
        if len(self._seen_msg_set) > len(self._seen_msg_ids) + 200:
            self._seen_msg_set = set(self._seen_msg_ids)

        # 过滤：仅保留与 filehelper 相关的消息
        from_user = raw.get('FromUserName', '')
        to_user = raw.get('ToUserName', '')
        if from_user != self.config.wechat_to_user_name and to_user != self.config.wechat_to_user_name:
            return

        unified = self.normalizer.normalize(raw)
        if unified is None:
            return
        self._message_cache.append(self._to_cached_message(unified))

        if self._on_message is not None:
            try:
                await self._on_message(unified)
            except Exception as exc:
                logger.warning(f'[wechat] on_message handler error: {exc}')

        await event_bus.publish(
            MessageReceivedEvent(source=self.source, message_id=unified.id)
        )

    ################################# 框架兼容输出与缓存转换 #################################
    def framework_state(self) -> dict[str, Any]:
        return {
            'server_label': AppConfig.app_name,
            'chat_enabled': False,
            'chat_webhook_enabled': False,
            'message_webhook_enabled': False,
            'uptime_seconds': 0,
            'task_count': 0,
            'enabled_task_count': 0,
            'plugins': {'loaded': [], 'count': 0},
            'message_store': {},
        }

    @staticmethod
    def _to_cached_message(unified: UnifiedMessage) -> dict[str, Any]:
        if unified.type == 'text':
            return {
                'id': unified.source_message_id,
                'type': 'text',
                'text': unified.content.text or '',
                'is_mine': False,
            }
        if unified.type == 'image':
            return {
                'id': unified.source_message_id,
                'type': 'image',
                'text': '[Image]',
                'file_name': unified.content.file_name or f'img_{unified.source_message_id}.jpg',
                'is_mine': False,
            }
        if unified.type == 'file':
            file_name = unified.content.file_name or f'file_{unified.source_message_id}'
            return {
                'id': unified.source_message_id,
                'type': 'file',
                'text': f'[File: {file_name}]',
                'file_name': file_name,
                'is_mine': False,
            }
        return {
            'id': unified.source_message_id,
            'type': str(unified.type),
            'text': unified.content.text or '',
            'is_mine': False,
        }
