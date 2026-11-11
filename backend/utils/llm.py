"""
Domestic LLM Integration Utility (DashScope Qwen-Max / DeepSeek-V3)
Uses OpenAI-compatible client interface for universal compatibility and speed.
"""

import os
import logging
from typing import Optional, List, Dict, Any
from config import settings

logger = logging.getLogger("rgm_llm")

class LLMClient:
    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY
        self.base_url = settings.OPENAI_API_BASE
        self.model = settings.LLM_MODEL
        self._client = None

    def _get_client(self):
        if not self._client and self.api_key:
            try:
                from openai import OpenAI
                extra_headers = {}
                if settings.DASHSCOPE_WORKSPACE_ID:
                    extra_headers["X-DashScope-WorkSpace"] = settings.DASHSCOPE_WORKSPACE_ID

                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    default_headers=extra_headers if extra_headers else None
                )
            except Exception as e:
                logger.error(f"[llm] Failed to initialize OpenAI/DashScope client: {e}")
        return self._client

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        model: Optional[str] = None,
        enable_search: bool = False,
    ) -> str:
        """Calls DashScope / OpenAI compatible LLM endpoint, optionally with live web search grounding."""
        client = self._get_client()
        if not client:
            logger.warning("[llm] LLM client not configured (no API key). Returning fallback response.")
            return "【Canova教练提示】分析服务未配置 API Key，请在后端环境变量中设置 DASHSCOPE_API_KEY。"

        target_model = model or self.model
        try:
            kwargs: Dict[str, Any] = {
                "model": target_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if enable_search:
                kwargs["extra_body"] = {
                    "enable_search": True,
                    "search_options": {
                        "forced_search": True,
                        "search_strategy": "pro",
                    },
                }
            try:
                response = client.chat.completions.create(**kwargs)
            except Exception as search_err:
                if enable_search:
                    logger.warning(f"[llm] Search-enabled call failed ({search_err}), retrying with basic forced_search...")
                    try:
                        kwargs["extra_body"] = {
                            "enable_search": True,
                            "search_options": {"forced_search": True},
                        }
                        response = client.chat.completions.create(**kwargs)
                    except Exception:
                        kwargs.pop("extra_body", None)
                        response = client.chat.completions.create(**kwargs)
                else:
                    raise search_err
            content = response.choices[0].message.content
            return content or ""
        except Exception as e:
            logger.error(f"[llm] Chat completion failed on model {target_model}: {e}")
            return f"AI 分析生成失败：{str(e)}"

llm_client = LLMClient()
