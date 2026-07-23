"""
预警通知模块 — 当账号出现异常时发送通知。

支持的通知渠道:
    - 日志记录（默认）
    - 钉钉 Webhook（可选）
    - 邮件（可选，后续扩展）

使用方式:
    from monitor.alert import AlertManager
    alert = AlertManager()
    alert.send_warning("acc_001", "消息延迟 > 5s")
"""

import json
from datetime import datetime
from typing import Optional

import requests

from config.settings import settings
from utils.logger import get_logger

logger = get_logger("alert")


class AlertLevel:
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertManager:
    """
    预警通知管理器。

    根据严重等级选择合适的通知渠道。
    """

    def __init__(self, dingtalk_webhook: str = ""):
        self.dingtalk_webhook = dingtalk_webhook or settings.ALERT_DINGTALK_WEBHOOK

    # ================================================================
    # 通知发送
    # ================================================================

    def send(
        self,
        level: str,
        account_id: str,
        message: str,
        details: dict = None,
    ):
        """
        发送预警通知。

        Args:
            level: 等级 (info/warning/critical)
            account_id: 账号标识
            message: 通知内容
            details: 附加详情
        """
        # 1. 始终记录日志
        log_msg = f"[{level.upper()}] [{account_id}] {message}"
        if details:
            log_msg += f" | details={json.dumps(details, ensure_ascii=False)}"

        if level == AlertLevel.CRITICAL:
            logger.error(log_msg)
        elif level == AlertLevel.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        # 2. 钉钉通知（warning 及以上）
        if level in (AlertLevel.WARNING, AlertLevel.CRITICAL):
            self._send_dingtalk(level, account_id, message, details)

    def send_warning(self, account_id: str, message: str, **details):
        """发送警告通知"""
        self.send(AlertLevel.WARNING, account_id, message, details)

    def send_critical(self, account_id: str, message: str, **details):
        """发送严重预警"""
        self.send(AlertLevel.CRITICAL, account_id, message, details)

    def send_info(self, account_id: str, message: str, **details):
        """发送信息通知"""
        self.send(AlertLevel.INFO, account_id, message, details)

    # ================================================================
    # 预设模板
    # ================================================================

    def alert_state_change(
        self,
        account_id: str,
        old_state: str,
        new_state: str,
        reason: str = "",
    ):
        """账号状态变更通知"""
        msg = f"账号状态变更: {old_state} → {new_state}"
        if reason:
            msg += f"（原因: {reason}）"

        level = AlertLevel.WARNING
        if new_state in ("suspended",):
            level = AlertLevel.CRITICAL

        self.send(level, account_id, msg)

    def alert_captcha_spike(self, account_id: str, count: int):
        """滑块验证频繁通知"""
        self.send_warning(
            account_id,
            f"滑块验证次数异常: {count} 次/天",
            captcha_count=count,
        )

    def alert_delay_spike(self, account_id: str, delay_ms: float):
        """消息延迟异常通知"""
        level = AlertLevel.CRITICAL if delay_ms > 10000 else AlertLevel.WARNING
        self.send(
            level, account_id,
            f"消息发送延迟过高: {delay_ms:.0f}ms",
            {"delay_ms": delay_ms},
        )

    def alert_connection_lost(self, serial: str):
        """设备连接断开通知"""
        self.send_critical(
            serial,
            f"设备连接断开: {serial}",
        )

    # ================================================================
    # 每日汇总
    # ================================================================

    def send_daily_summary(self, summary: dict):
        """
        发送每日养号汇总。

        Args:
            summary: {"total_accounts": N, "normal": N, "warning": N, ...}
        """
        total = summary.get("total_accounts", 0)
        normal = summary.get("normal", 0)
        warning = summary.get("warning", 0)
        cooldown = summary.get("cooldown", 0)

        msg = (
            f"养号日报: {total} 个账号 | "
            f"正常: {normal} | 预警: {warning} | 冷却: {cooldown}"
        )
        self.send_info("system", msg, **summary)

    # ================================================================
    # 钉钉通知
    # ================================================================

    def _send_dingtalk(
        self,
        level: str,
        account_id: str,
        message: str,
        details: dict = None,
    ):
        """通过钉钉 Webhook 发送通知"""
        if not self.dingtalk_webhook:
            return

        emoji = "[CRIT]" if level == AlertLevel.CRITICAL else "[WARN]"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        text = f"{emoji} 微信养号预警\n\n"
        text += f"**时间**: {now}\n"
        text += f"**账号**: {account_id}\n"
        text += f"**内容**: {message}\n"

        if details:
            text += f"**详情**: {json.dumps(details, ensure_ascii=False, indent=2)}\n"

        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"养号预警 - {account_id}",
                    "text": text,
                },
            }
            resp = requests.post(
                self.dingtalk_webhook,
                json=payload,
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"钉钉通知发送失败: {resp.status_code}")
        except Exception as e:
            logger.warning(f"钉钉通知异常: {e}")
