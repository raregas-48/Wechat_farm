"""
OpenCV 视觉定位模块 — 替代像素扫描，使用模板匹配和图像识别。

解决微信屏蔽 UiAutomation 后的 UI 定位问题。
所有方法基于截图 + OpenCV 分析，不依赖无障碍服务。
"""

import time, cv2, numpy as np
from PIL import Image
import uiautomator2 as u2


class CVLocator:
    """基于 OpenCV 的视觉定位器。"""

    def __init__(self, d: u2.Device):
        self.d = d

    def screenshot_cv(self):
        """获取当前屏幕截图为 OpenCV BGR 格式。"""
        pil_img = self.d.screenshot(format="pillow")
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    def screenshot_gray(self):
        """获取灰度截图。"""
        return cv2.cvtColor(self.screenshot_cv(), cv2.COLOR_BGR2GRAY)

    # ================================================================
    # 模板匹配
    # ================================================================

    def match_template(self, template_path: str, threshold: float = 0.6):
        """
        在屏幕上查找模板图像，返回最佳匹配位置。

        Args:
            template_path: 模板图片路径
            threshold: 匹配阈值 (0-1)

        Returns:
            (x, y) 中心坐标，或 None
        """
        screen = self.screenshot_gray()
        template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            return None

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            h, w = template.shape
            return (max_loc[0] + w // 2, max_loc[1] + h // 2)
        return None

    def match_all(self, template_path: str, threshold: float = 0.6, max_count: int = 10):
        """查找所有匹配位置，按匹配度降序排列。"""
        screen = self.screenshot_gray()
        template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            return []

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        h, w = template.shape
        locations = []
        flat = result.ravel()
        indices = np.argsort(flat)[::-1]  # 从高到低排序

        seen = set()
        for idx in indices:
            if len(locations) >= max_count:
                break
            val = flat[idx]
            if val < threshold:
                break
            y, x = divmod(idx, result.shape[1])
            # 去重：相邻位置只保留一个
            key = (x // 20, y // 20)
            if key not in seen:
                seen.add(key)
                locations.append({"x": x + w // 2, "y": y + h // 2, "score": float(val)})

        return sorted(locations, key=lambda l: l["y"])  # 按 y 排序

    # ================================================================
    # 朋友圈专用
    # ================================================================

    def find_dots_buttons(self, max_count: int = 10):
        """
        查找朋友圈中所有 "..." 按钮。
        使用模板匹配在右侧区域搜索。
        """
        # 基于灰度特征：在 x>1000 区域搜索小暗色图案
        screen = self.screenshot_gray()
        h, w = screen.shape

        # 在右侧区域使用边缘检测找小圆形/椭圆形
        right_region = screen[:, 1000:]
        # 二值化找到暗色小图案
        _, thresh = cv2.threshold(right_region, 180, 255, cv2.THRESH_BINARY_INV)
        # 形态学操作连接邻近像素
        kernel = np.ones((3, 3), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        # 找轮廓
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            # 过滤：太小或太大的不是按钮
            if 5 < cw < 50 and 5 < ch < 30:
                # 位于帖子区域 (y=300~2400)
                real_x = x + 1000 + cw // 2
                real_y = y + ch // 2
                if 300 < real_y < 2400:
                    candidates.append({"x": real_x, "y": real_y, "w": cw, "h": ch})

        # 按 y 排序并去重
        candidates.sort(key=lambda c: c["y"])
        result = []
        last_y = -100
        for c in candidates:
            if c["y"] - last_y > 20:  # 至少相隔 20px
                result.append(c)
                last_y = c["y"]

        return result[:max_count]

    def open_menu_cv(self) -> bool:
        """使用 OpenCV 找到 '...' 按钮并打开菜单。"""
        dots = self.find_dots_buttons(max_count=5)
        if not dots:
            return False

        # 尝试点击找到的候选点
        for d in dots[:5]:
            self.d.click(d["x"], d["y"])
            time.sleep(1.5)
            screen = self.screenshot_gray()
            # 检查菜单是否打开（屏幕中心变暗）
            h, w = screen.shape
            center = np.mean(screen[h//2-50:h//2+50, w//2-50:w//2+50])
            if center < 200:
                return True

        return False

    def find_menu_buttons_cv(self):
        """
        菜单打开后，用 OpenCV 找赞和评论按钮。
        菜单面板在屏幕底部，白色背景上有文字。
        """
        screen = self.screenshot_gray()
        h, w = screen.shape

        # 菜单区域：y=1050~1500
        menu_region = screen[1050:1500, :]
        # 二值化找文字
        _, thresh = cv2.threshold(menu_region, 100, 255, cv2.THRESH_BINARY_INV)
        # 膨胀连接字符
        kernel = np.ones((5, 3), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=1)

        # 找轮廓
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        text_boxes = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if 20 < cw < 200 and 20 < ch < 80:
                text_boxes.append({
                    "x": x + cw // 2,
                    "y": y + 1050 + ch // 2,
                    "w": cw, "h": ch
                })

        # 左侧为评论，右侧为赞
        result = {}
        for box in text_boxes:
            if box["x"] < 600:
                if "comment" not in result or box["x"] < result["comment"]["x"]:
                    result["comment"] = (box["x"], box["y"])
            else:
                if "like" not in result:
                    result["like"] = (box["x"], box["y"])

        return result
