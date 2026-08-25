import asyncio

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


SERVER_PARAMS = StdioServerParameters(
    command="uv",
    args=["run", "mcp-simple-resource"],
    cwd="/tmp/mcp-python-sdk/examples/servers/simple-resource",
)


async def main():
    async with stdio_client(SERVER_PARAMS) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            print("CONNECTED")

            print("\nSERVER CAPABILITIES:")
            print(session.server_capabilities)

            print("\nRESOURCES:")

            result = await session.list_resources()
            for resource in result.resources:
                print(resource)

            print("\nREAD RESOURCE:")
            result = await session.read_resource("file:///greeting.txt")
            print(result)

            print("\nTOOLS:")
            if session.server_capabilities.tools:
                result = await session.list_tools()
                print(result)
            else:
                print("Not supported")
                

            print("\nPROMPTS:")
            if session.server_capabilities.prompts:
                result = await session.list_prompts()
                print(result)
            else:
                print("Not supported")


if __name__ == "__main__":
    asyncio.run(main())


# import asyncio

# from mcp import ClientSession
# from mcp.client.streamable_http import streamable_http_client


# SERVER_URL = "https://example-server.modelcontextprotocol.io/mcp"


# async def main():
#     async with streamable_http_client(SERVER_URL) as (
#         read_stream,
#         write_stream,
#     ):
#         async with ClientSession(read_stream, write_stream) as session:
#             await session.initialize()

#             print("CONNECTED")

#             print("\nSERVER CAPABILITIES:")
#             print(session.get_server_capabilities())


# if __name__ == "__main__":
#     asyncio.run(main())