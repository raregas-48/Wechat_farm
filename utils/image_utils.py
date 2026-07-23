"""
图像工具模块 — 仅用于异常截图存储，不用于视觉识别 / 元素定位。

使用方式:
    from utils.image_utils import save_debug_screenshot
    path = save_debug_screenshot(d, account_id, "like_failed")
"""

import time
from pathlib import Path

import uiautomator2 as u2

from config.settings import settings
from utils.logger import get_logger

logger = get_logger("image_utils")


def save_debug_screenshot(
    d: u2.Device,
    account_id: str,
    tag: str = "",
) -> str | None:
    """
    保存调试截图（仅在操作异常时调用）。

    Args:
        d: uiautomator2 设备连接
        account_id: 账号标识
        tag: 场景标签（如 "like_failed"）

    Returns:
        截图文件路径，失败返回 None
    """
    try:
        account_dir = settings.SCREENSHOTS_DIR / account_id
        account_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{tag}.png" if tag else f"{timestamp}.png"
        filepath = account_dir / filename

        d.screenshot(str(filepath))
        logger.debug(f"调试截图已保存: {filepath}")
        return str(filepath)
    except Exception as e:
        logger.warning(f"保存截图失败 ({account_id}/{tag}): {e}")
        return None


def clean_old_screenshots(days: int = 7):
    """
    清理超过指定天数的旧截图。

    Args:
        days: 保留最近 N 天的截图
    """
    cutoff = time.time() - days * 86400
    removed = 0
    for png in settings.SCREENSHOTS_DIR.rglob("*.png"):
        if png.stat().st_mtime < cutoff:
            png.unlink()
            removed += 1
    if removed > 0:
        logger.info(f"已清理 {removed} 张旧截图（保留最近 {days} 天）")
