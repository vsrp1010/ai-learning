import os

from .base import LLMProvider
from .gemini import GeminiProvider
from .groq import GroqProvider


def create_provider() -> LLMProvider:
    provider_name = os.environ.get("LLM_PROVIDER", "groq").lower()
    model = os.environ.get("LLM_MODEL")

    if not model:
        raise ValueError(
            "LLM_MODEL environment variable is required"
        )

    if provider_name == "groq":
        return GroqProvider(model=model)

    if provider_name == "gemini":
        return GeminiProvider(model=model)

    raise ValueError(
        f"Unsupported LLM_PROVIDER: {provider_name}"
    )