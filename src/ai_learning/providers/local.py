from typing import Any

from openai import OpenAI

from .base import LLMProvider


class LocalProvider(LLMProvider):

    def __init__(self, model: str):
        self.client = OpenAI(
            api_key="ollama",
            base_url="http://localhost:11434/v1",
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