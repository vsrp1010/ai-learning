import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)

response = client.responses.create(
    model="openai/gpt-oss-20b",
    input="Explain what an LLM is in exactly three sentences.",
)

# print(response.output_text)
print(response)
