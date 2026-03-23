import os
from dotenv import load_dotenv
from pypdf import PdfReader
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# Import our new manager logic
from rag_manager import add_to_registry

load_dotenv()

CHUNK_SIZE = 1000
OVERLAP = 300

def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks

def process_and_ingest(file_path, file_name, file_hash):
    """
    Surgically ingests a single file into its own unique FAISS index.
    """
    documents = []
    
    # 1. Read PDF
    reader = PdfReader(file_path)
    for page_no, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        page_text = page_text.strip()

        if not page_text:
            continue

        chunks = chunk_text(page_text)

        for idx, chunk in enumerate(chunks):
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": file_name,
                        "page": page_no + 1,
                        "chunk": idx,
                        "hash": file_hash
                    }
                )
            )

    # 2. FIXED: Explicit Sync Client Configuration
    # Fetch key and ensure it's a string to prevent Async/Sync conflict
    api_key_val = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    
    embeddings = OpenAIEmbeddings(
        openai_api_key=str(api_key_val), # Explicit parameter name
        base_url="https://openrouter.ai/api/v1",
        model="text-embedding-3-small",
        check_embedding_ctx_length=False # Disables the sync/async pre-flight check
    )

    # 3. Create FAISS index
    # This will now correctly use the sync client initialized above
    db = FAISS.from_documents(documents, embeddings)
    
    # 4. Save to a unique folder named after the hash
    vector_db_path = os.path.join("index", file_hash)
    db.save_local(vector_db_path)

    # 5. Update the registry so the UI can see it
    add_to_registry(file_name, file_hash)
    
    return True