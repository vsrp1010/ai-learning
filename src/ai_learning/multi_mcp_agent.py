import asyncio
import json
import logging

from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from ai_learning.config import load_settings
from ai_learning.providers.factory import create_provider


logger = logging.getLogger(__name__)


def configure_logging(log_level):
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def mcp_tool_to_openai_tool(tool, server_name):
    return {
        "type": "function",
        "function": {
            "name": f"{server_name}.{tool.name}",
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


class AgentState:
    def __init__(self):
        self.messages = []
        self.executed_tools = []
        self.blocked_tools = []
        self.iterations = 0

    def add_user_message(self, content):
        self.messages.append(
            {
                "role": "user",
                "content": content,
            }
        )


async def call_tool_with_retry(
    route,
    arguments,
    max_retries,
    timeout,
):
    for attempt in range(max_retries + 1):
        try:
            return await asyncio.wait_for(
                route.call(arguments),
                timeout=timeout,
            )
        except Exception:
            if attempt == max_retries:
                raise

            logger.warning(
                "Tool retry attempt=%s/%s",
                attempt + 1,
                max_retries,
            )


async def run_agent(
    model_client,
    state,
    llm_tools,
    tool_registry,
    user_message,
    max_iterations=10,
    tool_timeout=10,
    tool_max_retries=2,
    approval_granted=False,
):
    state.add_user_message(user_message)

    for iteration in range(max_iterations):
        state.iterations = iteration + 1

        logger.info(
            "Agent iteration %s",
            iteration + 1,
        )

        response = model_client.complete(
            messages=state.messages,
            tools=llm_tools,
        )

        assistant_message = response.choices[0].message

        logger.debug(
            "LLM response: %s",
            assistant_message,
        )

        state.messages.append(assistant_message)

        if not assistant_message.tool_calls:
            return {
                "answer": assistant_message.content,
                "iterations": state.iterations,
                "tools_used": state.executed_tools,
                "blocked_tools": state.blocked_tools,
                "error": None,
            }

        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            logger.info(
                "LLM requested tool=%s",
                function_name,
            )

            route = tool_registry.get(function_name)

            if route is None:
                error_message = f"Unknown tool: {function_name}"

                logger.error(
                    "Unknown tool requested: %s",
                    function_name,
                )

                state.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(
                            {
                                "error": error_message,
                            }
                        ),
                    }
                )

                continue

            # Safety boundary:
            # destructive tools must be explicitly approved before
            # the MCP call is allowed to happen.
            if route.destructive and not approval_granted:
                logger.warning(
                    "Blocked destructive tool=%s: approval required",
                    function_name,
                )

                state.blocked_tools.append(function_name)

                tool_content = {
                    "error": "Tool execution blocked",
                    "reason": "Explicit user approval is required",
                    "tool": function_name,
                }

                state.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_content),
                    }
                )

                continue

            # Only record a tool as executed after it has passed
            # the safety gate and immediately before the MCP call.
            state.executed_tools.append(function_name)

            try:
                result = await call_tool_with_retry(
                    route,
                    arguments,
                    max_retries=tool_max_retries,
                    timeout=tool_timeout,
                )

                logger.debug(
                    "MCP result: %s",
                    result,
                )

                if result.is_error:
                    tool_content = {
                        "error": "MCP tool returned an error",
                        "details": result.structured_content,
                    }

                    logger.error(
                        "MCP tool returned an error: tool=%s",
                        function_name,
                    )
                else:
                    tool_content = result.structured_content

            except asyncio.TimeoutError:
                logger.error(
                    "Tool execution timed out: tool=%s timeout_seconds=%s",
                    function_name,
                    tool_timeout,
                )

                tool_content = {
                    "error": "Tool execution timed out",
                    "timeout_seconds": tool_timeout,
                }

            except Exception as exc:
                logger.error(
                    "Tool execution failed: tool=%s error=%s",
                    function_name,
                    exc,
                )

                tool_content = {
                    "error": "Tool execution failed",
                    "details": str(exc),
                }

            state.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_content),
                }
            )

    logger.warning(
        "Agent stopped after reaching maximum iterations=%s",
        max_iterations,
    )

    print("\nAGENT STOPPED:")
    print(f"Reached maximum of {max_iterations} iterations.")

    return {
        "answer": None,
        "iterations": state.iterations,
        "tools_used": state.executed_tools,
        "blocked_tools": state.blocked_tools,
        "error": "Maximum agent iterations reached",
    }


@dataclass
class ToolRoute:
    connection: "MCPConnection"
    tool_name: str
    read_only: bool = True
    destructive: bool = False

    async def call(self, arguments):
        return await self.connection.session.call_tool(
            self.tool_name,
            arguments,
        )


class MCPConnection:
    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.session = None
        self.tools = None
        self._exit_stack = AsyncExitStack()

    async def __aenter__(self):
        await self._exit_stack.__aenter__()

        read_stream, write_stream = (
            await self._exit_stack.enter_async_context(
                streamable_http_client(self.url)
            )
        )

        self.session = await self._exit_stack.enter_async_context(
            ClientSession(
                read_stream,
                write_stream,
            )
        )

        await self.session.initialize()

        self.tools = await self.session.list_tools()

        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return await self._exit_stack.__aexit__(
            exc_type,
            exc_value,
            traceback,
        )


class ModelClient:
    def __init__(self, provider):
        self.provider = provider

    def complete(self, messages, tools):
        return self.provider.chat(
            messages=messages,
            tools=tools,
        )


def register_mcp_tools(connection, tool_registry, llm_tools):
    for tool in connection.tools.tools:
        tool_name = f"{connection.name}.{tool.name}"

        annotations = tool.annotations

        read_only = (
            annotations.read_only_hint
            if annotations is not None
            and annotations.read_only_hint is not None
            else True
        )

        destructive = (
            annotations.destructive_hint
            if annotations is not None
            and annotations.destructive_hint is not None
            else False
        )

        tool_registry[tool_name] = ToolRoute(
            connection=connection,
            tool_name=tool.name,
            read_only=read_only,
            destructive=destructive,
        )

        llm_tools.append(
            mcp_tool_to_openai_tool(
                tool,
                connection.name,
            )
        )


@asynccontextmanager
async def connect_mcp_servers(server_configs):
    async with AsyncExitStack() as stack:
        connections = {}

        for name, url in server_configs.items():
            try:
                connections[name] = await stack.enter_async_context(
                    MCPConnection(name, url)
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Could not connect to MCP server '{name}' at {url}"
                ) from exc

        yield connections


class AgentRuntime:
    def __init__(
        self,
        model_client,
        llm_tools,
        tool_registry,
        max_iterations=10,
        tool_timeout=10,
        tool_max_retries=2,
        approval_granted=False,
    ):
        self.model_client = model_client
        self.llm_tools = llm_tools
        self.tool_registry = tool_registry
        self.state = AgentState()
        self.max_iterations = max_iterations
        self.tool_timeout = tool_timeout
        self.tool_max_retries = tool_max_retries
        self.approval_granted = approval_granted

    async def run(self, user_message):
        state = AgentState()

        return await run_agent(
            model_client=self.model_client,
            state=state,
            llm_tools=self.llm_tools,
            tool_registry=self.tool_registry,
            user_message=user_message,
            max_iterations=self.max_iterations,
            tool_timeout=self.tool_timeout,
            tool_max_retries=self.tool_max_retries,
            approval_granted=self.approval_granted,
        )


async def main():
    settings = load_settings()

    configure_logging(settings.log_level)

    mcp_servers = {
        "weather": settings.weather_mcp_url,
        "kubernetes": settings.kubernetes_mcp_url,
    }

    try:
        async with connect_mcp_servers(mcp_servers) as connections:
            tool_registry = {}
            llm_tools = []

            for connection in connections.values():
                register_mcp_tools(
                    connection,
                    tool_registry,
                    llm_tools,
                )

            print("\nUNIFIED TOOLS FOR LLM:")

            for tool in llm_tools:
                print(f"- {tool['function']['name']}")

            print("\nTOOL ROUTING:")

            for tool_name, route in tool_registry.items():
                print(
                    f"- {tool_name} → "
                    f"{route.connection.name.upper()}:{route.tool_name} "
                    f"(read_only={route.read_only}, "
                    f"destructive={route.destructive})"
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
                approval_granted=False,
            )

            result = await runtime.run(
                "Investigate the payments deployment. "
                "Identify any unhealthy pods, diagnose the problem, "
                "and use the pod logs to determine the likely root cause. "
                "Give me a concise summary of the evidence and "
                "recommended next steps. "
                "Do not restart anything unless I explicitly ask you to."
            )

            print("\nRESULT:")
            print(result)

            print("\nFINAL ANSWER:")
            print(result["answer"])

    except Exception as exc:
        logger.exception("Agent execution failed")
        print(f"\nAGENT EXECUTION FAILED: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
