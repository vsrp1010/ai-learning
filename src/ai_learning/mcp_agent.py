import asyncio
import os
import json

from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client


# server_params = StdioServerParameters(
#     command="uv",
#     args=[
#         "run",
#         "python",
#         "src/ai_learning/weather_server.py",
#     ],
# )

# server_params = StdioServerParameters(
#     command="uv",
#     args=["run", "python", "src/ai_learning/weather_server.py"],
# )

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
    llm = OpenAI(
        api_key=os.environ["GROQ_API_KEY"],
        base_url="https://api.groq.com/openai/v1",
    )
    # async with stdio_client(server_params) as (read_stream, write_stream):
    #     async with ClientSession(read_stream, write_stream) as session:
    async with streamable_http_client(
        "http://127.0.0.1:8000/mcp"
    ) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()

            llm_tools = [
                mcp_tool_to_openai_tool(tool)
                for tool in tools.tools
            ]

            print("AVAILABLE TOOLS:")
            for tool in llm_tools:
                print(tool)

            resources_result = await session.list_resources()

            print("\nAVAILABLE RESOURCES:")
            for resource in resources_result.resources:
                print(resource)

            resource_result = await session.read_resource(
                "weather://supported-cities"
            )

            print("\nRESOURCE CONTENT:")
            print(resource_result)

            prompts_result = await session.list_prompts()

            print("\nAVAILABLE PROMPTS:")
            for prompt in prompts_result.prompts:
                print(prompt)

            prompt_result = await session.get_prompt(
                "weather_summary",
                {"city": "Atlantis"},
            )

            print("\nPROMPT RESULT:")
            print(prompt_result)

            messages = [
                {
                    "role": "user",
                    "content": "Get both the weather and local time for Atlantis. They are independent pieces of information, so retrieve both.",
                }
            ]

            MAX_ITERATIONS = 10

            for iteration in range(MAX_ITERATIONS):
                print(f"\n--- AGENT ITERATION {iteration + 1} ---")

                response = llm.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=messages,
                    tools=llm_tools,
                )

                assistant_message = response.choices[0].message

                print("LLM RESPONSE:")
                print(assistant_message)

                # The assistant's response must be preserved
                # because it may contain tool calls.
                messages.append(assistant_message)

                # No tool calls means the LLM considers the task finished.
                if not assistant_message.tool_calls:
                    print("\nFINAL ANSWER:")
                    print(assistant_message.content)
                    break

                # Execute every tool requested by the LLM.
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)

                    print("\nLLM REQUESTED TOOL:")
                    print(function_name, arguments)

                    result = await session.call_tool(
                        function_name,
                        arguments,
                    )

                    print("\nMCP RESULT:")
                    print(result)

                    # Send the MCP result back into the conversation.
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result.structured_content),
                        }
                    )

            else:
                print("\nAGENT STOPPED:")
                print(f"Reached maximum of {MAX_ITERATIONS} iterations.")

            # response = llm.chat.completions.create(
            #     model="openai/gpt-oss-20b",
            #     messages=messages,
            #     tools=llm_tools,
            # )

            # assistant_message = response.choices[0].message

            # if assistant_message.tool_calls:
            #     for tool_call in assistant_message.tool_calls:
            #         function_name = tool_call.function.name
            #         arguments = json.loads(tool_call.function.arguments)

            #         print("\nLLM REQUESTED TOOL:")
            #         print(function_name, arguments)

            #         result = await session.call_tool(
            #             function_name,
            #             arguments,
            #         )

            #         print("\nMCP RESULT:")
            #         print(result)

            # print("\nLLM RESPONSE:")
            # print(assistant_message)


if __name__ == "__main__":
    asyncio.run(main())