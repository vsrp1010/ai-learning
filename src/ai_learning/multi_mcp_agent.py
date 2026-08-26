import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from dataclasses import dataclass
from contextlib import AsyncExitStack, asynccontextmanager

from ai_learning.providers.factory import create_provider

MCP_SERVERS = {
    "weather": "http://127.0.0.1:8000/mcp",
    "kubernetes": "http://127.0.0.1:8001/mcp",
}

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

            print(
                f"\nTOOL RETRY "
                f"{attempt + 1}/{max_retries}"
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
        print(f"\n--- AGENT ITERATION {iteration + 1} ---")

        response = model_client.complete(
            messages=state.messages,
            tools=llm_tools,
        )

        assistant_message = response.choices[0].message

        print("\nLLM RESPONSE:")
        print(assistant_message)

        state.messages.append(assistant_message)

        if not assistant_message.tool_calls:
            print("\nFINAL ANSWER:")
            print(assistant_message.content)
            return assistant_message.content

        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            print("\nLLM REQUESTED TOOL:")
            print(function_name, arguments)

            route = tool_registry.get(function_name)

            if route is None:
                error_message = f"Unknown tool: {function_name}"

                print("\nTOOL ERROR:")
                print(error_message)

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
                
                print("\nMCP RESULT:")
                print(result)

                if result.is_error:
                    tool_content = {
                        "error": "MCP tool returned an error",
                        "details": result.structured_content,
                    }
                else:
                    tool_content = result.structured_content

            except asyncio.TimeoutError:
                print("\nTOOL TIMEOUT")

                tool_content = {
                    "error": "Tool execution timed out",
                    "timeout_seconds": 10,
                }

            except Exception as exc:
                print("\nTOOL EXECUTION ERROR:")
                print(exc)

                tool_content = {
                    "error": "Tool execution failed",
                    "details": str(exc),
                }

            except Exception as exc:
                print("\nTOOL EXECUTION ERROR:")
                print(exc)

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

        read_stream, write_stream = await self._exit_stack.enter_async_context(
            streamable_http_client(self.url)
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
            connections[name] = await stack.enter_async_context(
                MCPConnection(name, url)
            )

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
    
    async with connect_mcp_servers(MCP_SERVERS) as connections:

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

        # provider = GroqProvider(
        #     model="openai/gpt-oss-20b",
        # )

        provider = create_provider()

        model_client = ModelClient(
            provider=provider,
        )

        runtime = AgentRuntime(
            model_client=model_client,
            llm_tools=llm_tools,
            tool_registry=tool_registry,
        )

        await runtime.run(
            "Check whether the checkout-abc123 pod is healthy."
        )

        await runtime.run(
            "Now tell me whether the weather in San Francisco "
            "is suitable for going outside."
        )

if __name__ == "__main__":
    asyncio.run(main())