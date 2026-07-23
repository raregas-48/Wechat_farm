"""
全局搜索模块 — OpenCV + ADBKeyboard IME。

工作流:
  1. 冷启动微信 → 确保在"微信"Tab
  2. 点击右上角搜索图标（放大镜，紧挨"+"按钮）
  3. 验证搜索页打开（页面差异对比）
  4. ADBKeyboard IME 注入关键词 → Enter 搜索

使用方式:
    from core.search_helper import SearchHelper
    helper = SearchHelper(device)
    helper.search("天气预报")
"""

import time
import cv2
import numpy as np

from utils.logger import get_logger

logger = get_logger("search_helper")


class SearchHelper:
    """微信全局搜索器。"""

    # 搜索图标候选位置（紧挨"+"按钮右侧，与朋友圈相机位置相近）
    SEARCH_CANDIDATES = [
        (0.831, 0.054),   # (1050, 150) — 主位置
        (0.820, 0.054),   # (1036, 150)
        (0.845, 0.054),   # (1068, 150)
        (0.855, 0.052),   # (1080, 145)
    ]

    def __init__(self, d, account_id: str = ""):
        self.d = d
        self.account_id = account_id
        self.w, self.h = d.info['displayWidth'], d.info['displayHeight']

    # ================================================================
    # 公共接口
    # ================================================================

    def open_search(self) -> bool:
        """
        打开微信全局搜索页面。

        Returns:
            是否成功打开搜索页
        """
        logger.info(f"[{self.account_id}] 打开搜索页")

        try:
            self._goto_wechat_home()
            self._click_search_icon()
            logger.info(f"[{self.account_id}] 搜索页已打开")
            return True
        except Exception as e:
            logger.error(f"[{self.account_id}] 打开搜索页失败: {e}")
            return False

    def search(self, keyword: str) -> bool:
        """
        打开搜索页并搜索关键词。

        Args:
            keyword: 搜索关键词

        Returns:
            是否成功
        """
        logger.info(f"[{self.account_id}] 搜索: '{keyword}'")

        if not self.open_search():
            return False

        try:
            self._input_keyword(keyword)
            self._press_search()
            logger.info(f"[{self.account_id}] 搜索完成: '{keyword}'")
            return True
        except Exception as e:
            logger.error(f"[{self.account_id}] 搜索失败: {e}")
            return False

    # ================================================================
    # 导航
    # ================================================================

    def _goto_wechat_home(self):
        """冷启动微信 → 微信 Tab。"""
        logger.debug(f"[{self.account_id}] 导航到微信首页")
        d, w, h = self.d, self.w, self.h

        d.screen_on()
        time.sleep(0.3)
        d.swipe(w // 2, int(h * 0.85), w // 2, int(h * 0.2), duration=0.3)
        time.sleep(0.5)
        d.app_stop("com.tencent.mm")
        time.sleep(1)
        d.app_start("com.tencent.mm")
        time.sleep(5)

        d.click(int(w * 0.125), int(h * 0.955))  # 微信 Tab
        time.sleep(2)

    # ================================================================
    # 点击搜索图标
    # ================================================================

    def _click_search_icon(self):
        """多位置重试点击搜索图标，用页面差异验证。"""
        logger.debug(f"[{self.account_id}] 点击搜索图标")
        d, w, h = self.d, self.w, self.h

        img_before = np.array(d.screenshot(format="pillow"))
        gray_before = cv2.cvtColor(img_before, cv2.COLOR_RGB2GRAY)

        for rx, ry in self.SEARCH_CANDIDATES:
            cx, cy = int(w * rx), int(h * ry)
            d.click(cx, cy)
            time.sleep(2)

            img_after = np.array(d.screenshot(format="pillow"))
            gray_after = cv2.cvtColor(img_after, cv2.COLOR_RGB2GRAY)
            diff = np.mean(cv2.absdiff(
                gray_after.astype(np.int16), gray_before.astype(np.int16)))

            if diff > 10:
                logger.debug(f"[{self.account_id}] 搜索页打开 ({cx},{cy}) diff={diff:.0f}")
                return

            d.press("back")
            time.sleep(0.5)

        raise RuntimeError("所有位置均未能打开搜索页")

    # ================================================================
    # 输入关键词 + 搜索
    # ================================================================

    def _input_keyword(self, keyword: str):
        """ADBKeyboard IME 注入搜索关键词。"""
        logger.debug(f"[{self.account_id}] 输入关键词: '{keyword}'")
        d, w, h = self.d, self.w, self.h

        # 点击搜索输入框（搜索页顶部居中）
        d.click(int(w * 0.50), int(h * 0.045))
        time.sleep(0.8)

        # IME 注入
        try:
            d.set_input_ime(True)
            time.sleep(0.3)
            d.send_keys(keyword)
            time.sleep(0.8)
            d.set_input_ime(False)
        except Exception as e:
            logger.warning(f"[{self.account_id}] IME失败: {e}，尝试shell")
            try:
                d.shell(f"input text {keyword}")
            except Exception:
                pass

    def _press_search(self):
        """按 Enter 键触发搜索。"""
        time.sleep(0.3)
        try:
            self.d.press("enter")
            time.sleep(2)
        except Exception:
            pass
