"""
截图实时定位引擎 — 通过截图+像素分析在微信界面上定位目标。

用于解决微信屏蔽 UiAutomation 后无法通过控件树定位的问题。
所有方法基于截图像素分析，不依赖无障碍服务。

使用方式:
    locator = ScreenLocator(d)
    pos = locator.find_text("朋友圈")  # 返回 (x, y) 或 None
    locator.click_text("朋友圈")       # 找到并点击
"""

import time
from typing import Optional, Tuple

import uiautomator2 as u2
from PIL import Image


class ScreenLocator:
    """基于截图的实时元素定位器。"""

    def __init__(self, d: u2.Device):
        self.d = d

    def screenshot(self) -> Image.Image:
        """获取当前屏幕截图（PIL Image）。"""
        return self.d.screenshot(format="pillow")

    # ================================================================
    # 像素扫描
    # ================================================================

    def find_dark_region(
        self,
        x_start: int, x_end: int,
        y_start: int, y_end: int,
        img: Image.Image = None,
        threshold: int = 80,
        min_pixels: int = 20,
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        在指定区域内查找暗色像素密集区（通常对应文字/图标）。

        Returns:
            (left, top, right, bottom) 或 None
        """
        if img is None:
            img = self.screenshot()
        # Find first dark pixel, then expand to find bounding box
        best_x = best_y = None
        for y in range(y_start, y_end, 3):
            for x in range(x_start, x_end, 3):
                r, g, b = img.getpixel((x, y))[:3]
                if r < threshold and g < threshold and b < threshold:
                    best_x, best_y = x, y
                    break
            if best_x is not None:
                break

        if best_x is None:
            return None

        # Expand to find region bounds
        left = right = best_x
        top = bottom = best_y
        for y in range(max(y_start, best_y - 30), min(y_end, best_y + 30), 2):
            for x in range(max(x_start, best_x - 40), min(x_end, best_x + 40), 2):
                r, g, b = img.getpixel((x, y))[:3]
                if r < threshold and g < threshold and b < threshold:
                    left = min(left, x)
                    right = max(right, x)
                    top = min(top, y)
                    bottom = max(bottom, y)

        if right - left < 5 or bottom - top < 5:
            return None
        return (left, top, right, bottom)

    def find_icon_center(
        self,
        x_start: int, x_end: int,
        y_start: int, y_end: int,
        img: Image.Image = None,
    ) -> Optional[Tuple[int, int]]:
        """
        查找区域内非白/非灰色像素密集区的中心（对应图标位置）。
        """
        if img is None:
            img = self.screenshot()
        xs, ys = [], []
        for y in range(y_start, y_end, 2):
            for x in range(x_start, x_end, 2):
                r, g, b = img.getpixel((x, y))[:3]
                if r < 230 or g < 230 or b < 230:
                    xs.append(x)
                    ys.append(y)
        if not xs:
            return None
        return (sum(xs) // len(xs), sum(ys) // len(ys))

    # ================================================================
    # 高层定位方法
    # ================================================================

    def find_search_icon(self) -> Optional[Tuple[int, int]]:
        """
        定位微信首页右上角的搜索图标。
        在顶部栏右侧约 x=880-980, y=130-180 区域查找。
        """
        img = self.screenshot()
        w, h = img.size
        # 搜索图标在右上角，+ 按钮左侧
        return self.find_icon_center(
            int(w * 0.68), int(w * 0.80),
            int(h * 0.045), int(h * 0.070),
            img=img,
        )

    def find_add_button(self) -> Optional[Tuple[int, int]]:
        """
        定位微信首页右上角的 + 按钮（红色/橙色）。
        """
        img = self.screenshot()
        w, h = img.size
        # 搜索红色像素（+ 按钮是红色）
        for y in range(int(h * 0.045), int(h * 0.070), 2):
            for x in range(int(w * 0.78), int(w * 0.88), 2):
                r, g, b = img.getpixel((x, y))[:3]
                if r > 200 and g < 120 and b < 120:
                    return (x, y)
        return None

    def find_search_input(self) -> Optional[Tuple[int, int, int, int]]:
        """
        定位搜索页面的输入框。搜索框在顶部，有"搜索"提示文字。
        Returns (left, top, right, bottom) of the input area.
        """
        img = self.screenshot()
        w, h = img.size
        # 搜索输入框在顶部，约 y=90-200
        region = self.find_dark_region(
            int(w * 0.15), int(w * 0.85),
            int(h * 0.03), int(h * 0.09),
            img=img,
        )
        return region

    def find_search_results(
        self,
        max_results: int = 5,
    ) -> list[dict]:
        """
        定位搜索页面的结果列表。
        返回 [{name: str, x: int, y: int, type: str}, ...]

        通过扫描行结构来识别不同的结果条目。
        """
        img = self.screenshot()
        w, h = img.size
        results = []

        # 搜索结果从 y~250 开始，每个条目约 120-140px 高
        # 条目包含左侧图标 + 右侧文字
        result_start_y = int(h * 0.09)
        result_end_y = int(h * 0.60)

        # 扫描暗色像素行作为文本行
        text_rows = []
        prev_dark = False
        for y in range(result_start_y, result_end_y, 2):
            dark_count = 0
            for x in range(int(w * 0.15), int(w * 0.70), 4):
                r, g, b = img.getpixel((x, y))[:3]
                if r < 80 and g < 80 and b < 80:
                    dark_count += 1
            if dark_count > 3:
                if not prev_dark:
                    text_rows.append(y)
                prev_dark = True
            else:
                prev_dark = False

        # Group text rows into items (rows close together)
        items = []
        if text_rows:
            current_group = [text_rows[0]]
            for y in text_rows[1:]:
                if y - current_group[-1] < 80:
                    current_group.append(y)
                else:
                    items.append(sum(current_group) // len(current_group))
                    current_group = [y]
            if current_group:
                items.append(sum(current_group) // len(current_group))

        for i, center_y in enumerate(items[:max_results]):
            results.append({
                "index": i,
                "y": center_y,
                "x": int(w * 0.4),  # approximate center-x for text
            })

        return results

    def click_center(self, x: int, y: int, sleep: float = 0.5):
        """点击指定坐标。"""
        self.d.click(x, y)
        time.sleep(sleep)

    # ================================================================
    # 朋友圈帖子定位（头像检测）
    # ================================================================

    def find_avatars(self) -> list[int]:
        """
        找到朋友圈页面所有头像的 Y 坐标。

        头像特征：左侧 x=30~200 区域内的圆形/方形非白色像素块。
        每个头像对应一个帖子。

        Returns:
            头像中心 Y 坐标列表，从上到下排列
        """
        img = self.screenshot()
        w = img.size[0]

        avatar_rows = []
        for y in range(200, 2400, 3):
            non_white = 0
            for x in range(30, 250, 4):
                r, g, b = img.getpixel((x, y))[:3]
                if r < 230 or g < 230 or b < 230:
                    non_white += 1
            if non_white > 5:  # 至少 5 个采样点非白色
                avatar_rows.append(y)

        if not avatar_rows:
            return []

        # 将相邻行分组成头像区域
        groups = [[avatar_rows[0]]]
        for y in avatar_rows[1:]:
            if y - groups[-1][-1] < 80:  # 80px 内属于同一头像
                groups[-1].append(y)
            else:
                groups.append([y])

        # 过滤太小的组（噪音），取每组的 y 中心
        avatars = []
        for g in groups:
            if len(g) > 3:  # 至少 4 行（头像至少 12px 高）
                avatars.append((g[0], g[-1]))

        return [sum(pair) // 2 for pair in avatars]

    def find_dots_button(self, post_index: int = 0) -> tuple[int, int] | None:
        """
        找到指定帖子的 "..." 菜单按钮。

        用头像定位：dots_x=1140, dots_y=下一帖子头像上方 20px。
        最后一个帖子用分割线定位。

        Returns:
            (x, y) 或 None
        """
        avatars = self.find_avatars()
        if not avatars:
            return None

        if post_index >= len(avatars):
            return None

        # 用下一帖子的头像定位 ... 按钮
        # 实测: dots 在下一头像上方约 180px (范围 175-190)
        if post_index + 1 < len(avatars):
            next_avatar_y = avatars[post_index + 1]
            dots_y = next_avatar_y - 180
        else:
            # 最后一个帖子：用分割线
            dividers = self.find_post_dividers()
            if dividers:
                dots_y = dividers[-1] + 56
            else:
                dots_y = avatars[post_index] + 500  # fallback

        return (1140, dots_y)

    def find_post_dividers(self, y_start: int = 300, y_end: int = 2400) -> list[int]:
        """查找帖子间的灰色分割线，作为 fallback 使用。"""
        img = self.screenshot()
        w = img.size[0]
        dividers = []
        for y in range(y_start, y_end, 2):
            gray = sum(1 for x in range(0, w, 10) if all(220 < c < 250 for c in img.getpixel((x, y))[:3]))
            if gray > 45:
                dividers.append(y)
        if not dividers:
            return []
        groups = [[dividers[0]]]
        for d in dividers[1:]:
            if d - groups[-1][-1] < 20:
                groups[-1].append(d)
            else:
                groups.append([d])
        return [sum(g) // len(g) for g in groups if len(g) > 3]

    def find_menu_buttons(self) -> dict:
        """
        菜单打开后，截图定位赞和评论按钮。

        菜单底部弹出后，按钮分布在 x 轴：
        - 赞位于右侧，x 偏移 +20 左右
        - 评论位于左侧，x 偏移 -700 左右

        Returns:
            {"like": (x, y), "comment": (x, y)} 或空字典
        """
        img = self.screenshot()
        w, h = img.size

        # 菜单是底部白色弹出层，扫描 y=1100~1400 区域
        # 找两簇深色像素：左簇(评论)、右簇(赞)
        buttons = {}
        for scan_y in range(1100, 1450, 3):
            left_dark = []
            right_dark = []
            for scan_x in range(50, w, 4):
                r, g, b = img.getpixel((scan_x, scan_y))[:3]
                if r < 100 and g < 100 and b < 100:
                    if scan_x < 700:
                        left_dark.append(scan_x)
                    else:
                        right_dark.append(scan_x)
            if left_dark and not buttons:
                cx = sum(left_dark) // len(left_dark)
                buttons["comment"] = (cx, scan_y)
            if right_dark and "like" not in buttons:
                cx = sum(right_dark) // len(right_dark)
                buttons["like"] = (cx, scan_y)
            if len(buttons) == 2:
                break

        return buttons

    def open_post_menu(self, post_index: int = 0, attempt: int = 0) -> bool:
        """大范围扫描右侧找 '...' 并打开菜单。"""
        img = self.screenshot()
        w, h = img.size

        # 扫描区域：右侧 x=1080~1200, y=1000~2100
        # 用不同步长覆盖更多位置
        step_y = 30 + attempt * 8  # 每次调用用不同步长
        for y in range(1000, 2100, step_y):
            for x in [1120, 1080, 1160, 1100, 1180]:
                self.d.click(x, y)
                time.sleep(0.8)  # 快速检查
                check = self.screenshot()
                if sum(check.getpixel((w // 2, h // 2))[:3]) < 650:
                    return True
        return False

    def find_and_click_result(self, search_text: str) -> bool:
        """
        在搜索结果中找到包含特定文字的条目并点击。
        由于无法读取文字，使用实时截图 + 区域匹配。

        策略：点击搜索结果中第1-3个条目，逐个尝试是否打开了正确页面。
        """
        results = self.find_search_results(max_results=5)
        if not results:
            return False

        # 尝试点击前几个结果中的目标类型条目
        # 搜索结果的排序通常是：最常使用、联系人、公众号、聊天记录等
        for r in results[:4]:
            self.click_center(r["x"], r["y"], sleep=1.5)
            # 简单验证：检查是否离开了搜索页面
            img = self.screenshot()
            w, h = img.size
            # 检查顶部是否还有搜索框（有=还在搜索页，无=已跳转）
            top_color = img.getpixel((w // 2, int(h * 0.05)))[:3]
            # 如果 top 区域颜色变化大，说明可能已跳转
            if top_color[0] < 200 or top_color[1] < 200:
                return True
            self.d.press("back")
            time.sleep(0.5)

        return False
