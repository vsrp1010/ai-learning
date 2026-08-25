import os
from typing import Any

from openai import OpenAI

from .base import LLMProvider


class GeminiProvider(LLMProvider):

    def __init__(self, model: str):
        self.client = OpenAI(
            api_key=os.environ["GEMINI_API_KEY"],
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
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