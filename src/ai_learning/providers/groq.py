from typing import Any

from openai import OpenAI

from .base import LLMProvider


class GroqProvider(LLMProvider):

    def __init__(self, model: str, api_key: str | None):
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is required when using the Groq provider"
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        self.model = model

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ):
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
        )