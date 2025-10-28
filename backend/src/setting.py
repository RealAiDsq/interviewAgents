import os

def _int_from_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, value)

MAX_LLM_PARALLEL = _int_from_env("LLM_MAX_PARALLEL", 128)