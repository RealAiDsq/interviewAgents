from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from langchain_openai import ChatOpenAI


class ChatLLMFactory:
    """统一封装国产大模型 (Qwen, Kimi, Zhipu)，兼容 OpenAI 接口"""

    DEFAULT_PROVIDER = "zhipu"

    PROVIDERS: Dict[str, Dict[str, Any]] = {
        # "qwen": {
        #     "label": "通义千问",
        #     "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        #     "api_key_env": "DASHSCOPE_API_KEY",
        #     "default_model": "qwen2.5-7b-instruct",
        #     "models": [
        #         {"id": "qwen2.5-7b-instruct", "label": "Qwen2.5 7B Instruct", "context_window": "16K"},
        #         {"id": "qwen2.5-14b-instruct", "label": "Qwen2.5 14B Instruct", "context_window": "32K"},
        #         {"id": "qwen-max", "label": "Qwen-Max", "context_window": "200K"},
        #     ],
        #     "models_endpoint": None,
        # },
        # "kimi": {
        #     "label": "Moonshot Kimi",
        #     "base_url": "https://api.moonshot.cn/v1",
        #     "api_key_env": "KIMI_API_KEY",
        #     "default_model": "moonshot-v1-32k",
        #     "models": [
        #         {"id": "moonshot-v1-8k", "label": "Kimi 8K", "context_window": "8K"},
        #         {"id": "moonshot-v1-32k", "label": "Kimi 32K", "context_window": "32K"},
        #         {"id": "moonshot-v1-128k", "label": "Kimi 128K", "context_window": "128K"},
        #     ],
        #     "models_endpoint": None,
        # },
        # "zhipu": {
        #     "label": "智谱 GLM",
        #     "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        #     "api_key_env": "ZHIPU_API_KEY",
        #     "default_model": "GLM-4-Flash",
        #     "models": [
        #         {"id": "GLM-4-Flash", "label": "GLM-4-Flash (高效)"},
        #         {"id": "GLM-4-Air", "label": "GLM-4-Air"},
        #         {"id": "GLM-3-Turbo", "label": "GLM-3-Turbo"},
        #     ],
        #     "models_endpoint": None,
        # },
        "siliconflow": {
            "label": "SiliconFlow",
            "base_url": "https://api.siliconflow.cn/v1",
            "api_key_env": "SILICONFLOW_API_KEY",
            "default_model": None,
            "models": [],
            "models_endpoint": "/models",
        },
    }

    MODEL_CACHE_TTL = 300  # seconds
    _model_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}

    @classmethod
    def get_default_provider(cls) -> str:
        return cls.DEFAULT_PROVIDER if cls.DEFAULT_PROVIDER in cls.PROVIDERS else next(iter(cls.PROVIDERS.keys()))

    @classmethod
    def get_default_model(cls, provider: str) -> Optional[str]:
        conf = cls.PROVIDERS.get(provider)
        if not conf:
            return None
        if conf.get("default_model"):
            return conf["default_model"]
        models = conf.get("models") or []
        if models:
            return models[0]["id"]
        return None

    @classmethod
    def get_catalog(cls) -> List[Dict[str, Any]]:
        catalog = []
        for provider, conf in cls.PROVIDERS.items():
            catalog.append({
                "provider": provider,
                "label": conf.get("label", provider),
                "default_model": cls.get_default_model(provider),
                "models": conf.get("models", []),
            })
        return catalog

    @classmethod
    def ensure_provider_ready(cls, provider: str) -> Dict[str, Any]:
        if provider not in cls.PROVIDERS:
            raise ValueError(f"未知 provider: {provider}, 可选: {list(cls.PROVIDERS.keys())}")

        conf = cls.PROVIDERS[provider]

        api_key = os.getenv(conf["api_key_env"])
        if not api_key:
            raise ValueError(f"请先设置环境变量 {conf['api_key_env']}")

        return {**conf, "api_key": api_key}

    @classmethod
    async def fetch_provider_models(cls, provider: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
        conf = cls.ensure_provider_ready(provider)
        now = time.time()
        cached = cls._get_cached_models(provider, now, force_refresh)
        if cached is not None:
            return cached

        endpoint = conf.get("models_endpoint")
        if not endpoint:
            models = conf.get("models", [])
            cls._store_models_cache(provider, now, models)
            return models

        models = await cls._request_remote_models(conf, endpoint)
        if not models:
            models = conf.get("models", [])

        cls._store_models_cache(provider, now, models)
        return models

    @classmethod
    def _get_cached_models(cls, provider: str, now: float, force_refresh: bool) -> Optional[List[Dict[str, Any]]]:
        if force_refresh:
            return None
        cached = cls._model_cache.get(provider)
        if cached and now - cached[0] < cls.MODEL_CACHE_TTL:
            return cached[1]
        return None

    @classmethod
    def _store_models_cache(cls, provider: str, timestamp: float, models: List[Dict[str, Any]]) -> None:
        cls._model_cache[provider] = (timestamp, models)

    @classmethod
    async def _request_remote_models(cls, conf: Dict[str, Any], endpoint: str) -> List[Dict[str, Any]]:
        url = cls._build_request_url(conf["base_url"], endpoint)
        headers = {
            "Authorization": f"Bearer {conf['api_key']}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                payload = resp.json()
        except Exception:
            return []

        return cls._parse_model_payload(payload)

    @staticmethod
    def _build_request_url(base_url: str, endpoint: str) -> str:
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    @classmethod
    def _parse_model_payload(cls, payload: Any) -> List[Dict[str, Any]]:
        items: List[Any] = []
        if isinstance(payload, dict):
            if isinstance(payload.get("data"), list):
                items = payload["data"]
            elif isinstance(payload.get("models"), list):
                items = payload["models"]
        elif isinstance(payload, list):
            items = payload

        models: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            mid = item.get("id") or item.get("name")
            if not mid:
                continue
            label = item.get("label") or item.get("display_name") or item.get("name") or mid
            context = item.get("context_window") or item.get("context_length") or item.get("max_context_length")
            models.append({
                "id": mid,
                "label": label,
                "context_window": context,
            })
        return models

    @classmethod
    async def resolve_model(
        cls,
        provider: str,
        model: Optional[str] = None,
        *,
        force_refresh: bool = False,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Resolve a valid model id for provider, returning the id and candidate list."""

        cls.ensure_provider_ready(provider)
        models = await cls.fetch_provider_models(provider, force_refresh=force_refresh)
        valid_ids = {m.get("id") for m in models if m.get("id")}

        if model:
            if valid_ids and model not in valid_ids:
                raise ValueError(f"模型 {model} 不存在或不可用，请重新选择")
            return model, models

        fallback = cls.get_default_model(provider)
        if fallback and fallback in valid_ids:
            return fallback, models

        if valid_ids:
            return next(iter(valid_ids)), models

        if fallback:
            return fallback, models

        raise ValueError(f"Provider {provider} 未配置可用模型，请先在后台补充模型信息")

    @classmethod
    def create(
        cls,
        provider: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        streaming: bool = False,
        callbacks: Optional[List[Any]] = None,
    ) -> ChatOpenAI:
        """创建一个 ChatOpenAI 模型"""
        conf = cls.ensure_provider_ready(provider)
        api_key = conf["api_key"]

        resolved_model = model or cls.get_default_model(provider)
        if not resolved_model:
            raise ValueError(f"Provider {provider} 未配置默认模型，请显式指定 model 参数")

        return ChatOpenAI(
            model=resolved_model,
            api_key=api_key,
            base_url=conf["base_url"],
            temperature=temperature,
            streaming=streaming,
            callbacks=callbacks or [],
        )

