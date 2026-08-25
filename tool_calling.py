import json
import os

from openai import OpenAI


client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)


# def get_weather(city: str) -> str:
#     """Return the current weather for a city."""
#     # Fake data for learning purposes.
#     weather = {
#         "San Francisco": "Foggy, 62°F",
#         "New York": "Sunny, 78°F",
#         "Bangalore": "Cloudy, 72°F",
#     }

#     return weather.get(city, f"No weather data available for {city}")

def get_weather(city: str) -> str:
    """Return the current weather for a city."""

    if city == "New York":
        raise RuntimeError("Weather service temporarily unavailable")

    weather = {
        "San Francisco": "Foggy, 62°F",
        "New York": "Sunny, 78°F",
        "Bangalore": "Cloudy, 72°F",
    }

    return weather.get(city, f"No weather data available for {city}")

def get_time(city: str) -> str:
    """Return the current local time for a city."""
    # Fake data for learning purposes.
    times = {
        "San Francisco": "10:30 PM",
        "New York": "1:30 AM",
        "Bangalore": "10:00 AM",
    }

    return times.get(city, f"No time data available for {city}")

def execute_tool(function_name: str, arguments: dict) -> str:
    try:
        if function_name == "get_weather":
            return get_weather(**arguments)

        if function_name == "get_time":
            return get_time(**arguments)

        return f"Unknown tool: {function_name}"

    except Exception as e:
        return f"Tool execution failed: {type(e).__name__}: {e}"

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city to get weather for",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current local time for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city to get the local time for",
                    }
                },
                "required": ["city"],
            },
        },
    },
]


messages = [
    {
        "role": "user",
        # "content": "What's the weather and local time in San Francisco?",
        "content": "What's the weather in San Francisco and New York?",
    }
]

MAX_ITERATIONS = 5

for iteration in range(MAX_ITERATIONS):

    print(f"\n--- AGENT ITERATION {iteration + 1} ---")

    # Ask the model what to do next.
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=messages,
        tools=tools,
    )

    assistant_message = response.choices[0].message

    print("MODEL RESPONSE:")
    print(assistant_message)
    print()

    # The model has finished.
    if not assistant_message.tool_calls:
        print("FINAL ANSWER:")
        print(assistant_message.content)
        break

    # The model wants one or more tools.
    messages.append(assistant_message)

    for tool_call in assistant_message.tool_calls:
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        print("TOOL REQUEST:")
        print(function_name, arguments)
        print()

        result = execute_tool(function_name, arguments)

        print("TOOL RESULT:")
        print(result)
        print()

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            }
        )

else:
    print(
        f"Agent stopped after reaching the "
        f"maximum of {MAX_ITERATIONS} iterations."
    )

# 1. Ask the model what it wants to do.
# response = client.chat.completions.create(
#     model="openai/gpt-oss-20b",
#     messages=messages,
#     tools=tools,
# )

# assistant_message = response.choices[0].message

# print("MODEL RESPONSE:")
# print(assistant_message)
# print()


# # 2. Did the model request a tool?
# if assistant_message.tool_calls:

#     messages.append(assistant_message)

#     for tool_call in assistant_message.tool_calls:
#         function_name = tool_call.function.name
#         arguments = json.loads(tool_call.function.arguments)

#         print("TOOL REQUEST:")
#         print(function_name, arguments)
#         print()

#         # 3. Execute the actual Python function.
#         result = execute_tool(function_name, arguments)

#         print("TOOL RESULT:")
#         print(result)
#         print()

#         # 4. Give the tool result back to the model.
#         messages.append(
#             {
#                 "role": "tool",
#                 "tool_call_id": tool_call.id,
#                 "content": result,
#             }
#         )

#     # 5. Ask the model for the final answer.
#     final_response = client.chat.completions.create(
#         model="openai/gpt-oss-20b",
#         messages=messages,
#         tools=tools,
#     )

#     print("FINAL ANSWER:")
#     print(final_response.choices[0].message.content)

# else:
#     print("The model did not request a tool.")
#     print(assistant_message.content)

