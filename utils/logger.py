"""
统一日志模块 — 基于 loguru，支持文件轮转和控制台输出。

使用方式:
    from utils.logger import get_logger
    logger = get_logger("wechat_control")
    logger.info("打开了朋友圈")
"""

import sys
from pathlib import Path

from loguru import logger


def setup_logger(
    log_dir: str | Path = None,
    level: str = "INFO",
    retention: str = "30 days",
    rotation: str = "50 MB",
):
    """
    初始化全局日志配置。

    Args:
        log_dir: 日志文件目录，默认项目根下的 logs/
        level: 日志级别
        retention: 日志保留时长
        rotation: 日志文件轮转大小
    """
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "logs"
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # 移除默认 handler
    logger.remove()

    # 控制台输出 — 彩色格式
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[source]: <20}</cyan> | "
            "<level>{message}</level>"
        ),
        level=level,
        colorize=True,
    )

    # 全量日志文件 — 按大小轮转
    logger.add(
        str(log_dir / "wechat_farm_{time:YYYY-MM-DD}.log"),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[source]: <20} | {message}",
        level="DEBUG",
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
        enqueue=True,
    )

    # 错误日志单独文件
    logger.add(
        str(log_dir / "error_{time:YYYY-MM-DD}.log"),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {extra[source]: <20} | {message}",
        level="ERROR",
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
        enqueue=True,
    )

    return logger


def get_logger(source: str = "default"):
    """
    获取带有 source 标识的 logger。

    Args:
        source: 模块名称，用于在日志中标识来源

    Returns:
        绑定了 source 的 logger 实例
    """
    return logger.bind(source=source)
