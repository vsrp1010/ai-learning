import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_model: str
    groq_api_key: str | None
    gemini_api_key: str | None


def load_settings() -> Settings:
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    model = os.environ.get("LLM_MODEL")

    if not model:
        raise ValueError(
            "LLM_MODEL environment variable is required"
        )

    return Settings(
        llm_provider=provider,
        llm_model=model,
        groq_api_key=os.environ.get("GROQ_API_KEY"),
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
    )