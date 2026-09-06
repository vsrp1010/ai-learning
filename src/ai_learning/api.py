from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from pydantic import BaseModel

from ai_learning.config import load_settings
from ai_learning.multi_mcp_agent import (
    AgentRuntime,
    ModelClient,
    connect_mcp_servers,
    register_mcp_tools,
)
from ai_learning.providers.factory import create_provider


class ChatRequest(BaseModel):
    message: str
    approval_granted: bool = False

class ChatResponse(BaseModel):
    answer: str | None
    iterations: int
    tools_used: list[str]
    blocked_tools: list[str]
    error: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()

    mcp_servers = {
        "weather": settings.weather_mcp_url,
        "kubernetes": settings.kubernetes_mcp_url,
    }

    async with connect_mcp_servers(mcp_servers) as connections:
        tool_registry = {}
        llm_tools = []

        for server_name, connection in connections.items():
            register_mcp_tools(
                server_name,
                connection["url"],
                connection["tools"],
                tool_registry,
                llm_tools,
            )

        provider = create_provider()

        model_client = ModelClient(
            provider=provider,
        )

        runtime = AgentRuntime(
            model_client=model_client,
            llm_tools=llm_tools,
            tool_registry=tool_registry,
            max_iterations=settings.agent_max_iterations,
            tool_timeout=settings.tool_timeout,
            tool_max_retries=settings.tool_max_retries,
        )

        app.state.runtime = runtime

        yield


app = FastAPI(
    title="Kubernetes Troubleshooting Agent",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
    }


@app.get("/ready")
async def ready(request: Request):
    if not hasattr(request.app.state, "runtime"):
        return {
            "status": "not_ready",
        }

    return {
        "status": "ready",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    runtime: AgentRuntime = request.app.state.runtime

    result = await runtime.run(
        body.message,
        approval_granted=body.approval_granted,
    )

    return ChatResponse(**result)
