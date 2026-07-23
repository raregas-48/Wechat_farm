"""
信任积累期脚本（第1-2周）— 只看不互动，建立基础信任。

行为特征:
    - 刷朋友圈但不点赞/评论
    - 刷视频号
    - 阅读公众号文章并收藏
    - 全局搜索
    - 小额支付（打开收付款页面）
    - 23:00-07:00 不活跃
"""

from scripts.base_script import BaseScript, ActionType, Action, DailyScript


class TrustBuildingScript(BaseScript):
    """信任积累期 — 纯消费不生产"""

    STAGE_NAME = "trust_building"

    def _build_weekday_script(self) -> DailyScript:
        return DailyScript(
            stage=self.STAGE_NAME,
            is_weekend=False,
            actions=[
                # 08:00 - 打开微信，查看消息
                Action(ActionType.OPEN_WECHAT, "07:30", "08:30", (180, 480)),
                # 08:30 - 刷朋友圈（不互动）
                Action(ActionType.SCROLL_MOMENTS, "08:00", "09:00", (300, 600)),
                # 10:00 - 全局搜索（模拟找东西）
                Action(ActionType.GLOBAL_SEARCH, "09:30", "10:30", (60, 180)),
                # 12:00 - 刷视频号
                Action(ActionType.SCROLL_CHANNELS, "11:30", "13:00", (600, 900)),
                # 12:30 - 阅读公众号文章并收藏
                Action(ActionType.READ_ARTICLE, "12:00", "13:30", (300, 600)),
                Action(ActionType.FAVORITE_ARTICLE, "12:30", "13:30", (30, 120)),
                # 14:00 - 搜索小程序
                Action(ActionType.GLOBAL_SEARCH, "13:30", "15:00", (60, 180),
                       params={"keyword_category": "mini_program"}),
                # 16:00 - 打开收藏夹浏览
                Action(ActionType.BROWSE_FAVORITES, "15:30", "16:30", (120, 300)),
                # 17:00 - 打开支付页面
                Action(ActionType.MAKE_PAYMENT, "16:30", "18:00", (60, 300)),
                # 19:00 - 刷朋友圈
                Action(ActionType.SCROLL_MOMENTS, "18:30", "20:00", (300, 600)),
                # 20:30 - 刷视频号
                Action(ActionType.SCROLL_CHANNELS, "20:00", "21:30", (300, 600)),
                # 22:00 - 睡前最后刷朋友圈
                Action(ActionType.SCROLL_MOMENTS, "21:30", "22:30", (180, 480)),
                # 23:00-07:00 - 不活跃
                Action(ActionType.SLEEP, "23:00", "07:00", (0, 0)),
            ],
        )

    def _build_weekend_script(self) -> DailyScript:
        """周末版：晚起晚睡，行为更悠闲"""
        return DailyScript(
            stage=self.STAGE_NAME,
            is_weekend=True,
            actions=[
                # 09:00 - 晚起，打开微信
                Action(ActionType.OPEN_WECHAT, "08:30", "10:00", (180, 480)),
                # 10:00 - 刷朋友圈
                Action(ActionType.SCROLL_MOMENTS, "09:30", "11:00", (300, 900)),
                # 12:00 - 搜索
                Action(ActionType.GLOBAL_SEARCH, "11:00", "13:00", (60, 180)),
                # 13:00 - 刷视频号
                Action(ActionType.SCROLL_CHANNELS, "12:30", "14:30", (600, 1200)),
                # 15:00 - 阅读公众号文章
                Action(ActionType.READ_ARTICLE, "14:30", "16:30", (300, 600)),
                Action(ActionType.FAVORITE_ARTICLE, "15:00", "16:30", (30, 120)),
                # 17:00 - 收藏夹
                Action(ActionType.BROWSE_FAVORITES, "16:00", "18:00", (120, 300)),
                # 19:00 - 支付页面
                Action(ActionType.MAKE_PAYMENT, "18:00", "20:00", (60, 300)),
                # 20:00 - 刷朋友圈
                Action(ActionType.SCROLL_MOMENTS, "19:30", "21:00", (300, 900)),
                # 21:30 - 刷视频号
                Action(ActionType.SCROLL_CHANNELS, "20:30", "22:30", (300, 600)),
                # 23:00 - 睡前朋友圈
                Action(ActionType.SCROLL_MOMENTS, "22:00", "23:30", (180, 480)),
                # 00:00-08:00 - 不活跃
                Action(ActionType.SLEEP, "00:00", "08:00", (0, 0)),
            ],
        )
