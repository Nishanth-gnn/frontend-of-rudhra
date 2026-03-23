import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # 1. Define how to start the local MCP server
    # Note: Change "python" to "python3" if you are on Mac/Linux and it complains
    server_params = StdioServerParameters(
        command="python", 
        args=["calendar_server.py"], # Pointing to the server we just built
    )

    print("Connecting to the LocalCalendar MCP Server...")
    
    # 2. Open the standard input/output connection
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 3. Initialize the MCP protocol session
            await session.initialize()
            print("Connected!\n")
            
            # 4. Fetch the tools from the server (This is what the LLM will see)
            tools_response = await session.list_tools()
            print("Tools discovered from the server:")
            for tool in tools_response.tools:
                print(f"- {tool.name}: {tool.description}")

            print("\n--- Testing Tool Execution ---")
            
            # 5. Manually test calling the 'add_event' tool 
            # (Later, the LLM will generate these arguments dynamically)
            result = await session.call_tool("add_event", arguments={
                "title": "MCP Client Test",
                "date": "2026-03-15 02:00 PM",
                "description": "Making sure the client and server can talk."
            })
            
            # MCP returns a list of content blocks, we print the text of the first one
            print(f"Server Response: {result.content[0].text}")

if __name__ == "__main__":
    asyncio.run(main())