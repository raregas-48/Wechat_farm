"""
任务队列 — 基于 asyncio 的任务调度核心。

负责任务的排队、执行、重试和状态跟踪。

使用方式:
    queue = TaskQueue(max_concurrent=5)
    await queue.submit(task)
    await queue.wait_all()
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from utils.logger import get_logger

logger = get_logger("task_queue")


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """单个任务"""
    id: str
    name: str
    coro: Callable[[], Coroutine]
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    scheduled_time: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retries: int = 0
    max_retries: int = 1
    account_id: str = ""
    tags: list[str] = field(default_factory=list)


class TaskQueue:
    """
    异步任务队列。

    支持:
      - 并发控制（信号量限制同时执行数）
      - 重试机制
      - 超时控制
      - 依赖任务链
    """

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tasks: list[Task] = []
        self._pending: list[Task] = []
        self._running: dict[str, asyncio.Task] = {}
        self._completed: list[Task] = []
        self._failed: list[Task] = []

    # ================================================================
    # 任务提交
    # ================================================================

    def add_task(self, task: Task):
        """添加任务到队列"""
        self._tasks.append(task)

    def create_task(
        self,
        name: str,
        coro: Callable[[], Coroutine],
        account_id: str = "",
        max_retries: int = 1,
        tags: list[str] = None,
    ) -> Task:
        """快捷创建并添加任务"""
        task = Task(
            id=f"task_{int(time.time() * 1000)}_{len(self._tasks)}",
            name=name,
            coro=coro,
            account_id=account_id,
            max_retries=max_retries,
            tags=tags or [],
        )
        self.add_task(task)
        return task

    # ================================================================
    # 任务执行
    # ================================================================

    async def _execute_task(self, task: Task) -> Task:
        """执行单个任务（含重试）"""
        async with self._semaphore:
            for attempt in range(task.max_retries + 1):
                try:
                    task.status = TaskStatus.RUNNING
                    task.started_at = time.time()
                    if attempt > 0:
                        logger.debug(f"任务重试 ({attempt}/{task.max_retries}): {task.name}")

                    task.result = await task.coro()
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = time.time()
                    self._completed.append(task)
                    logger.debug(f"任务完成: {task.name} [{task.account_id}]")
                    return task

                except asyncio.CancelledError:
                    task.status = TaskStatus.CANCELLED
                    task.error = "任务被取消"
                    return task

                except Exception as e:
                    task.error = str(e)
                    if attempt >= task.max_retries:
                        task.status = TaskStatus.FAILED
                        task.completed_at = time.time()
                        self._failed.append(task)
                        logger.error(
                            f"任务失败: {task.name} [{task.account_id}] "
                            f"(重试{task.max_retries}次后): {e}"
                        )
                        return task

                    # 重试前等待
                    wait_time = 2 ** attempt  # 指数退避
                    logger.warning(
                        f"任务失败，{wait_time}s 后重试: {task.name}: {e}"
                    )
                    await asyncio.sleep(wait_time)

        return task

    async def run_all(self) -> list[Task]:
        """
        并发执行所有待处理任务。

        Returns:
            完成的任务列表（含成功和失败）
        """
        logger.info(f"开始执行 {len(self._tasks)} 个任务...")
        start_time = time.time()

        coros = [self._execute_task(task) for task in self._tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        elapsed = time.time() - start_time
        completed = [t for t in self._tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in self._tasks if t.status == TaskStatus.FAILED]
        logger.info(
            f"任务执行完成: {len(completed)} 成功 / {len(failed)} 失败 "
            f"(耗时 {elapsed:.1f}s)"
        )
        return self._tasks

    async def run_for_account(self, account_id: str) -> list[Task]:
        """仅执行指定账号的任务"""
        account_tasks = [t for t in self._tasks if t.account_id == account_id]
        coros = [self._execute_task(t) for t in account_tasks]
        await asyncio.gather(*coros, return_exceptions=True)
        return account_tasks

    # ================================================================
    # 状态查询
    # ================================================================

    def get_stats(self) -> dict:
        """获取任务统计"""
        return {
            "total": len(self._tasks),
            "completed": len(self._completed),
            "failed": len(self._failed),
            "pending": sum(1 for t in self._tasks if t.status == TaskStatus.PENDING),
        }

    def clear(self):
        """清空任务队列"""
        self._tasks.clear()
        self._completed.clear()
        self._failed.clear()
