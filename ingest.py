import os
from dotenv import load_dotenv
from pypdf import PdfReader

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# --------------------------------------------------
# Config
# --------------------------------------------------
load_dotenv()

PDF_PATH = "data"
VECTOR_DB_PATH = "index"

CHUNK_SIZE = 1000
OVERLAP = 300

# --------------------------------------------------
# Chunking (paragraph-safe, large chunks)
# --------------------------------------------------
def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap

    return chunks

# --------------------------------------------------
# Ingest PDFs
# --------------------------------------------------
def ingest():
    documents = []

    for file in os.listdir(PDF_PATH):
        if not file.endswith(".pdf"):
            continue

        reader = PdfReader(os.path.join(PDF_PATH, file))

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
                            "source": file,
                            "page": page_no + 1,
                            "chunk": idx
                        }
                    )
                )

    embeddings = OpenAIEmbeddings(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1"
    )

    db = FAISS.from_documents(documents, embeddings)
    db.save_local(VECTOR_DB_PATH)

    print("✅ PDF ingestion completed (RAG-aligned).")

if __name__ == "__main__":
    ingest()