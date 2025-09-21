from langchain_openai import ChatOpenAI

class ChatLLMFactory:
    """统一封装国产大模型 (Qwen, Kimi, Zhipu)，兼容OpenAI格式"""

    PROVIDERS = {
        "qwen": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key_env": "DASHSCOPE_API_KEY",
        },
        "kimi": {
            "base_url": "https://api.moonshot.cn/v1",
            "api_key_env": "KIMI_API_KEY",
        },
        "zhipu": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4/",
            "api_key_env": "ZHIPU_API_KEY",
        },
    }

    @classmethod
    def create(cls, provider: str, model: str | None = None, temperature: float = 0.7, streaming: bool = False, callbacks=None):
        """创建一个 ChatOpenAI 模型"""
        if provider not in cls.PROVIDERS:
            raise ValueError(f"未知 provider: {provider}, 可选: {list(cls.PROVIDERS.keys())}")

        conf = cls.PROVIDERS[provider]

        # 从环境变量获取 API_KEY
        import os
        api_key = os.getenv(conf["api_key_env"])
        if not api_key:
            raise ValueError(f"请先设置环境变量 {conf['api_key_env']}")

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=conf["base_url"],
            temperature=temperature,
            streaming=streaming,
            callbacks=callbacks or [],
        )
    
