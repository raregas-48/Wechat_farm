"""
评论模板库 — 用于朋友圈评论的快速生成。

使用方式:
    from content.comment_templates import CommentTemplateManager
    mgr = CommentTemplateManager()
    comment = mgr.get_comment(persona)
"""

import random
from typing import Optional


class CommentTemplateManager:
    """评论模板管理器"""

    TEMPLATES: dict[str, list[str]] = {
        "赞美": [
            "好好看！",
            "这也太好看了吧",
            "👍 不错不错",
            "美！",
            "好看好看",
            "拍得真好",
            "厉害了",
        ],
        "关心": [
            "最近还好吗",
            "注意身体啊",
            "照顾好自己",
            "辛苦了",
        ],
        "调侃": [
            "哈哈，笑死",
            "这是认真的吗 😂",
            "有被内涵到",
            "请说出你的故事",
            "这个表情到位了",
        ],
        "同感": [
            "同感同感",
            "确实如此",
            "我也是这么想的",
            "+1",
            "不能更同意了",
        ],
        "提问": [
            "这是哪里啊？",
            "好吃吗？求地址",
            "怎么做到的？",
            "这是什么？",
        ],
    }

    def get_comment(
        self,
        persona: Optional[dict] = None,
        style: str = None,
    ) -> str:
        """
        生成一条随机评论。

        Args:
            persona: 人格档案
            style: 评论风格（赞美/关心/调侃/同感/提问），None 随机选

        Returns:
            评论文本
        """
        if style is None:
            if persona:
                comment_style = persona.get("comment_style", "")
                if "赞美" in comment_style or "热情" in comment_style:
                    style = "赞美"
                elif "调侃" in comment_style or "搞笑" in comment_style:
                    style = "调侃"
                elif "关心" in comment_style:
                    style = "关心"
                elif "简短" in comment_style:
                    style = "同感"

            if style is None:
                style = random.choice(list(self.TEMPLATES.keys()))

        templates = self.TEMPLATES.get(style, self.TEMPLATES["赞美"])
        return random.choice(templates)
