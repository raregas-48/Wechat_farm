"""
批次管理器 — 按注册时间将账号分组，流水线推进养号阶段。

流水线模式:
    Week 1:  批次A (10个号) → trust_building
    Week 3:  批次B (10个号) → trust_building, 批次A → light_interact
    Week 5:  批次C (10个号) → trust_building, 批次B → light_interact, 批次A → normal_use
    ...
    Month 3: 批次A 成熟出仓 → mature

使用方式:
    bm = BatchManager(db)
    bm.create_batch("batch_a", ["acc_001", "acc_002"], "2026-07-01")
    bm.advance_all_stages()
"""

from datetime import date, datetime
from typing import Optional

from config.account_stages import (
    AccountStage,
    get_stage_for_account,
    STAGE_CONFIGS,
)
from storage.db import Database
from utils.logger import get_logger

logger = get_logger("batch_manager")


class BatchManager:
    """
    批次管理器 — 管理账号的批量注册、阶段推进和状态跟踪。
    """

    def __init__(self, db: Database):
        self.db = db

    # ================================================================
    # 批次管理
    # ================================================================

    def create_batch(
        self,
        batch_name: str,
        account_ids: list[str],
        registration_date: str,
        persona_ids: list[str] = None,
    ):
        """
        创建一个新的养号批次。

        Args:
            batch_name: 批次名称
            account_ids: 账号 ID 列表
            registration_date: 注册日期
            persona_ids: 人格 ID 列表（长度应与 account_ids 相同）
        """
        stage = AccountStage.TRUST_BUILDING.value

        for i, account_id in enumerate(account_ids):
            persona_id = persona_ids[i] if persona_ids and i < len(persona_ids) else None
            self.db.insert_account(
                id=account_id,
                batch_name=batch_name,
                registration_date=registration_date,
                stage=stage,
                persona_id=persona_id,
                state="normal",
                mode="full",
            )

        logger.info(
            f"批次 '{batch_name}' 已创建: {len(account_ids)} 个账号, "
            f"注册日期 {registration_date}, 阶段 {stage}"
        )

    def get_batch_accounts(self, batch_name: str) -> list[dict]:
        """获取批次中的所有账号"""
        all_accounts = self.db.get_all_accounts()
        return [a for a in all_accounts if a.get("batch_name") == batch_name]

    def list_batches(self) -> dict[str, int]:
        """列出所有批次及账号数量"""
        accounts = self.db.get_all_accounts()
        batches: dict[str, int] = {}
        for a in accounts:
            batch = a.get("batch_name", "未分组")
            batches[batch] = batches.get(batch, 0) + 1
        return batches

    # ================================================================
    # 阶段推进
    # ================================================================

    def advance_all_stages(self):
        """
        对所有活跃账号检查并推进阶段。

        根据注册日期与当前日期的差值自动判断应处于哪个阶段。
        """
        accounts = self.db.get_active_accounts()
        updated_count = 0

        for acc in accounts:
            reg_date = acc.get("registration_date")
            if not reg_date:
                continue

            try:
                expected_stage = get_stage_for_account(reg_date)
            except ValueError:
                continue

            current_stage = acc.get("stage", "")
            if expected_stage.value != current_stage:
                logger.info(
                    f"账号 {acc['id']}: 阶段晋升 "
                    f"{current_stage} → {expected_stage.value}"
                )
                self.db.update_account(acc["id"], stage=expected_stage.value)
                updated_count += 1

        if updated_count > 0:
            logger.info(f"阶段推进完成: {updated_count} 个账号")

    def get_stage_summary(self) -> dict[str, int]:
        """获取各阶段的账号数量统计"""
        accounts = self.db.get_all_accounts()
        summary: dict[str, int] = {}
        for acc in accounts:
            stage = acc.get("stage", "unknown")
            summary[stage] = summary.get(stage, 0) + 1
        return summary

    # ================================================================
    # 成熟出仓判断
    # ================================================================

    def get_mature_accounts(self) -> list[dict]:
        """
        获取已达到成熟期的账号列表。

        这些账号已可用于 benchmark 测试。
        """
        return self.db.get_accounts_by_stage(AccountStage.MATURE.value)

    def mark_as_test_ready(self, account_id: str):
        """
        将账号标记为"可投入测试"。

        仅当账号处于成熟期（mature）时才建议标记。
        """
        acc = self.db.get_account(account_id)
        if acc and acc.get("stage") == AccountStage.MATURE.value:
            self.db.update_account(account_id, state="mature", mode="full")
            logger.info(f"账号 {account_id} 已标记为测试就绪")
        else:
            logger.warning(f"账号 {account_id} 尚未达到成熟期，不建议投入测试")

    # ================================================================
    # 账号状态汇总
    # ================================================================

    def get_batch_report(self, batch_name: str = None) -> dict:
        """
        生成批次报告。

        Args:
            batch_name: 批次名称，None 返回所有批次

        Returns:
            {"batch_name": {"total": N, "stages": {...}, "states": {...}}}
        """
        if batch_name:
            accounts = self.get_batch_accounts(batch_name)
        else:
            accounts = self.db.get_all_accounts()

        report = {
            "total": len(accounts),
            "by_stage": {},
            "by_state": {},
            "by_level": {},
        }

        for acc in accounts:
            stage = acc.get("stage", "unknown")
            state = acc.get("state", "normal")
            level = acc.get("level", "L1")

            report["by_stage"][stage] = report["by_stage"].get(stage, 0) + 1
            report["by_state"][state] = report["by_state"].get(state, 0) + 1
            report["by_level"][level] = report["by_level"].get(level, 0) + 1

        return report
