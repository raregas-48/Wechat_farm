"""
数据模型定义 — 使用 dataclass 定义各表的 Python 对应结构。

这些类简化了数据库记录与 Python 对象之间的转换。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Account:
    id: str
    wechat_id: Optional[str] = None
    phone: Optional[str] = None
    device_serial: Optional[str] = None
    imei: Optional[str] = None
    sim_number: Optional[str] = None
    registration_date: Optional[str] = None
    batch_name: Optional[str] = None
    stage: str = "trust_building"
    persona_id: Optional[str] = None
    level: str = "L1"
    state: str = "normal"
    mode: str = "full"
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_row(cls, row: tuple, columns: list[str]) -> "Account":
        """从 SQLite 查询结果构建 Account"""
        data = dict(zip(columns, row))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ActionLog:
    account_id: str
    action_type: str
    action_params: Optional[str] = None
    scheduled_time: Optional[str] = None
    executed_at: Optional[str] = None
    success: int = 1
    error_msg: Optional[str] = None
    screenshot_path: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Friend:
    account_id: str
    friend_name: str
    friend_wechat_id: Optional[str] = None
    source: Optional[str] = None
    added_date: Optional[str] = None
    last_chat_time: Optional[str] = None
    chat_count: int = 0
    id: Optional[int] = None


@dataclass
class Moment:
    account_id: str
    content: Optional[str] = None
    has_images: int = 0
    image_paths: Optional[str] = None
    posted_at: Optional[str] = None
    likes_count: int = 0
    comments_count: int = 0
    id: Optional[int] = None


@dataclass
class HealthCheck:
    account_id: str
    check_time: Optional[str] = None
    moments_visible: int = 1
    add_friend_normal: int = 1
    message_delay_ms: Optional[float] = None
    captcha_count: int = 0
    risk_score: float = 0.0
    state: str = "normal"
    notes: Optional[str] = None
    id: Optional[int] = None


@dataclass
class ContentHistory:
    account_id: str
    content_type: str
    content_hash: Optional[str] = None
    content_preview: Optional[str] = None
    source: str = "template"
    generated_at: Optional[str] = None
    id: Optional[int] = None
