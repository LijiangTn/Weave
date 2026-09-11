"""
asyncio.Task 生命周期管理器

统一启动/取消后台任务，避免裸 asyncio.create_task 在 shutdown 时悬挂。
"""

import asyncio
from typing import Any, Coroutine

from utils.log_util import logger

class TaskManager:
    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []

    def spawn(self, coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task:
        """启动后台协程并纳入跟踪；任务结束后自动从池中移除。"""
        task = asyncio.create_task(coro, name=name)
        self._tasks.append(task)
        task.add_done_callback(self._on_done)
        logger.debug(f'TaskManager: spawned {name}')
        return task

    def _on_done(self, task: asyncio.Task) -> None:
        try:
            self._tasks.remove(task)
        except ValueError:
            return
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.warning(f'Task {task.get_name()} exited with error: {exc}')

    async def cancel_all(self) -> None:
        """取消所有跟踪中的任务并等待结束。"""
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.warning(f'Task {task.get_name()} raised during cancel: {exc}')
        self._tasks.clear()
        logger.debug('TaskManager: all tasks cancelled')

    @property
    def active(self) -> int:
        return len(self._tasks)

task_manager = TaskManager()