import os
import asyncio
import base64
import requests
from datetime import datetime
from typing import TypedDict, Annotated, Optional
from dotenv import load_dotenv

load_dotenv()

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.runnables import RunnableConfig

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient

from google import genai
from google.genai import types

from mcp_tools import TOOLS as GITHUB_FUNCTIONS
from database import get_user_context  # Personalization context
from image_gen import generate_image
from db_bck import DatabaseManager, get_checkpointer  # Persistent DB Layer

# Updated Import to resolve Rename Warning
from ddgs import DDGS

# =====================================================
# ENV VALIDATION
# =====================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

if not all([OPENAI_API_KEY, GEMINI_API_KEY, NVIDIA_API_KEY]):
    raise ValueError("Missing API Keys (OpenAI, Gemini, or NVIDIA) in .env file.")

db_manager = DatabaseManager()

# =====================================================
# STATE
# =====================================================
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    image_bytes: Optional[bytes]

# =====================================================
# TOOLS
# =====================================================

@tool
def generate_image_tool(prompt: str) -> str:
    """
    Generate an image from a text prompt using FLUX model.
    Returns base64 string prefixed with [IMAGE_BASE64].
    """
    try:
        img_bytes = generate_image(prompt)
        encoded = base64.b64encode(img_bytes).decode("utf-8")
        return f"[IMAGE_BASE64]{encoded}"
    except Exception as e:
        return f"❌ Image generation failed: {str(e)}"

@tool
def web_search_tool(query: str) -> str:
    """
    Search the web for the latest information, news, and real-time data.
    Use this for any events or facts occurring after October 2023.
    """
    try:
        current_year = datetime.now().year
        # Optimization: Append current year to query for freshness
        search_query = query if str(current_year) in query else f"{query} {current_year}"
        
        with DDGS() as ddgs:
            # text() returns a list of dicts in the latest ddgs version
            results = [r for r in ddgs.text(search_query, max_results=6)]
        
        if not results:
            return "No recent web results found."

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(f"SOURCE [{i}]: {r.get('title')}\nURL: {r.get('href')}\nCONTENT: {r.get('body')}")
        
        return "\n\n---\n\n".join(formatted)
    except Exception as e:
        return f"❌ Search failed: {str(e)}"

# =====================================================
# AGENT
# =====================================================
class UnifiedAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=2048,
        )
        self.mcp_client = None
        self.chatbot = None
        self.tools_map = {}
        self.genai_client = genai.Client(api_key=GEMINI_API_KEY)
        self.saver_ctx = None 

    async def initialize(self):
        github_tools = [tool(func) for func in GITHUB_FUNCTIONS.values()]

        self.mcp_client = MultiServerMCPClient({
            "local_calendar": {
                "command": "python",
                "args": ["calendar_server.py"],
                "transport": "stdio",
            },
            "filesystem": {
                "command": "python",
                "args": ["filesystem_server.py"],
                "transport": "stdio",
            }
        })

        remote_tools = await self.mcp_client.get_tools()
        all_tools = github_tools + remote_tools + [generate_image_tool, web_search_tool]

        self.tools_map = {t.name: t for t in all_tools}
        self.llm_with_tools = self.llm.bind_tools(all_tools)

        print(f"🛠️ AGENT INITIALIZED: Found {len(self.tools_map)} total tools.")

        graph = StateGraph(ChatState)
        graph.add_node("agent_node", self.agent_node)
        graph.add_edge(START, "agent_node")
        graph.add_edge("agent_node", END)

        self.saver_ctx = get_checkpointer()
        checkpointer = self.saver_ctx.__enter__()
        checkpointer.setup()

        self.chatbot = graph.compile(checkpointer=checkpointer)

    def agent_node(self, state: ChatState, config: Optional[RunnableConfig] = None):
        full_messages = list(state["messages"])
        image_bytes = state.get("image_bytes")
        
        active_tid = config["configurable"].get("thread_id", "default_thread") if config else "default_thread"
        messages = full_messages[-16:] if len(full_messages) > 16 else full_messages

        now_dt = datetime.now()
        current_date_str = now_dt.strftime("%A, %B %d, %Y, %I:%M %p")
        cutoff_date = "October 2023"

        # UPDATED: DESCRIPTIVE & ANALYTICAL PROMPT
        sys_msg = SystemMessage(
            content=(
                f"### CORE ROLE\n"
                f"You are a professional AI Research Assistant. Today is {current_date_str}.\n\n"
                
                f"### KNOWLEDGE & TIME CONSTRAINTS\n"
                f"- Internal knowledge cutoff: {cutoff_date}.\n"
                f"- For any facts, news, or technical releases after {cutoff_date}, you MUST use 'web_search_tool'.\n\n"
                
                f"### OPERATIONAL GUIDELINES (DESCRIPTIVE MODE)\n"
                f"- **Comprehensive Synthesis**: Do not just list snippets. Analyze all provided search results and combine them into a detailed, cohesive narrative.\n"
                f"- **Depth of Information**: If asked about a version or event, include release dates, major features, context, and implications.\n"
                f"- **Structured Layout**: Use Markdown headers (###), bold text, and bullet points for high readability.\n"
                f"- **Citations**: Cite every factual claim using [1], [2], etc., corresponding to the search source index.\n"
                f"- **Tone**: Maintain a professional, helpful, and grounded tone. Prioritize accuracy over brevity."
            )
        )

        if image_bytes:
            image_context = self.analyze_image(image_bytes)
            if image_context:
                messages.append(SystemMessage(content=f"User uploaded image context: {image_context}"))

        steps = 0
        while steps < 10:
            response = self.llm_with_tools.invoke([sys_msg] + messages)

            if not getattr(response, "tool_calls", None):
                return {"messages": [response], "image_bytes": None}

            messages.append(response)

            for call in response.tool_calls:
                name = call["name"]
                args = call.get("args", {})
                cid = call["id"]

                print(f"🚀 AGENT CALLING TOOL: {name}")

                if name not in self.tools_map:
                    messages.append(ToolMessage(content="Tool not found", tool_call_id=cid))
                    continue

                try:
                    tool_obj = self.tools_map[name]
                    if name == "web_search_tool":
                        result = asyncio.run(asyncio.to_thread(tool_obj.invoke, args))
                    else:
                        result = asyncio.run(tool_obj.ainvoke(args))

                    if isinstance(result, str) and result.startswith("[IMAGE_BASE64]"):
                        raw_b64 = result.replace("[IMAGE_BASE64]", "")
                        img_data = base64.b64decode(raw_b64)
                        att_id = db_manager.save_image_attachment(active_tid, img_data)
                        return {"messages": [AIMessage(content=f"[IMAGE_STORED_ID:{att_id}]")], "image_bytes": None}

                    messages.append(ToolMessage(content=str(result), tool_call_id=cid))
                except Exception as e:
                    print(f"🔥 TOOL ERROR: {e}")
                    messages.append(ToolMessage(content=str(e), tool_call_id=cid))

            steps += 1

        return {"messages": [AIMessage(content="Maximum research depth reached.")], "image_bytes": None}

    def analyze_image(self, image_bytes: bytes) -> str:
        if not image_bytes: return ""
        try:
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            response = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "meta/llama-3.2-11b-vision-instruct",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }]
                }
            )
            return response.json()["choices"][0]["message"]["content"] if response.status_code == 200 else ""
        except: return ""

    def transcribe_audio(self, audio_bytes):
        if not audio_bytes: return None
        try:
            res = self.genai_client.models.generate_content(
                model="gemini-flash-latest",
                contents=[types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"), "Transcribe exactly."]
            )
            return res.text.strip()
        except: return None

def generate_chat_title(text: str) -> str:
    try:
        llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            model="gpt-4o-mini",
            temperature=0.2,
            max_tokens=20,
        )
        prompt = f"Generate a short creative chat title (max 4 words) for: {text}. No quotes."
        title = llm.invoke(prompt).content.strip()
        return " ".join(title.split()[:4])
    except: return "New Chat"