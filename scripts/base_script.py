"""
行为脚本基类 — 定义 DailyScript 数据结构、ActionType 枚举和脚本执行接口。

所有养号阶段脚本都继承此基类，统一行为调度和执行逻辑。

使用方式:
    script = TrustBuildingScript(wc, persona, db)
    await script.run_daily()
"""

import asyncio
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Optional

from core.wechat_control import WeChatControl
from core.humanizer import Humanizer
from storage.db import Database
from utils.logger import get_logger
from utils.image_utils import save_debug_screenshot
from monitor.metrics import MetricsReporter

logger = get_logger("scripts")


class ActionType(Enum):
    """动作类型枚举"""
    OPEN_WECHAT = "open_wechat"
    SCROLL_MOMENTS = "scroll_moments"
    LIKE_MOMENT = "like_moment"
    COMMENT_MOMENT = "comment_moment"
    BROWSE_MOMENTS_INTERACT = "browse_moments_interact"
    POST_MOMENT = "post_moment"
    SCROLL_CHANNELS = "scroll_channels"
    LIKE_CHANNEL = "like_channel"
    READ_ARTICLE = "read_article"
    FAVORITE_ARTICLE = "favorite_article"
    GLOBAL_SEARCH = "global_search"
    SEND_MESSAGE = "send_message"
    SEND_IMAGE = "send_image"
    SEND_VOICE = "send_voice"
    SEND_EMOJI = "send_emoji"
    MAKE_PAYMENT = "make_payment"
    OPEN_FAVORITES = "open_favorites"
    BROWSE_FAVORITES = "browse_favorites"
    IDLE = "idle"
    SLEEP = "sleep"


@dataclass
class Action:
    """单个行为动作"""
    action_type: ActionType
    time_window_start: str          # "08:00"
    time_window_end: str            # "09:00"
    duration_seconds: tuple         # (min, max)
    params: dict = field(default_factory=dict)
    random_offset_minutes: int = 30


@dataclass
class DailyScript:
    """单日行为剧本"""
    stage: str
    is_weekend: bool
    actions: list[Action]


class BaseScript(ABC):
    """
    行为脚本基类。

    子类需要实现:
      - _build_weekday_script() → DailyScript
      - _build_weekend_script() → DailyScript

    公用能力:
      - 动作到 WeChatControl 方法的映射和执行
      - 时间窗口调度
      - 异常处理和日志记录
      - 每日限量检查
    """

    STAGE_NAME = "base"

    def __init__(
        self,
        wechat: WeChatControl,
        persona: dict,
        db: Database,
        metrics: Optional[MetricsReporter] = None,
    ):
        self.wc = wechat
        self.h = wechat.h
        self.persona = persona
        self.db = db
        self.account_id = wechat.account_id
        self.metrics = metrics or MetricsReporter()

        # 当日操作计数器
        self._daily_counts: dict[str, int] = {}

        # 动作处理器映射
        self._action_handlers: dict[ActionType, Callable] = {
            ActionType.OPEN_WECHAT:      self._handle_open_wechat,
            ActionType.SCROLL_MOMENTS:          self._handle_scroll_moments,
            ActionType.LIKE_MOMENT:             self._handle_like_moment,
            ActionType.COMMENT_MOMENT:          self._handle_comment_moment,
            ActionType.BROWSE_MOMENTS_INTERACT: self._handle_browse_moments_interact,
            ActionType.POST_MOMENT:      self._handle_post_moment,
            ActionType.SCROLL_CHANNELS:  self._handle_scroll_channels,
            ActionType.LIKE_CHANNEL:     self._handle_like_channel,
            ActionType.READ_ARTICLE:     self._handle_read_article,
            ActionType.FAVORITE_ARTICLE: self._handle_favorite_article,
            ActionType.GLOBAL_SEARCH:    self._handle_global_search,
            ActionType.SEND_MESSAGE:     self._handle_send_message,
            ActionType.SEND_IMAGE:       self._handle_send_image,
            ActionType.SEND_VOICE:       self._handle_send_voice,
            ActionType.SEND_EMOJI:       self._handle_send_emoji,
            ActionType.MAKE_PAYMENT:     self._handle_make_payment,
            ActionType.OPEN_FAVORITES:   self._handle_open_favorites,
            ActionType.BROWSE_FAVORITES: self._handle_browse_favorites,
            ActionType.IDLE:             self._handle_idle,
            ActionType.SLEEP:            self._handle_sleep,
        }

    # ================================================================
    # 子类必须实现
    # ================================================================

    @abstractmethod
    def _build_weekday_script(self) -> DailyScript:
        """构建工作日行为剧本"""
        ...

    @abstractmethod
    def _build_weekend_script(self) -> DailyScript:
        """构建周末行为剧本"""
        ...

    # ================================================================
    # 每日执行入口
    # ================================================================

    async def run_daily(self):
        """
        执行一天的养号剧本。

        1. 判断工作日/周末 → 选择对应剧本
        2. 为每个动作生成精确执行时间（时间窗口 + 随机偏移）
        3. 按时间顺序等待并执行
        """
        is_weekend = datetime.now().weekday() >= 5
        script = self._build_weekend_script() if is_weekend else self._build_weekday_script()

        logger.info(
            f"[{self.account_id}] 开始执行 {self.STAGE_NAME} "
            f"({'周末' if is_weekend else '工作日'}) 剧本, "
            f"共 {len(script.actions)} 个动作"
        )

        scheduled = self._schedule_actions(script.actions)
        success_count = 0
        fail_count = 0

        for exec_time, action in scheduled:
            # 等待到预定时间
            now = datetime.now()
            wait = (exec_time - now).total_seconds()
            if wait > 0:
                # 如果等待时间长，分段 sleep 以便响应中断
                while wait > 0:
                    chunk = min(wait, 60)  # 每次最多 sleep 60s
                    await asyncio.sleep(chunk)
                    wait -= chunk

                    # 检查是否在允许的操作时间内
                    current_hour = datetime.now().hour
                    if action.action_type != ActionType.SLEEP:
                        if current_hour < 7 or current_hour >= 23:
                            logger.debug(
                                f"[{self.account_id}] 超出活跃时间({current_hour}h)，"
                                f"跳过动作 {action.action_type.value}"
                            )
                            break
                else:
                    # wait loop 正常结束，执行动作
                    pass
                if current_hour < 7 or current_hour >= 23:
                    continue

            # 执行动作
            handler = self._action_handlers.get(action.action_type)
            if handler:
                start_time = time.time()
                try:
                    result = handler(action.params)
                    elapsed = time.time() - start_time

                    if result:
                        success_count += 1
                    else:
                        fail_count += 1
                        logger.warning(
                            f"[{self.account_id}] 动作未成功: {action.action_type.value}"
                        )

                    # 记录日志
                    self.db.log_action(
                        account_id=self.account_id,
                        action_type=action.action_type.value,
                        success=result,
                        action_params=action.params,
                    )

                    # 上报指标
                    self.metrics.record_action(
                        self.account_id, action.action_type.value,
                        success=result, duration=elapsed,
                    )

                except Exception as e:
                    fail_count += 1
                    logger.error(
                        f"[{self.account_id}] 动作异常 {action.action_type.value}: {e}"
                    )
                    self.db.log_action(
                        account_id=self.account_id,
                        action_type=action.action_type.value,
                        success=False,
                        error_msg=str(e),
                        action_params=action.params,
                        screenshot_path=save_debug_screenshot(
                            self.wc.d, self.account_id, action.action_type.value
                        ) or "",
                    )

                # 动作间随机间隔
                await asyncio.sleep(self.h.action_interval("general"))

        logger.info(
            f"[{self.account_id}] 剧本执行完成: "
            f"{success_count} 成功 / {fail_count} 失败"
        )
        return {"success": success_count, "fail": fail_count}

    # ================================================================
    # 时间调度
    # ================================================================

    def _schedule_actions(self, actions: list[Action]) -> list[tuple[datetime, Action]]:
        """
        为每个动作生成精确执行时间。

        在时间窗口内随机选取 + 随机偏移。
        """
        scheduled = []
        today = datetime.now().date()

        for action in actions:
            start_h, start_m = map(int, action.time_window_start.split(":"))
            end_h, end_m = map(int, action.time_window_end.split(":"))

            window_start = datetime(today.year, today.month, today.day, start_h, start_m)
            window_end = datetime(today.year, today.month, today.day, end_h, end_m)

            # 处理跨天窗口（如 SLEEP 23:00-07:00）
            if window_end <= window_start:
                window_end += timedelta(days=1)

            window_seconds = (window_end - window_start).total_seconds()
            if window_seconds > 0:
                random_offset = self.h.uniform(0, window_seconds)
                exec_time = window_start + timedelta(seconds=random_offset)
            else:
                exec_time = window_start

            scheduled.append((exec_time, action))

        scheduled.sort(key=lambda x: x[0])
        return scheduled

    # ================================================================
    # 动作处理函数
    # ================================================================

    def _handle_open_wechat(self, params: dict) -> bool:
        """打开微信，模拟查看消息"""
        self.wc.ensure_wechat_home()
        # 模拟查看消息列表的停留时间
        self.h.random_sleep(1.0, 3.0)
        return True

    def _handle_scroll_moments(self, params: dict) -> bool:
        """刷朋友圈"""
        if not self.wc.open_moments():
            return False
        times = params.get("times") or self.h.randint(6, 16)
        self.wc.scroll_moments(times)
        self.wc.d.press("back")
        return True

    def _handle_like_moment(self, params: dict) -> bool:
        """点赞朋友圈（OCR 时间戳定位方案）"""
        count = params.get("count", 1)
        if isinstance(count, tuple):
            count = self.h.randint(*count)
        success = 0
        for _ in range(count):
            idx = self.h.randint(0, min(5, count)) if count > 1 else 0
            if self.wc.like_moment(post_index=idx):
                success += 1
            if _ < count - 1:
                self.h.random_sleep(0.5, 2.0)
        return success > 0

    def _handle_comment_moment(self, params: dict) -> bool:
        """评论朋友圈（LLM 优先，模板降级）"""
        text = params.get("text", "")
        if not text:
            try:
                from content.llm_client import LLMClient
                text = LLMClient().generate_comment(self.persona)
            except Exception:
                from content.comment_templates import CommentTemplateManager
                text = CommentTemplateManager().get_comment(self.persona)
        return self.wc.comment_moment(text)

    def _handle_browse_moments_interact(self, params: dict) -> bool:
        """浏览朋友圈并随机点赞+评论（OCR 方案）"""
        duration = params.get("duration", 300)
        comment_text = params.get("comment_text", "")
        like_rate = params.get("like_rate", 0.35)
        result = self.wc.browse_moments_interact(
            duration_seconds=duration,
            comment_text=comment_text,
            like_rate=like_rate,
        )
        return result.get("liked", 0) > 0 or result.get("commented", 0) > 0

    def _handle_post_moment(self, params: dict) -> bool:
        """发朋友圈（LLM 优先，模板降级）"""
        text = params.get("text", "")
        if not text:
            try:
                from content.llm_client import LLMClient
                text = LLMClient().generate_post_text(self.persona)
            except Exception:
                from content.post_templates import PostTemplateManager
                text = PostTemplateManager().get_random_post(self.persona)
        return self.wc.post_moment(text)

    def _handle_scroll_channels(self, params: dict) -> bool:
        """刷视频号（OCR + 概率点赞）"""
        from core.channels_browser import ChannelsBrowser
        times = params.get("times") or self.h.randint(3, 8)
        like_rate = params.get("like_rate", 0.2)
        browser = ChannelsBrowser(self.wc.d, account_id=self.account_id)
        browser.browse(scroll_count=times, like_rate=like_rate)
        return True

    def _handle_like_channel(self, params: dict) -> bool:
        """点赞视频号"""
        from core.channels_browser import ChannelsBrowser
        browser = ChannelsBrowser(self.wc.d, account_id=self.account_id)
        return browser._like_current()

    def _handle_read_article(self, params: dict) -> bool:
        """阅读公众号文章（OCR 方案）"""
        from core.public_account_browser import PublicAccountBrowser
        duration = params.get("duration", 180)
        browser = PublicAccountBrowser(self.wc.d, account_id=self.account_id)
        browser.browse(duration_seconds=duration)
        return True

    def _handle_favorite_article(self, params: dict) -> bool:
        """收藏文章"""
        return self.wc.favorite_article()

    def _handle_global_search(self, params: dict) -> bool:
        """全局搜索"""
        keyword = params.get("keyword", "")
        if not keyword:
            from content.search_keywords import SearchKeywordManager
            keyword = SearchKeywordManager().get_random_keyword(self.persona)
        return self.wc.global_search(keyword)

    def _handle_send_message(self, params: dict) -> bool:
        """发送聊天消息（OCR+IME 方案）"""
        from core.message_sender import MessageSender

        contact = params.get("contact", "")
        if not contact:
            friend = self.db.get_random_friend(self.account_id)
            if not friend:
                logger.debug(f"[{self.account_id}] 没有好友可聊天")
                return True
            contact = friend["friend_name"]

        text = params.get("text", "")
        if not text:
            try:
                from content.llm_client import LLMClient
                text = LLMClient().generate_chat_text(
                    self.persona,
                    context=self.h.choice(["small_talk", "greeting", "share"]),
                )
            except Exception:
                from content.chat_templates import ChatTemplateManager
                text = ChatTemplateManager().get_random_chat(
                    self.h.choice(["small_talk", "greeting", "share"]),
                    self.persona,
                )

        sender = MessageSender(self.wc.d, account_id=self.account_id)
        return sender.send(contact=contact, message=text)

    def _handle_send_image(self, params: dict) -> bool:
        """发送图片（OCR+OpenCV 方案）"""
        from core.image_sender import ImageSender

        contact = params.get("contact", "")
        if not contact:
            friend = self.db.get_random_friend(self.account_id)
            if not friend:
                logger.debug(f"[{self.account_id}] 没有好友可发送图片")
                return True
            contact = friend["friend_name"]

        count = params.get("count", 1)
        sender = ImageSender(self.wc.d, account_id=self.account_id)
        return sender.send(contact=contact, photo_count=count)

    def _handle_send_voice(self, params: dict) -> bool:
        """发送语音"""
        contact = params.get("contact", "")
        if contact:
            self.wc.open_chat(contact)
        duration = params.get("duration")
        return self.wc.send_voice(duration)

    def _handle_send_emoji(self, params: dict) -> bool:
        """发送表情"""
        return self.wc.send_emoji()

    def _handle_make_payment(self, params: dict) -> bool:
        """打开支付页面（模拟支付行为）"""
        return self.wc.open_payment_page()

    def _handle_open_favorites(self, params: dict) -> bool:
        """打开收藏夹页面"""
        return self.wc.open_favorites()

    def _handle_browse_favorites(self, params: dict) -> bool:
        """浏览收藏夹（OCR + CLAHE 方案）"""
        from core.favorites_browser import FavoritesBrowser
        duration = params.get("duration", 180)
        browser = FavoritesBrowser(self.wc.d, account_id=self.account_id)
        browser.browse(duration_seconds=duration)
        return True

    def _handle_idle(self, params: dict) -> bool:
        """空闲（保持在线但不操作）"""
        idle_sec = self.h.uniform(
            params.get("min_seconds", 60),
            params.get("max_seconds", 300),
        )
        time.sleep(idle_sec)
        return True

    def _handle_sleep(self, params: dict) -> bool:
        """睡眠时段，不执行任何操作"""
        return True

    # ================================================================
    # 限量检查
    # ================================================================

    def _check_daily_limit(self, action_type: str, limit: int) -> bool:
        """检查当日操作是否超限"""
        count = self._daily_counts.get(action_type, 0)
        if count >= limit:
            logger.debug(
                f"[{self.account_id}] {action_type} 已达当日上限 ({limit})"
            )
            return False
        return True

    def _increment_daily_count(self, action_type: str):
        """增加当日操作计数"""
        self._daily_counts[action_type] = self._daily_counts.get(action_type, 0) + 1
