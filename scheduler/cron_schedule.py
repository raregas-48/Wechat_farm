"""
定时调度器 — 基于 APScheduler 的定时任务管理。

负责每日定时触发养号脚本、健康检查、日志清理等周期性任务。

使用方式:
    scheduler = CronScheduler()
    scheduler.add_daily_job(run_daily_script, hour=7, minute=0)
    scheduler.start()
"""

from datetime import datetime, timedelta
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from utils.logger import get_logger

logger = get_logger("cron_scheduler")


class CronScheduler:
    """
    定时调度器 — 管理所有周期执行的任务。
    """

    def __init__(self):
        self._scheduler = BackgroundScheduler(
            timezone="Asia/Shanghai",  # 默认中国时区
            job_defaults={
                "coalesce": True,         # 合并错过的任务
                "max_instances": 1,       # 同一任务最多同时运行 1 个实例
                "misfire_grace_time": 300,  # 错过 5 分钟内的任务仍然执行
            },
        )

    def start(self):
        """启动调度器"""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("定时调度器已启动")

    def stop(self):
        """停止调度器"""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("定时调度器已停止")

    def add_daily_job(
        self,
        func: Callable,
        hour: int = 7,
        minute: int = 0,
        job_id: str = "",
        args: list = None,
        kwargs: dict = None,
    ):
        """
        添加每日定时任务。

        Args:
            func: 任务函数
            hour: 执行时间（时，0-23）
            minute: 执行时间（分，0-59）
            job_id: 任务标识（可选）
            args: 位置参数
            kwargs: 关键字参数
        """
        # 为每个任务增加 0-5 分钟的随机抖动，避免多个任务同时触发
        import random
        jitter_minute = random.randint(0, 5)

        self._scheduler.add_job(
            func,
            trigger=CronTrigger(hour=hour, minute=minute + jitter_minute),
            id=job_id or f"daily_{hour:02d}{minute:02d}",
            args=args or [],
            kwargs=kwargs or {},
            replace_existing=True,
        )
        logger.info(f"已添加每日任务: {job_id or func.__name__} @ {hour:02d}:{minute + jitter_minute:02d}")

    def add_interval_job(
        self,
        func: Callable,
        minutes: int = 60,
        job_id: str = "",
        args: list = None,
        kwargs: dict = None,
    ):
        """
        添加间隔执行的任务。

        Args:
            func: 任务函数
            minutes: 间隔分钟数
            job_id: 任务标识
            args: 位置参数
            kwargs: 关键字参数
        """
        self._scheduler.add_job(
            func,
            trigger=IntervalTrigger(minutes=minutes),
            id=job_id or f"interval_{minutes}m",
            args=args or [],
            kwargs=kwargs or {},
            replace_existing=True,
        )
        logger.info(f"已添加间隔任务: {job_id or func.__name__} @ 每 {minutes} 分钟")

    def remove_job(self, job_id: str):
        """移除定时任务"""
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"已移除定时任务: {job_id}")
        except Exception as e:
            logger.warning(f"移除定时任务失败: {job_id}: {e}")

    def get_jobs(self) -> list:
        """获取所有已注册的定时任务"""
        return self._scheduler.get_jobs()

    def is_running(self) -> bool:
        """检查调度器是否正在运行"""
        return self._scheduler.running
