import asyncio
import json
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from dataclasses import dataclass
from contextlib import AsyncExitStack, asynccontextmanager

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
            print("\nFINAL ANSWER:")
            print(assistant_message.content)

            return assistant_message.content

        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            state.executed_tools.append(function_name)

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

    return None


@dataclass
class ToolRoute:
    connection: "MCPConnection"
    tool_name: str

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

        tool_registry[tool_name] = ToolRoute(
            connection=connection,
            tool_name=tool.name,
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
    ):
        self.model_client = model_client
        self.llm_tools = llm_tools
        self.tool_registry = tool_registry
        self.state = AgentState()

        self.max_iterations = max_iterations
        self.tool_timeout = tool_timeout
        self.tool_max_retries = tool_max_retries

    async def run(self, user_message):
        return await run_agent(
            model_client=self.model_client,
            state=self.state,
            llm_tools=self.llm_tools,
            tool_registry=self.tool_registry,
            user_message=user_message,
            max_iterations=self.max_iterations,
            tool_timeout=self.tool_timeout,
            tool_max_retries=self.tool_max_retries,
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
                    f"{route.connection.name.upper()}:{route.tool_name}"
                )

            provider = create_provider()
            model_client = ModelClient(provider=provider)

            runtime = AgentRuntime(
                model_client=model_client,
                llm_tools=llm_tools,
                tool_registry=tool_registry,
                max_iterations=settings.agent_max_iterations,
                tool_timeout=settings.tool_timeout,
                tool_max_retries=settings.tool_max_retries,
            )

            await runtime.run(
                # "Diagnose pod checkout-abc123 and summarize the result."
                #"Check the current weather in San Jose. Then check the status of the Kubernetes pod named \"my-app-pod\" and diagnose it if it is unhealthy. Give me a concise operational summary, including the weather, pod health, and any recommended action."
                # "Investigate the payments deployment. Identify any unhealthy pods, diagnose the problem, and give me a concise summary of the likely issue and recommended next steps. Do not restart anything unless I explicitly ask you to."
                "Investigate the payments deployment. Identify any unhealthy pods, diagnose the problem, and use the pod logs to determine the likely root cause. Give me a concise summary of the evidence and recommended next steps. Do not restart anything unless I explicitly ask you to."
            )

    except Exception as exc:
        logger.error("Agent startup failed: %s", exc)
        print(f"\nAGENT STARTUP FAILED: {exc}")

if __name__ == "__main__":
    asyncio.run(main())