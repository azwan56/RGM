"""
Domestic LLM Integration Utility (DashScope Qwen-Max / DeepSeek-V3)
Uses OpenAI-compatible client interface for universal compatibility and speed.
"""

import os
import base64
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
                import httpx
                from openai import OpenAI
                extra_headers = {}
                if settings.DASHSCOPE_WORKSPACE_ID:
                    extra_headers["X-DashScope-WorkSpace"] = settings.DASHSCOPE_WORKSPACE_ID

                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=httpx.Timeout(45.0, connect=8.0),
                    max_retries=1,
                    default_headers=extra_headers if extra_headers else None,
                )
            except Exception as e:
                logger.error(f"[llm] Failed to initialize OpenAI/DashScope client: {e}")
        return self._client

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        model: Optional[str] = None,
        enable_search: bool = False,
        response_format: Optional[Dict[str, Any]] = None,
        disable_thinking: bool = False,
        raise_on_error: bool = False,
        search_strategy: str = "standard",
    ) -> str:
        """Calls DashScope / OpenAI compatible LLM endpoint, optionally with live web search grounding."""
        client = self._get_client()
        if not client:
            if raise_on_error:
                raise RuntimeError("LLM client not configured (missing API key)")
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
            if response_format is not None:
                kwargs["response_format"] = response_format

            extra_body: Dict[str, Any] = {}
            if disable_thinking:
                extra_body["enable_thinking"] = False
            if enable_search:
                extra_body["enable_search"] = True
                extra_body["search_options"] = {
                    "forced_search": True,
                    "search_strategy": search_strategy or "standard",
                }
            if extra_body:
                kwargs["extra_body"] = extra_body

            try:
                response = client.chat.completions.create(**kwargs)
            except Exception as search_err:
                if enable_search:
                    logger.warning(f"[llm] Search-enabled call failed ({search_err}), retrying with basic forced_search...")
                    fallback_extra: Dict[str, Any] = {
                        "enable_search": True,
                        "search_options": {"forced_search": True},
                    }
                    if disable_thinking:
                        fallback_extra["enable_thinking"] = False
                    kwargs["extra_body"] = fallback_extra
                    response = client.chat.completions.create(**kwargs)
                else:
                    raise search_err

            content = response.choices[0].message.content
            return content or ""
        except Exception as e:
            logger.error(f"[llm] Chat completion failed on model {target_model}: {e}")
            if raise_on_error:
                raise
            return f"AI 分析生成失败：{str(e)}"

    def call_vision_ocr(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        prompt: str = "",
        max_tokens: int = 2200,
    ) -> str:
        """Calls dedicated Qwen3.5-OCR vision model (with bounded resolution & fallback)."""
        if not image_bytes:
            raise ValueError("图片内容为空")
        client = self._get_client()
        if not client:
            raise ValueError("服务端视觉识别配置缺失，请联系管理员")

        b64_str = base64.b64encode(image_bytes).decode("ascii")
        primary_ocr = getattr(settings, "LLM_MODEL_OCR", "qwen3.5-ocr") or "qwen3.5-ocr"
        models_to_try = [primary_ocr]
        if primary_ocr != "qwen-vl-plus":
            models_to_try.append("qwen-vl-plus")

        last_err: Optional[Exception] = None
        for model_name in models_to_try:
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime_type};base64,{b64_str}"},
                                    "min_pixels": 3136,
                                    "max_pixels": 1280 * 1280,
                                },
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                    temperature=0.1,
                    max_tokens=max_tokens,
                    extra_body={"enable_thinking": False},
                )
                content = (resp.choices[0].message.content or "").strip()
                if content:
                    return content
            except Exception as e:
                last_err = e
                logger.warning(f"[llm] Vision OCR failed on {model_name}: {e}")
        raise ValueError(f"图片文字识别失败: {last_err}")

llm_client = LLMClient()
