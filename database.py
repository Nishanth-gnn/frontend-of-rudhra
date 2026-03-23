import sqlite3
import json

DB_NAME = "user_context.db"

def init_db():
    """Initializes the database and creates the table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # user_id will be things like 'u1' or your thread_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            preferences TEXT,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_user_context(user_id: str, context_dict: dict):
    """Saves or updates the user's personal choices (overwrites if exists)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    context_json = json.dumps(context_dict)
    cursor.execute('''
        INSERT INTO user_profiles (user_id, preferences)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET 
            preferences = excluded.preferences,
            last_updated = CURRENT_TIMESTAMP
    ''', (user_id, context_json))
    conn.commit()
    conn.close()

def get_user_context(user_id: str) -> dict:
    """Retrieves the stored preferences for a user."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT preferences FROM user_profiles WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.loads(row[0])
    return {}

# Run initialization automatically when the file is used
init_db()