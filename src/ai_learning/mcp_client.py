import asyncio
from unittest import result
import os
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

llm = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)

server_params = StdioServerParameters(
    command="uv",
    args=[
        "run",
        "python",
        # "src/ai_learning/weather_server.py",
        "src/ai_learning/k8s_mcp_server.py",
    ],
)

def mcp_tool_to_openai_tool(tool):
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }

async def main():
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:

            await session.initialize()

            tools = await session.list_tools()

            llm_tools = [
                mcp_tool_to_openai_tool(tool)
                for tool in tools.tools
            ]

            print("\nTOOLS FOR LLM:")
            print(llm_tools)

            print("TOOLS EXPOSED BY MCP SERVER:")
            # for tool in tools.tools:
            #     print(f"- {tool.name}: {tool.description}")
            for tool in tools.tools:
                print(tool.model_dump())

            result = await session.call_tool(
                "get_pod_status",
                {"pod_name": "checkout-abc123"},
            )

            print("TOOL RESULT:")
            print(result)

            resources = await session.list_resources()

            print("\nRESOURCES EXPOSED BY MCP SERVER:")

            for resource in resources.resources:
                print(resource.model_dump())

            result = await session.read_resource("k8s://deployments")

            print("\nRESOURCE RESULT:")
            print(result)

            result = await session.read_resource("k8s://cluster-config")

            print("\nCLUSTER CONFIG:")
            print(result)

            result = await session.call_tool(
                "restart_deployment",
                {"deployment_name": "checkout"},
            )

            print("\nRESTART DEPLOYMENT RESULT:")
            print(result)

            result = await session.call_tool(
                "get_pod_status",
                {"pod_name": "checkout-abc123"},
            )

            print("\nPOD STATUS AFTER RESTART:")
            print(result)

            result = await session.call_tool(
                "diagnose_pod",
                {"pod_name": "payments-xyz456"},
            )

            print("\nPOD DIAGNOSIS:")
            print(result)

            result = await session.call_tool(
                "diagnose_pod",
                {"pod_name": "checkout-abc123"},
            )

            print("\nHEALTHY POD DIAGNOSIS:")
            print(result)

            prompts = await session.list_prompts()

            print("\nPROMPTS EXPOSED BY MCP SERVER:")

            for prompt in prompts.prompts:
                print(prompt.model_dump())

            result = await session.get_prompt(
                "deployment_manifest",
                {
                    "application": "checkout",
                    "image": "checkout:v1.4.2",
                    "replicas": "3",
                },
            )

            print("\nDEPLOYMENT MANIFEST PROMPT:")
            print(result)

            messages = [
                {
                    "role": "user",
                    "content": "What's the weather like in San Francisco?",
                }
            ]

            response = llm.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=messages,
                tools=llm_tools,
            )

            assistant_message = response.choices[0].message
            if assistant_message.tool_calls:
                messages.append(assistant_message)

                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)

                    print("\nLLM REQUESTED MCP TOOL:")
                    print(function_name, arguments)

                    result = await session.call_tool(
                        function_name,
                        arguments,
                    )

                    print("\nMCP TOOL RESULT:")
                    print(result)

                    tool_content = result.structured_content

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_content),
                        }
                    )

                final_response = llm.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=messages,
                    tools=llm_tools,
                )

                print("\nFINAL ANSWER:")
                print(final_response.choices[0].message.content)
            

if __name__ == "__main__":
    asyncio.run(main())