from mcp.server import MCPServer
import asyncio
from pydantic import BaseModel
from mcp.types import ToolAnnotations

class WeatherResult(BaseModel):
    city: str
    temperature: int
    unit: str
    conditions: str

mcp = MCPServer("weather-server")

WEATHER_DATA = {
    "San Francisco": {
        "temperature": 62,
        "unit": "F",
        "conditions": "Foggy",
    },
    "New York": {
        "temperature": 78,
        "unit": "F",
        "conditions": "Sunny",
    },
    "Bangalore": {
        "temperature": 72,
        "unit": "F",
        "conditions": "Cloudy",
    },
}

@mcp.tool(
    structured_output=True,
    annotations=ToolAnnotations(
        title="Get Weather",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def get_weather(city: str) -> WeatherResult:
    """Get the current weather for a city."""

    weather = WEATHER_DATA.get(city)

    if weather is None:
        raise ValueError(f"No weather data available for {city}")

    return WeatherResult(
        city=city,
        **weather,
    )

@mcp.resource("weather://supported-cities")
def supported_cities() -> str:
    """List cities supported by the weather server."""
    return "\n".join(WEATHER_DATA.keys())

@mcp.tool(
    structured_output=True,
    annotations=ToolAnnotations(
        title="Get Time",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def get_time(city: str) -> str:
    """Return the current local time for a city."""
    times = {
        "San Francisco": "10:30 PM",
        "New York": "1:30 AM",
        "Bangalore": "10:00 AM",
    }

    return times.get(city, f"No time data available for {city}")

@mcp.prompt()
def weather_summary(city: str):
    """Create a concise weather summary request for a city."""
    return f"Provide a concise weather summary for {city}, including the current weather and local time."


# if __name__ == "__main__":
#     asyncio.run(mcp.run_stdio_async())

if __name__ == "__main__":
    asyncio.run(
        mcp.run_streamable_http_async(
            host="0.0.0.0",
            port=8000,
            streamable_http_path="/mcp",
        )
    )