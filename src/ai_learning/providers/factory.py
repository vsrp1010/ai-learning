from ai_learning.config import load_settings

from .base import LLMProvider
from .gemini import GeminiProvider
from .groq import GroqProvider
from .local import LocalProvider


def create_provider() -> LLMProvider:
    settings = load_settings()

    if settings.llm_provider == "groq":
        return GroqProvider(
            model=settings.llm_model,
            api_key=settings.groq_api_key,
        )

    if settings.llm_provider == "gemini":
        return GeminiProvider(
            model=settings.llm_model,
            api_key=settings.gemini_api_key,
        )

    if settings.llm_provider == "local":
        return LocalProvider(
            model=settings.llm_model,
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER: {settings.llm_provider}"
    )