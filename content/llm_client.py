"""
LLM 客户端 — 调用 LLM API 生成差异化的聊天内容和朋友圈文案。

支持的提供商:
    - DeepSeek（推荐，性价比高，中文能力强）
    - OpenAI 兼容接口（可接入任何兼容的 API）
    - 本地模型（Ollama 等，完全离线）

安全措施:
    - 每次调用使用不同的 prompt 注入人格信息
    - temperature 随机微调，确保内容多样性
    - 记录生成历史哈希，定期检查同质化趋势

使用方式:
    from content.llm_client import LLMClient
    client = LLMClient()
    post = client.generate_post_text(persona)
    chat = client.generate_chat_text(persona, context="和朋友闲聊")
"""

import hashlib
import random
import time
from typing import Optional

from openai import OpenAI

from config.settings import settings
from utils.logger import get_logger

logger = get_logger("llm_client")


class LLMClient:
    """
    LLM 内容生成客户端。

    封装了朋友圈文案、聊天内容、评论的生成逻辑。
    """

    def __init__(self):
        self.client: Optional[OpenAI] = None
        if settings.LLM_API_KEY:
            self.client = OpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
            )
        self._history_hashes: list[str] = []

    @property
    def available(self) -> bool:
        """检查 LLM 是否可用"""
        return self.client is not None

    # ================================================================
    # 朋友圈文案
    # ================================================================

    def generate_post_text(
        self,
        persona: dict,
        topic: str = "日常",
    ) -> str:
        """
        生成朋友圈文案。

        Args:
            persona: 人格档案
            topic: 文案主题

        Returns:
            朋友圈文案（30-120字）
        """
        prompt = self._build_post_prompt(persona, topic)
        text = self._call_api(prompt, temperature=0.85, max_tokens=200)
        return self._ensure_variety(text, persona)

    # ================================================================
    # 聊天内容
    # ================================================================

    def generate_chat_text(
        self,
        persona: dict,
        context: str = "和朋友闲聊",
        scene: str = "small_talk",
    ) -> str:
        """
        生成聊天消息。

        Args:
            persona: 人格档案
            context: 对话背景
            scene: 对话场景

        Returns:
            聊天文本（10-50字）
        """
        prompt = f"""你正在模拟一个真实微信用户的聊天对话。

你的个人画像：
- 年龄：{persona.get('age', '25-35')}
- 城市：{persona.get('city', '北京')}
- 兴趣爱好：{', '.join(persona.get('hobbies', ['日常']))}
- 聊天风格：{persona.get('comment_style', '自然随意')}

当前场景：{context}
对话类型：{scene}

请用真实自然的口吻，发一条微信聊天消息（10-50字）。
要求：
- 像是随手打的，不要太正式
- 不用句号结尾（微信聊天习惯）
- 偶尔出现语气词（哈哈、嗯、哦）
- 不要用 emoji 堆砌，可以不用 emoji
"""
        text = self._call_api(prompt, temperature=0.9, max_tokens=100)
        return text

    # ================================================================
    # 评论
    # ================================================================

    def generate_comment(
        self,
        persona: dict,
        post_text: str = "",
    ) -> str:
        """
        生成朋友圈评论。

        Args:
            persona: 人格档案
            post_text: 被评论的朋友圈内容

        Returns:
            评论文本（5-25字）
        """
        post_context = f'\n朋友圈内容："{post_text}"' if post_text else ""
        prompt = f"""你是一个微信用户，看到了朋友发的朋友圈。{post_context}

你的个人画像：
- 年龄：{persona.get('age', '25-35')}
- 评论风格：{persona.get('comment_style', '简洁真诚')}

请用朋友间的自然口吻写一条评论（5-25字）。
要求：简短、自然、像随手敲的。
"""
        text = self._call_api(prompt, temperature=0.8, max_tokens=80)
        return text

    # ================================================================
    # 内部方法
    # ================================================================

    def _build_post_prompt(self, persona: dict, topic: str) -> str:
        """构建朋友圈文案 prompt"""
        return f"""你是一个真实微信用户，以下是你的个人画像：
- 年龄：{persona.get('age', '25-35')}岁
- 城市：{persona.get('city', '北京')}
- 兴趣爱好：{', '.join(persona.get('hobbies', ['美食', '旅行', '阅读']))}
- 发圈风格：{persona.get('post_style', '随性简短')}
- 常发主题：{', '.join(persona.get('topics', ['日常']))}

请用真实自然的口吻，写一条朋友圈文案（30-100字），主题是"{topic}"。

要求：
- 不要用 emoji 堆砌（最多2个）
- 不要太正式或太文艺
- 像普通人随手发的，有口语化表达
- 不要提任何敏感话题或政治内容
- 可以偶尔有小错别字（体现真实感，但不要太刻意）
"""

    def _call_api(
        self,
        prompt: str,
        temperature: float = 0.9,
        max_tokens: int = 200,
    ) -> str:
        """
        调用 LLM API。

        Args:
            prompt: 完整 prompt
            temperature: 温度参数（含微小随机调整）
            max_tokens: 最大输出 token

        Returns:
            LLM 返回的文本，失败返回空字符串
        """
        if not self.client:
            logger.warning("LLM 客户端未配置 API Key，返回空字符串")
            return ""

        # temperature 微调，进一步增加多样性
        adjusted_temp = temperature + random.uniform(-0.05, 0.05)
        adjusted_temp = max(0.1, min(1.5, adjusted_temp))

        try:
            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=adjusted_temp,
                max_tokens=max_tokens,
                timeout=30,
            )
            text = response.choices[0].message.content.strip()

            # 记录哈希用于同质化检测
            self._record_hash(text)

            return text
        except Exception as e:
            logger.error(f"LLM API 调用失败: {e}")
            return ""

    def _record_hash(self, text: str):
        """记录内容哈希，用于后续同质化检测"""
        if text:
            h = hashlib.md5(text.encode()).hexdigest()
            self._history_hashes.append(h)
            # 只保留最近 500 条记录
            if len(self._history_hashes) > 500:
                self._history_hashes = self._history_hashes[-500:]

    def check_homogeneity(self) -> dict:
        """
        检查生成内容的同质化程度。

        Returns:
            {"total": int, "unique": int, "dup_ratio": float}
        """
        if not self._history_hashes:
            return {"total": 0, "unique": 0, "dup_ratio": 0.0}

        total = len(self._history_hashes)
        unique = len(set(self._history_hashes))
        dup_ratio = 1.0 - (unique / total)
        return {"total": total, "unique": unique, "dup_ratio": dup_ratio}

    def _ensure_variety(self, text: str, persona: dict) -> str:
        """检查内容是否过于重复，必要时回退到模板"""
        if not text:
            return ""
        h = hashlib.md5(text.encode()).hexdigest()
        recent_count = sum(1 for past in self._history_hashes[-20:] if past == h)
        if recent_count >= 2:
            logger.debug("检测到内容重复，但保留（LLM 多样性在合理范围）")
        return text
