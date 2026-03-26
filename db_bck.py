import os
import psycopg2
from psycopg2.extras import RealDictCursor
from langgraph.checkpoint.postgres import PostgresSaver
from dotenv import load_dotenv

load_dotenv()

# Get the verified URL from your .env
DB_URL = os.getenv("DATABASE_URL")

class DatabaseManager:
    def __init__(self):
        self.url = DB_URL

    def get_connection(self):
        """Returns a standard psycopg2 connection for synchronous tasks."""
        return psycopg2.connect(self.url)

    # --------------------------------------------------
    # THREAD & SIDEBAR LOGIC
    # --------------------------------------------------
    def save_chat_thread(self, thread_id, title, user_id="default_user"):
        """Registers or updates a chat thread in the 'chat_threads' table."""
        query = """
        INSERT INTO chat_threads (thread_id, title, user_id, last_updated)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (thread_id) 
        DO UPDATE SET title = EXCLUDED.title, last_updated = CURRENT_TIMESTAMP;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (thread_id, title, user_id))
                conn.commit()
        except Exception as e:
            print(f"Error saving chat thread: {e}")

    def get_all_threads(self, user_id="default_user"):
        """Fetches all threads for the sidebar."""
        query = "SELECT thread_id, title FROM chat_threads WHERE user_id = %s ORDER BY last_updated DESC;"
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (user_id,))
                    return cur.fetchall()
        except Exception as e:
            print(f"Error fetching threads: {e}")
            return []

    def update_chat_title(self, thread_id, new_title):
        """Updates the title of an existing chat thread."""
        query = "UPDATE chat_threads SET title = %s, last_updated = CURRENT_TIMESTAMP WHERE thread_id = %s;"
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (new_title, thread_id))
                conn.commit()
                print(f"✅ Thread {thread_id} renamed to: {new_title}")
        except Exception as e:
            print(f"Error updating chat title: {e}")

    def delete_chat_thread(self, thread_id):
        """Deletes a thread and all its associated data (cascading cleanup)."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Delete associated images/attachments
                    cur.execute("DELETE FROM chat_attachments WHERE thread_id = %s;", (thread_id,))
                    
                    # 2. Delete Download Configs (the PDF paths)
                    cur.execute("DELETE FROM chat_download_configs WHERE thread_id = %s;", (thread_id,))

                    # 3. Delete LangGraph checkpoints (history)
                    cur.execute("DELETE FROM checkpoints WHERE thread_id = %s;", (thread_id,))
                    cur.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s;", (thread_id,))
                    cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s;", (thread_id,))
                    
                    # 4. Delete the thread record itself
                    cur.execute("DELETE FROM chat_threads WHERE thread_id = %s;", (thread_id,))
                    
                conn.commit()
                print(f"🗑️ Thread {thread_id} and all associated data deleted.")
        except Exception as e:
            print(f"Error deleting chat thread: {e}")

    # --------------------------------------------------
    # DOWNLOAD PATH LOGIC
    # --------------------------------------------------
    def get_chat_download_path(self, thread_id):
        """Retrieves the persistent PDF path for a specific thread."""
        query = "SELECT pdf_path FROM chat_download_configs WHERE thread_id = %s;"
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (thread_id,))
                    result = cur.fetchone()
                    return result[0] if result else None
        except Exception as e:
            print(f"Error fetching download path: {e}")
            return None

    def save_chat_download_path(self, thread_id, pdf_path):
        """Saves or updates the persistent PDF path for a thread."""
        query = """
        INSERT INTO chat_download_configs (thread_id, pdf_path, last_updated)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (thread_id) 
        DO UPDATE SET pdf_path = EXCLUDED.pdf_path, last_updated = CURRENT_TIMESTAMP;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (thread_id, pdf_path))
                conn.commit()
                print(f"💾 PDF Path saved for thread {thread_id}: {pdf_path}")
        except Exception as e:
            print(f"Error saving download path: {e}")

    # --------------------------------------------------
    # IMAGE / ATTACHMENT LOGIC
    # --------------------------------------------------
    def save_image_attachment(self, thread_id, image_bytes, mime_type="image/png"):
        """Stores binary image data into BYTEA column."""
        query = """
        INSERT INTO chat_attachments (thread_id, file_data, mime_type)
        VALUES (%s, %s, %s)
        RETURNING attachment_id;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (thread_id, psycopg2.Binary(image_bytes), mime_type))
                    attachment_id = cur.fetchone()[0]
                    conn.commit()
                    return attachment_id
        except Exception as e:
            print(f"Error saving image: {e}")
            return None

    def get_image_by_id(self, attachment_id):
        """Retrieves image binary data for the frontend."""
        query = "SELECT file_data, mime_type FROM chat_attachments WHERE attachment_id = %s;"
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (attachment_id,))
                    return cur.fetchone()
        except Exception as e:
            print(f"Error fetching image {attachment_id}: {e}")
            return None

# --------------------------------------------------
# LANGGRAPH PERSISTENCE FACTORY
# --------------------------------------------------
def get_checkpointer():
    """
    Returns the PostgresSaver context manager.
    """
    return PostgresSaver.from_conn_string(DB_URL)