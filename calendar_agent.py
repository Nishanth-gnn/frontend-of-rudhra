import asyncio
import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# Ensure your API key is set in your terminal or via a .env file
# os.environ["OPENAI_API_KEY"] = "your-openai-api-key"

async def main():
    # 1. Initialize your LLM
    model = ChatOpenAI(model="gpt-4o") 

    print("Starting the Local MCP Server and Agent...\n")
    
    # 2. Configure the MultiServerMCPClient to run our server script
    # This automatically spins up calendar_server.py in the background
    async with MultiServerMCPClient({
        "local_calendar": {
            "command": "python", 
            "args": ["calendar_server.py"],
            "transport": "stdio",
        }
    }) as client:
        
        # 3. Fetch the tools from the server and convert them for LangChain
        tools = await client.get_tools()
        print(f"Successfully loaded {len(tools)} tools from the MCP server.")

        # 4. Create a reactive agent equipped with our calendar tools
        agent = create_react_agent(model, tools)

        # 5. Simple chat loop to talk to the agent
        print("Agent is ready! (Type 'exit' to quit)\n")
        print("-" * 40)
        
        while True:
            user_input = input("You: ")
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
                
            # Stream the agent's thought process and response
            async for chunk in agent.astream({"messages": [{"role": "user", "content": user_input}]}):
                if "agent" in chunk:
                    # Print the LLM's final response
                    print(f"Agent: {chunk['agent']['messages'][-1].content}")
                elif "tools" in chunk:
                    # Print a notification when the LLM decides to use a tool
                    tool_name = chunk['tools']['messages'][-1].name
                    print(f"\n[ System: Agent executed the '{tool_name}' tool ]\n")

if __name__ == "__main__":
    asyncio.run(main())