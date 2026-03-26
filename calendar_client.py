import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # 1. Define how to start the local MCP server
    # Note: Use "python" or "python3" depending on your environment
    server_params = StdioServerParameters(
        command="python", 
        args=["calendar_server.py"], # Ensuring this matches your server filename
    )

    print("🔍 Probing LocalCalendar MCP Server...")
    
    try:
        # 2. Open the standard input/output connection
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                
                # 3. Initialize the MCP protocol session
                await session.initialize()
                print("✅ Connection Established!\n")
                
                # 4. Fetch the tools from the server
                # This verifies the server is correctly exporting its functions
                tools_response = await session.list_tools()
                
                print("🛠️  Discovered Tools:")
                if not tools_response.tools:
                    print("⚠️  Warning: No tools found on this server.")
                else:
                    for tool in tools_response.tools:
                        print(f"  - {tool.name}: {tool.description}")
                        # Optional: Print the arguments the LLM will see
                        print(f"    Parameters: {tool.inputSchema.get('properties', {}).keys()}")

                print("\n🏁 Discovery complete. Connection closed.")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())