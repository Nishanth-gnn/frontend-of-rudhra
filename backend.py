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
from langgraph.checkpoint.memory import InMemorySaver

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient

from google import genai
from google.genai import types

from mcp_tools import TOOLS as GITHUB_FUNCTIONS
from database import get_user_context
from image_gen import generate_image


# =====================================================
# ENV VALIDATION
# =====================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

if not all([OPENAI_API_KEY, GEMINI_API_KEY, NVIDIA_API_KEY]):
    raise ValueError("Missing API Keys (OpenAI, Gemini, or NVIDIA) in .env file.")


# =====================================================
# STATE
# =====================================================
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    image_bytes: Optional[bytes]


# =====================================================
# IMAGE TOOL
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

        all_tools = github_tools + remote_tools + [generate_image_tool]

        self.tools_map = {t.name: t for t in all_tools}
        self.llm_with_tools = self.llm.bind_tools(all_tools)

        graph = StateGraph(ChatState)
        graph.add_node("agent_node", self.agent_node)
        graph.add_edge(START, "agent_node")
        graph.add_edge("agent_node", END)

        self.chatbot = graph.compile(checkpointer=InMemorySaver())

    # --------------------------------------------------
    # IMAGE ANALYSIS
    # --------------------------------------------------
    def analyze_image(self, image_bytes: bytes) -> str:
        if not image_bytes:
            return ""
        try:
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            response = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {NVIDIA_API_KEY}",
                    "Content-Type": "application/json"
                },
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
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            return ""
        except:
            return ""

    # --------------------------------------------------
    # AUDIO TRANSCRIPTION
    # --------------------------------------------------
    def transcribe_audio(self, audio_bytes):
        if not audio_bytes:
            return None
        try:
            res = self.genai_client.models.generate_content(
                model="gemini-flash-latest",
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                    "Transcribe exactly."
                ]
            )
            return res.text.strip()
        except:
            return None

    # --------------------------------------------------
    # CORE LOOP
    # --------------------------------------------------
    async def agent_node(self, state: ChatState):
        full_messages = list(state["messages"])
        image_bytes = state.get("image_bytes")

        if len(full_messages) > 16:
            messages = full_messages[-16:]
        else:
            messages = full_messages

        personal = get_user_context("default_user").get("raw_text", "")
        now = datetime.now().strftime("%A, %B %d, %Y, %I:%M %p")

        # ✅ ONLY CHANGE (SAFE PROMPT INJECTION)
        sys_msg = SystemMessage(
            content=f"""You are a helpful assistant. Today is {now}.
{personal}

When using filesystem tools:
- Use 'desktop/' for Desktop directory
- Use 'documents/' for Documents directory
- Avoid using ambiguous relative paths like './' unless explicitly required
"""
        )

        if image_bytes:
            image_context = self.analyze_image(image_bytes)
            if image_context:
                messages.append(
                    SystemMessage(content=f"Image context: {image_context}")
                )

        steps = 0
        while steps < 10:
            response = await self.llm_with_tools.ainvoke([sys_msg] + messages)

            if not getattr(response, "tool_calls", None):
                return {"messages": [response], "image_bytes": None}

            messages.append(response)

            for call in response.tool_calls:
                name = call["name"]
                args = call.get("args", {})
                cid = call["id"]

                if name not in self.tools_map:
                    messages.append(ToolMessage(content="Tool not found", tool_call_id=cid))
                    continue

                try:
                    result = await self.tools_map[name].ainvoke(args)

                    if isinstance(result, str) and result.startswith("[IMAGE_BASE64]"):
                        return {
                            "messages": [AIMessage(content=result)],
                            "image_bytes": None
                        }

                    messages.append(ToolMessage(content=str(result), tool_call_id=cid))

                except Exception as e:
                    messages.append(ToolMessage(content=str(e), tool_call_id=cid))

            steps += 1

        return {"messages": [AIMessage(content="Max steps reached")], "image_bytes": None}


# --------------------------------------------------
# TITLE GENERATION
# --------------------------------------------------
def generate_chat_title(text: str) -> str:
    try:
        llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            model="gpt-4o-mini",
            temperature=0.2,
            max_tokens=20,
        )

        prompt = f"""
        Generate a short, creative chat title (max 4 words) based on the following user query.
        Do not use punctuation or quotes.
        Query: {text}
        """

        title = llm.invoke(prompt).content.strip()
        return " ".join(title.split()[:4])

    except:
        return "New Chat"