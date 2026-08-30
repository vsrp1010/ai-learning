FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --locked --no-install-project

COPY src ./src

RUN uv sync --locked

EXPOSE 8080

CMD ["uv", "run", "--no-sync", "uvicorn", "ai_learning.api:app", "--host", "0.0.0.0", "--port", "8080"]