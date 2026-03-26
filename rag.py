import os
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()

# Use fallback logic to ensure the correct key is retrieved from .env
api_key_val = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")

if not api_key_val:
    raise ValueError("API Key (OPENROUTER_API_KEY or OPENAI_API_KEY) not found in .env file.")

# --------------------------------------------------
# LLM (OpenRouter via OpenAI-compatible API)
# --------------------------------------------------
llm = ChatOpenAI(
    api_key=str(api_key_val),
    base_url="https://openrouter.ai/api/v1",
    model="gpt-3.5-turbo",
    temperature=0.1,
    max_tokens=1500 # Increased slightly for more descriptive explanations
)

# --------------------------------------------------
# Embeddings (Standardized for Sync stability)
# --------------------------------------------------
embeddings = OpenAIEmbeddings(
    openai_api_key=str(api_key_val),
    base_url="https://openrouter.ai/api/v1",
    model="text-embedding-3-small",
    check_embedding_ctx_length=False # Prevents sync/async conflict during retrieval
)

# --------------------------------------------------
# Query normalizer
# --------------------------------------------------
def normalize_query(query: str) -> str:
    prompt = f"""
Correct spelling and casing of the following question.
Do NOT change its meaning.

Question:
{query}

Corrected question:
"""
    response = llm.invoke(prompt)
    return response.content.strip()


# --------------------------------------------------
# MAIN RAG FUNCTION (DYNAMIC LOADING)
# --------------------------------------------------
def ask_pdf(question: str) -> str:
    # 1. Check for Active Material Hash from Session State
    active_hash = st.session_state.get("active_rag_hash")
    
    if not active_hash:
        return "⚠️ No material selected. Please go to the Material Library and 'Connect' to a PDF."

    # 2. Construct specific path for this content hash
    target_db_path = os.path.join("index", active_hash)

    if not os.path.exists(target_db_path):
        return "❌ Error: Vector database for this material not found. Please re-ingest."

    # 3. Load the specific FAISS index for this query
    try:
        db = FAISS.load_local(
            target_db_path,
            embeddings,
            allow_dangerous_deserialization=True
        )
    except Exception as e:
        return f"❌ Failed to load vector database: {str(e)}"

    # 4. Process Question
    clean_question = normalize_query(question)
    docs = db.similarity_search(clean_question, k=5)

    if not docs:
        return "Not found in the document."

    # Restore document flow based on metadata
    docs = sorted(
        docs,
        key=lambda d: (
            d.metadata.get("source", ""),
            d.metadata.get("page", 0),
            d.metadata.get("chunk", 0)
        )
    )

    context = "\n\n".join(d.page_content for d in docs)

    MAX_CONTEXT_CHARS = 8000
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS]

    if not context.strip():
        return "Not found in the document."

    # UPDATED: Descriptive & Organized Prompt
    prompt = f"""
You are an expert Educational Assistant. Your goal is to explain concepts from the provided document in a clear, organized, and helpful manner.

TASK:
Answer the question using ONLY the context provided below.

CRITICAL RULES:
- **Strict Grounding**: Use ONLY the provided context. Do NOT use outside knowledge.
- **Simplification**: Explain complex concepts in simple, accessible language.
- **Organization**: Structure your answer with Markdown headers (###), bold text for key terms, and bullet points for lists.
- **Completeness**: Include all relevant details from the context, but present them as a descriptive explanation rather than just a verbatim copy.
- **Negative Constraint**: If the answer is not contained within the context, say exactly: "Not found in the document."

Context:
{context}

Question:
{clean_question}

Answer (Descriptive, structured explanation):
"""

    response = llm.invoke(prompt)
    return response.content.strip()