"""
监控指标模块 — Prometheus 指标上报（可选）。

提供以下指标:
    - wechat_farm_actions_total: 操作总数（按账号、类型、成功/失败分类）
    - wechat_farm_device_online: 设备在线状态
    - wechat_farm_account_risk_score: 账号风险评分
    - wechat_farm_action_duration_seconds: 操作耗时

使用方式:
    from monitor.metrics import MetricsReporter
    reporter = MetricsReporter()
    reporter.record_action("acc_001", "scroll_moments", success=True, duration=2.5)
"""

import time
from typing import Optional

from utils.logger import get_logger

logger = get_logger("metrics")

# 尝试导入 Prometheus，如果未安装则使用空实现
try:
    from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, generate_latest

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.info("prometheus-client 未安装，监控指标功能禁用")


class MetricsReporter:
    """
    监控指标上报器。

    如果 prometheus-client 未安装，所有操作降级为日志记录。
    """

    def __init__(self):
        self._registry: Optional[CollectorRegistry] = None

        if _PROMETHEUS_AVAILABLE:
            self._registry = CollectorRegistry()

            # 操作计数器
            self._action_counter = Counter(
                "wechat_farm_actions_total",
                "操作总数",
                ["account_id", "action_type", "status"],  # status: success/fail
                registry=self._registry,
            )

            # 设备在线状态
            self._device_online = Gauge(
                "wechat_farm_device_online",
                "设备在线状态 (1=在线, 0=离线)",
                ["serial"],
                registry=self._registry,
            )

            # 账号风险评分
            self._risk_score = Gauge(
                "wechat_farm_account_risk_score",
                "账号风险评分 (0.0-1.0)",
                ["account_id"],
                registry=self._registry,
            )

            # 操作耗时
            self._action_duration = Histogram(
                "wechat_farm_action_duration_seconds",
                "操作耗时（秒）",
                ["account_id", "action_type"],
                buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
                registry=self._registry,
            )

    # ================================================================
    # 指标上报
    # ================================================================

    def record_action(
        self,
        account_id: str,
        action_type: str,
        success: bool = True,
        duration: float = 0.0,
    ):
        """记录一次操作"""
        if not _PROMETHEUS_AVAILABLE:
            return

        status = "success" if success else "fail"
        self._action_counter.labels(
            account_id=account_id, action_type=action_type, status=status
        ).inc()

        if duration > 0:
            self._action_duration.labels(
                account_id=account_id, action_type=action_type
            ).observe(duration)

    def set_device_online(self, serial: str, online: bool):
        """设置设备在线状态"""
        if not _PROMETHEUS_AVAILABLE:
            return
        self._device_online.labels(serial=serial).set(1 if online else 0)

    def set_risk_score(self, account_id: str, score: float):
        """设置账号风险评分"""
        if not _PROMETHEUS_AVAILABLE:
            return
        self._risk_score.labels(account_id=account_id).set(score)

    # ================================================================
    # 导出
    # ================================================================

    def get_metrics(self) -> str:
        """获取 Prometheus 格式的指标文本"""
        if not _PROMETHEUS_AVAILABLE:
            return "# prometheus-client not installed\n"
        return generate_latest(self._registry).decode("utf-8")
