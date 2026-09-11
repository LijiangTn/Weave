"""
微信后台同步 worker

- 动态轮询（空闲时拉长间隔）
- 心跳检测（独立协程）
- 自动重连（基于已持久化的 session）
- 检测到掉线时不立刻清理 session，等 re-login 失败才清理
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from config.env import WechatConfig
from connectors.wechat.protocol import WeChatProtocol
from connectors.wechat.session import WeChatSessionStore
from utils.connector_runtime import ConnectorState
from utils.log_util import logger

################################# worker 回调桥 #################################
@dataclass
class WeChatSyncCallbacks:
    """worker 与 connector 之间的回调桥"""

    on_state: Callable[[ConnectorState, str | None], Awaitable[None]]
    on_login_success: Callable[[], Awaitable[None]]
    on_login_expired: Callable[[], Awaitable[None]]
    on_heartbeat: Callable[[], None]
    on_message: Callable[[dict[str, Any]], Awaitable[None]]

################################# 微信后台同步 worker #################################
class WeChatSyncWorker:
    """管理 sync + heartbeat 两个 asyncio.Task，统一启停。"""

    def __init__(
        self,
        *,
        protocol: WeChatProtocol,
        session_store: WeChatSessionStore,
        callbacks: WeChatSyncCallbacks,
        config: WechatConfig,
    ) -> None:
        self.protocol = protocol
        self.session_store = session_store
        self.callbacks = callbacks
        self.config = config

        self._listener_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    ################################# 启动与停止 #################################
    def start(self) -> None:
        if self._listener_task is not None:
            return
        self._stop_event.clear()
        self._listener_task = asyncio.create_task(self._listener_loop(), name='wechat-listener')
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name='wechat-heartbeat')

    async def stop(self) -> None:
        self._stop_event.set()
        tasks = [self._listener_task, self._heartbeat_task]
        for task in tasks:
            if task is None:
                continue
            task.cancel()
        for task in tasks:
            if task is None:
                continue
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.warning(f'[wechat] sync task ended with error: {exc}')
        self._listener_task = None
        self._heartbeat_task = None

    ################################# 主循环与心跳 #################################
    async def _listener_loop(self) -> None:
        """消息同步主循环"""
        poll_interval = self.config.wechat_poll_interval
        min_interval = self.config.wechat_poll_min_interval
        max_interval = self.config.wechat_poll_max_interval

        logger.info('[wechat] listener started')
        while not self._stop_event.is_set():
            had_messages = False
            try:
                if not self.protocol.session.has_auth():
                    await self._ensure_login()
                if self.protocol.session.has_auth():
                    status = await self.protocol.synccheck()
                    if status == 'hasMsg':
                        data = await self.protocol.webwxsync()
                        msgs = data.get('AddMsgList') or []
                        for raw in msgs:
                            had_messages = True
                            try:
                                await self.callbacks.on_message(raw)
                            except Exception as exc:
                                logger.warning(f'[wechat] on_message handler error: {exc}')
                    elif status == 'loginout':
                        logger.warning('[wechat] synccheck reports loginout')
                        await self.callbacks.on_login_expired()
                        await asyncio.sleep(self.config.wechat_reconnect_delay)
                        self.protocol.session.skey = ''
                        self.protocol.session.sid = ''
                        self.protocol.session.pass_ticket = ''
                        self.protocol.session.uin = ''
                        await self.session_store.save(self.protocol.session)
                        continue
                poll_interval = min_interval if had_messages else min(poll_interval * 1.2, max_interval)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f'[wechat] listener loop error: {exc}')
                poll_interval = max_interval

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=poll_interval)
            except asyncio.TimeoutError:
                pass

        logger.info('[wechat] listener stopped')

    async def _heartbeat_loop(self) -> None:
        """心跳：定期记录 last_heartbeat 并触发 on_heartbeat 回调"""
        logger.info('[wechat] heartbeat started')
        while not self._stop_event.is_set():
            try:
                self.callbacks.on_heartbeat()
            except Exception as exc:
                logger.warning(f'[wechat] heartbeat callback error: {exc}')

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.config.wechat_heartbeat_interval
                )
            except asyncio.TimeoutError:
                pass

        logger.info('[wechat] heartbeat stopped')

    ################################# 登录等待与 uuid 等待 #################################
    async def _ensure_login(self) -> None:
        """等待用户扫码登录（uuid 有效时轮询；无 uuid 时引导用户取二维码）"""
        if not self.protocol.session.uuid:
            await self.callbacks.on_state(ConnectorState.WAITING_QR, 'waiting for qr')
            # 等待外部 /qr 触发 uuid 申请
            await self._await_uuid(timeout=300.0)
            if not self.protocol.session.uuid:
                return
        await self.callbacks.on_state(ConnectorState.LOGGING_IN, 'polling login')
        code = await self.protocol.poll_login()
        if code == 200:
            self.protocol.session.cookies = self.protocol.capture_cookies()
            await self.session_store.save(self.protocol.session)
            await self.callbacks.on_login_success()
        elif code in {408, 201}:
            # 还在等扫码，下次循环继续轮询
            return
        else:
            await self.callbacks.on_login_expired()
            self.protocol.session.uuid = ''
            await asyncio.sleep(self.config.wechat_reconnect_delay)

    async def _await_uuid(self, timeout: float) -> None:
        """uuid 由 /qr 接口写入；这里等待直到有值或超时"""
        deadline = time.time() + timeout
        while not self.protocol.session.uuid and time.time() < deadline:
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=0.5)
                return
            except asyncio.TimeoutError:
                continue
