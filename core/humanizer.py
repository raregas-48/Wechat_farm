"""
拟人化引擎 — 生成符合真人操作特征的随机参数。

覆盖维度:
    1. 点击坐标 — 正态分布偏移（非均匀分布）
    2. 滑动轨迹 — Bézier 曲线 + 缓入缓出速度
    3. 操作间隔 — 对数正态分布
    4. 输入节奏 — 随机停顿 + 偶尔的打错删除重打
    5. 犹豫行为 — 偶尔点错再返回
"""

import math
import random
import time
from typing import Optional

import uiautomator2 as u2

from utils.logger import get_logger

logger = get_logger("humanizer")


class Humanizer:
    """
    拟人化操作参数生成器。

    每个账号应使用不同的 seed，确保行为模式差异化。

    使用方式:
        h = Humanizer(seed=42)
        x, y = h.human_offset(center_x=540, center_y=960)
        h.random_sleep(1.0, 3.0)
        h.human_swipe(d, "up")
    """

    def __init__(self, seed: int = None):
        self.random = random.Random(seed)
        self._last_action_time = time.time()

    # ================================================================
    # 坐标拟人化
    # ================================================================

    def human_offset(
        self,
        center_x: int,
        center_y: int,
        sigma: float = 5.0,
    ) -> tuple[int, int]:
        """
        对点击坐标施加正态分布偏移。

        使用 Box-Muller 变换生成正态分布随机数，
        使点击分布集中在中心附近，而非均匀散开。

        Args:
            center_x: 控件中心 X 坐标
            center_y: 控件中心 Y 坐标
            sigma: 标准差（像素），默认 5px

        Returns:
            (偏移后的 x, 偏移后的 y)
        """
        # Box-Muller 变换
        u1 = max(self.random.random(), 1e-10)
        u2 = self.random.random()
        z_x = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

        u1, u2 = self.random.random(), self.random.random()
        u1 = max(u1, 1e-10)
        z_y = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

        offset_x = int(z_x * sigma)
        offset_y = int(z_y * sigma)

        # 限制最大偏移
        offset_x = max(-20, min(20, offset_x))
        offset_y = max(-20, min(20, offset_y))

        return center_x + offset_x, center_y + offset_y

    # ================================================================
    # 时间间隔拟人化
    # ================================================================

    def random_sleep(self, min_sec: float, max_sec: float):
        """
        对数正态分布睡眠。

        真人操作间隔不是均匀分布，而是对数正态分布——
        大部分间隔偏短，少数偏长（分心、犹豫等）。

        Args:
            min_sec: 最小睡眠秒数
            max_sec: 最大睡眠秒数
        """
        median = math.sqrt(min_sec * max_sec)
        mu = math.log(median)
        sigma = 0.5

        sleep_time = self.random.lognormvariate(mu, sigma)
        sleep_time = max(min_sec, min(sleep_time, max_sec))
        time.sleep(sleep_time)

    def action_interval(self, action_type: str = "general") -> float:
        """
        生成两个操作之间的间隔时间。

        不同动作类型有不同的生理反应时间：
          - click: 点击后的视觉确认反应时间 0.8~2.5s
          - scroll: 滑动后的内容阅读时间 1.5~5.0s
          - type_start: 打字前思考时间 1.0~3.0s

        Args:
            action_type: 动作类型

        Returns:
            间隔秒数
        """
        intervals = {
            "click":       (0.8, 2.5),
            "scroll":      (1.5, 5.0),
            "type_start":  (1.0, 3.0),
            "tab_switch":  (0.5, 1.5),
            "general":     (0.5, 3.0),
        }
        min_t, max_t = intervals.get(action_type, intervals["general"])
        return self._lognormal_sample(min_t, max_t)

    def _lognormal_sample(self, min_val: float, max_val: float) -> float:
        """生成对数正态分布随机值"""
        median = math.sqrt(min_val * max_val)
        mu = math.log(median) if median > 0 else 0
        sigma = 0.5
        value = self.random.lognormvariate(mu, sigma)
        return max(min_val, min(value, max_val))

    # ================================================================
    # 滑动拟人化
    # ================================================================

    def bezier_swipe_path(
        self,
        start: tuple,
        end: tuple,
        num_points: int = 30,
    ) -> list[tuple]:
        """
        生成三次 Bézier 曲线滑动路径。

        加入随机控制点偏移 + 每个采样点的微小扰动，
        使滑动轨迹呈现自然弧度，而非直线。

        Args:
            start: 起点 (x, y)
            end: 终点 (x, y)
            num_points: 采样点数

        Returns:
            路径点列表 [(x1, y1), (x2, y2), ...]
        """
        dx = end[0] - start[0]
        dy = end[1] - start[1]

        # 随机控制点（在路径的 25% 和 75% 处，横向偏移）
        cp1_x = start[0] + dx * self.random.uniform(0.2, 0.4)
        cp1_y = start[1] + dy * self.random.uniform(-0.1, 0.1) + self.random.randint(-30, 30)
        cp2_x = start[0] + dx * self.random.uniform(0.6, 0.8)
        cp2_y = start[1] + dy * self.random.uniform(-0.1, 0.1) + self.random.randint(-30, 30)

        points = []
        for i in range(num_points):
            t_linear = i / (num_points - 1)
            # Ease-in⁴: 起点附近点数更稀疏(极快启动) → 终点附近点数密集(减速)
            # 幂次越高起点越快，配合缩短的 duration 彻底避免长按判定
            t = 1 - (1 - t_linear) ** 4
            # 三次 Bézier
            x = (
                (1 - t) ** 3 * start[0]
                + 3 * (1 - t) ** 2 * t * cp1_x
                + 3 * (1 - t) * t ** 2 * cp2_x
                + t**3 * end[0]
            )
            y = (
                (1 - t) ** 3 * start[1]
                + 3 * (1 - t) ** 2 * t * cp1_y
                + 3 * (1 - t) * t ** 2 * cp2_y
                + t**3 * end[1]
            )
            # 微小扰动
            x += self.random.gauss(0, 1.5)
            y += self.random.gauss(0, 1.5)
            points.append((int(x), int(y)))

        return points

    def human_swipe(
        self,
        d: u2.Device,
        direction: str = "up",
        distance: float = 0.6,
        duration: Optional[float] = None,
    ):
        """
        执行拟人化滑动。

        自动生成 Bézier 路径，分段执行，
        速度曲线呈缓入缓出特征。

        Args:
            d: uiautomator2 设备连接
            direction: "up" / "down" / "left" / "right"
            distance: 滑动距离占屏幕高度的比例
            duration: 滑动总耗时（秒），None 则随机
        """
        w, h = d.window_size()

        if direction == "up":
            sx = w // 2 + self.random.randint(-40, 40)
            sy = int(h * 0.78) + self.random.randint(-30, 30)
            ex = w // 2 + self.random.randint(-40, 40)
            ey = int(h * max(0.1, 0.78 - distance)) + self.random.randint(-20, 20)
        elif direction == "down":
            sx = w // 2 + self.random.randint(-40, 40)
            sy = int(h * 0.25) + self.random.randint(-20, 20)
            ex = w // 2 + self.random.randint(-40, 40)
            ey = int(h * min(0.9, 0.25 + distance)) + self.random.randint(-20, 20)
        elif direction == "left":
            sx = int(w * 0.85) + self.random.randint(-20, 20)
            sy = h // 2 + self.random.randint(-50, 50)
            ex = int(w * max(0.05, 0.85 - distance)) + self.random.randint(-20, 20)
            ey = h // 2 + self.random.randint(-50, 50)
        elif direction == "right":
            sx = int(w * 0.15) + self.random.randint(-20, 20)
            sy = h // 2 + self.random.randint(-50, 50)
            ex = int(w * min(0.95, 0.15 + distance)) + self.random.randint(-20, 20)
            ey = h // 2 + self.random.randint(-50, 50)
        else:
            sx, sy, ex, ey = w // 2, int(h * 0.8), w // 2, int(h * 0.2)

        # 边界保护
        sx, sy = max(10, min(sx, w - 10)), max(10, min(sy, h - 10))
        ex, ey = max(10, min(ex, w - 10)), max(10, min(ey, h - 10))

        if duration is None:
            duration = self.random.uniform(0.07, 0.18)

        # 使用 uiautomator2 的 swipe 配合 points（取关键采样点）
        # num_points=25: 配合 ease-out 提供足够分辨率的减速阶段
        path = self.bezier_swipe_path((sx, sy), (ex, ey), num_points=25)
        d.swipe_points(path, duration=duration)

    # ================================================================
    # 犹豫 & 误操作模拟
    # ================================================================

    def should_hesitate(self, probability: float = 0.03) -> bool:
        """
        判断是否应加入"犹豫"行为（比如点开后停一下再看）。

        Args:
            probability: 触发概率，默认 3%
        """
        return self.random.random() < probability

    def should_mistap(self, probability: float = 0.01) -> bool:
        """
        判断是否应模拟"点错再返回"。

        Args:
            probability: 触发概率，默认 1%
        """
        return self.random.random() < probability

    def simulate_mistap_and_back(self, d: u2.Device):
        """
        模拟误操作：随机点一个位置，然后反应一下按返回。
        """
        w, h = d.window_size()
        wrong_x = self.random.randint(80, w - 80)
        wrong_y = self.random.randint(150, h - 150)
        d.click(wrong_x, wrong_y)
        self.random_sleep(0.8, 2.0)  # 反应过来需要时间
        d.press("back")
        logger.debug("模拟误操作：点错后返回")

    # ================================================================
    # 随机辅助方法
    # ================================================================

    def randint(self, a: int, b: int) -> int:
        """在 [a, b] 范围内随机取整数"""
        return self.random.randint(a, b)

    def uniform(self, a: float, b: float) -> float:
        """在 [a, b] 范围内随机取浮点数"""
        return self.random.uniform(a, b)

    def choice(self, seq: list):
        """从列表中随机选一个元素"""
        return self.random.choice(seq)

    def gauss(self, mu: float, sigma: float) -> float:
        """生成正态分布随机数"""
        return self.random.gauss(mu, sigma)

    def weighted_choice(self, items: list, weights: list[float]):
        """加权随机选择"""
        return self.random.choices(items, weights=weights, k=1)[0]

    def generate_wechat_sport_steps(self, is_weekend: bool = False) -> int:
        """
        生成当日微信运动步数（供记录参考）。
        实际步数由手机传感器自然产生，此为模拟参考值。

        Args:
            is_weekend: 是否周末

        Returns:
            步数建议值
        """
        if is_weekend:
            base = self.random.randint(1500, 12000)
        else:
            base = self.random.randint(3000, 15000)
        return base
