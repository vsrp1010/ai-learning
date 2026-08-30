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

    weather_mcp_url: str
    kubernetes_mcp_url: str

    agent_max_iterations: int
    tool_timeout: int
    tool_max_retries: int

    log_level: str


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

        weather_mcp_url=os.environ.get(
            "WEATHER_MCP_URL",
            "http://127.0.0.1:8000/mcp",
        ),
        kubernetes_mcp_url=os.environ.get(
            "KUBERNETES_MCP_URL",
            "http://127.0.0.1:8001/mcp",
        ),

        agent_max_iterations=int(
            os.environ.get("AGENT_MAX_ITERATIONS", "10")
        ),
        tool_timeout=int(
            os.environ.get("TOOL_TIMEOUT", "10")
        ),
        tool_max_retries=int(
            os.environ.get("TOOL_MAX_RETRIES", "2")
        ),

        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    )
