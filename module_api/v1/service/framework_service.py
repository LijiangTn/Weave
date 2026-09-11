"""
框架运行时服务
"""

import json
import os
import platform
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config.env import AppConfig, StorageConfig, WechatConfig
from module_api.v1.service.message_store_service import MessageStoreService
from module_api.v1.service.wechat_service import WechatService
from utils.connector_runtime import BaseConnector


@dataclass
class ScheduledTask:
    task_id: str
    time_hm: str
    command_text: str
    enabled: bool = True
    description: str = ''
    last_run_date: str | None = None
    created_at: str = ''


class FrameworkService:
    _started_at = time.time()
    _chat_enabled = False
    _tasks: dict[str, ScheduledTask] = {}
    _task_file = Path(StorageConfig.storage_dir) / 'framework_tasks.json'
    _loaded_plugins = ('builtin', 'framework_api', 'webui')
    _registered_routes = (
        '/framework/state',
        '/framework/chat_mode',
        '/framework/execute',
        'GET /framework/tasks',
        'POST /framework/tasks',
        '/framework/tasks/{task_id}',
        '/framework/tasks/{task_id}/enabled',
        '/framework/tasks/{task_id}/run',
        '/plugins',
        '/plugins/reload',
        '/health',
        '/stability',
        '/trace/status',
        '/trace/recent',
        '/trace/clear',
        '/debug_html',
        '/webui',
        '/webui/qr',
        '/webui/status',
    )
    _builtin_commands = ('ping', 'plugins', 'status')

    @classmethod
    def mark_started(cls) -> None:
        cls._started_at = time.time()
        cls._load_tasks()

    @classmethod
    def _load_tasks(cls) -> None:
        if not cls._task_file.exists():
            cls._tasks = {}
            return
        try:
            rows = json.loads(cls._task_file.read_text(encoding='utf-8'))
        except Exception:
            cls._tasks = {}
            return
        tasks: dict[str, ScheduledTask] = {}
        for item in rows:
            try:
                task = ScheduledTask(**item)
            except Exception:
                continue
            tasks[task.task_id] = task
        cls._tasks = tasks

    @classmethod
    def _save_tasks(cls) -> None:
        cls._task_file.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(task) for task in cls._tasks.values()]
        cls._task_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    @classmethod
    async def get_state(cls, connector: BaseConnector, message_store_stats: dict[str, Any]) -> dict[str, Any]:
        return {
            'server_label': AppConfig.app_name,
            'chat_enabled': cls._chat_enabled,
            'chat_webhook_enabled': False,
            'message_webhook_enabled': bool(message_store_stats.get('webhook_url')),
            'uptime_seconds': int(time.time() - cls._started_at),
            'task_count': len(cls._tasks),
            'enabled_task_count': len([task for task in cls._tasks.values() if task.enabled]),
            'plugins': cls.list_plugins(),
            'message_store': message_store_stats,
        }

    @classmethod
    def list_tasks(cls) -> list[dict[str, Any]]:
        return [asdict(task) for task in sorted(cls._tasks.values(), key=lambda item: (item.time_hm, item.task_id))]

    @classmethod
    def add_task(cls, time_hm: str, command_text: str, description: str = '') -> dict[str, Any]:
        if not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', time_hm):
            raise ValueError('Invalid time format, expected HH:MM')
        task_id = f'task_{int(time.time() * 1000)}'
        task = ScheduledTask(
            task_id=task_id,
            time_hm=time_hm,
            command_text=command_text.strip(),
            enabled=True,
            description=description.strip(),
            created_at=datetime.now().isoformat(timespec='seconds'),
        )
        cls._tasks[task_id] = task
        cls._save_tasks()
        return asdict(task)

    @classmethod
    def delete_task(cls, task_id: str) -> bool:
        if task_id not in cls._tasks:
            return False
        del cls._tasks[task_id]
        cls._save_tasks()
        return True

    @classmethod
    def set_task_enabled(cls, task_id: str, enabled: bool) -> bool:
        task = cls._tasks.get(task_id)
        if task is None:
            return False
        task.enabled = enabled
        cls._save_tasks()
        return True

    @classmethod
    async def run_task_now(cls, connector: BaseConnector, task_id: str) -> bool:
        task = cls._tasks.get(task_id)
        if task is None:
            return False
        result = await cls.execute_command_text(task.command_text, connector, source=task_id)
        if result is not None and await WechatService.check_login_status(connector, poll=False):
            await WechatService.send_text(connector, result)
        task.last_run_date = datetime.now().strftime('%Y-%m-%d')
        cls._save_tasks()
        return True

    @classmethod
    def set_chat_mode(cls, enabled: bool) -> None:
        cls._chat_enabled = bool(enabled)

    @classmethod
    async def execute_command_text(
        cls,
        text: str,
        connector: BaseConnector,
        *,
        source: str = 'api_execute',
    ) -> str | None:
        raw = text.strip()
        if not raw:
            return None
        lowered = raw.lower()
        if lowered in {'#ping#', '/ping', 'ping'}:
            return 'Pong!'
        if lowered in {'/plugins', 'plugins'}:
            status = cls.list_plugins()
            lines = [
                f"插件目录: {status['plugins_dir']}",
                f"已加载: {status['loaded_count']} 个插件",
                f"命令数: {status['commands_count']}",
                f"处理器: {status['handlers_count']}",
            ]
            if status['loaded_plugins']:
                lines.append(f"插件列表: {', '.join(status['loaded_plugins'])}")
            return '\n'.join(lines)
        if lowered in {'/status', 'status'}:
            login = await WechatService.get_login_status(connector)
            uptime = int(time.time() - cls._started_at)
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return (
                f'server={AppConfig.app_name}\n'
                f'time={now}\n'
                f'uptime={uptime}s\n'
                f'platform={platform.platform()}\n'
                f'python={platform.python_version()}\n'
                f'pid={os.getpid()}\n'
                f"wechat_logged_in={login.get('logged_in', False)}\n"
                f'chat_mode={cls._chat_enabled}\n'
                f'tasks={len(cls._tasks)}\n'
                f'plugins={len(cls._loaded_plugins)}'
            )
        return None

    @classmethod
    def list_plugins(cls) -> dict[str, Any]:
        plugins_dir = str(Path.cwd() / 'plugins')
        return {
            'plugins_dir': plugins_dir,
            'loaded_count': len(cls._loaded_plugins),
            'loaded_plugins': list(cls._loaded_plugins),
            'errors': [],
            'commands_count': len(cls._builtin_commands),
            'handlers_count': 0,
            'routes_count': len(cls._registered_routes),
        }

    @classmethod
    def reload_plugins(cls) -> dict[str, Any]:
        return cls.list_plugins()

    @classmethod
    async def health_check(cls, connector: BaseConnector) -> dict[str, Any]:
        is_logged_in = await WechatService.check_login_status(connector, poll=False)
        return {
            'status': 'healthy' if is_logged_in else 'degraded',
            'logged_in': is_logged_in,
            'uptime': int(time.time() - cls._started_at),
            'stability': cls._stability_payload(connector),
        }

    @classmethod
    def stability_status(cls, connector: BaseConnector) -> dict[str, Any]:
        payload = cls._stability_payload(connector)
        payload['config'] = {
            'heartbeat_interval': WechatConfig.wechat_heartbeat_interval,
            'reconnect_delay': WechatConfig.wechat_reconnect_delay,
            'file_retention_days': 30,
        }
        return payload

    @classmethod
    def _stability_payload(cls, connector: BaseConnector) -> dict[str, Any]:
        status = connector.get_status()
        return {
            'reconnect_attempts': status.reconnect_attempts,
            'max_reconnect_attempts': WechatConfig.wechat_max_reconnect_attempts,
            'last_heartbeat': status.last_heartbeat,
            'last_message_time': status.last_message_at,
            'total_messages': 0,
            'recent_errors': [status.last_error] if status.last_error else [],
        }

    @classmethod
    async def get_message_store_stats(cls, db) -> dict[str, Any]:
        stats = await MessageStoreService.get_stats(db)
        stats['webhook_url'] = await MessageStoreService.get_webhook(db)
        return stats

    @classmethod
    async def get_debug_snapshot(cls, connector: BaseConnector) -> dict[str, Any]:
        login = await WechatService.get_login_status(connector)
        trace = await WechatService.get_trace_status(connector)
        rows: list[dict[str, Any]] = []
        if trace.get('enabled'):
            rows = await WechatService.read_recent_traces(connector, limit=20)
        return {
            'mode': 'direct_protocol',
            'message': 'browser page source is unavailable in direct protocol mode',
            'login_status': login,
            'trace_status': trace,
            'recent_traces': rows,
        }
