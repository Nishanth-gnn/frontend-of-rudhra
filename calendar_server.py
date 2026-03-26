import os
import json
import uuid
import requests
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Optional
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load credentials
load_dotenv()

# Initialize the MCP Server
mcp = FastMCP("LocalCalendar")

# =====================================================
# CONFIG & CREDENTIALS
# =====================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(current_dir, "calendar_db.json")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =====================================================
# GIT-OPS LOGIC (CLOUD PERSISTENCE)
# =====================================================

def git_sync_cloud():
    """
    Ensures the local calendar data is pushed to GitHub.
    This is what makes the system work when your laptop is OFF.
    """
    try:
        # Check if DB_FILE exists locally first
        if not os.path.exists(DB_FILE):
            return False

        # Stage the file
        subprocess.run(["git", "add", DB_FILE], check=True, capture_output=True)
        
        # Create commit message
        commit_msg = f"Sync: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Commit changes
        subprocess.run(["git", "commit", "-m", commit_msg], check=True, capture_output=True)
        
        # Push to the 'main' branch
        subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Git Error: {e.stderr.decode()}")
        return False

# =====================================================
# DB UTILS (PRUNING & LOADING)
# =====================================================

def prune_db():
    """Removes events older than 2 days to keep the file small."""
    if not os.path.exists(DB_FILE): 
        # Create empty DB if it doesn't exist
        with open(DB_FILE, "w") as f:
            json.dump({}, f)
        return
    
    try:
        with open(DB_FILE, "r") as f:
            db = json.load(f)
    except: return

    now = datetime.now()
    threshold = now - timedelta(days=2)
    
    pruned_db = {eid: info for eid, info in db.items() 
                 if datetime.strptime(info['date'].split(' ')[0], "%Y-%m-%d") >= threshold}
    
    with open(DB_FILE, "w") as f:
        json.dump(pruned_db, f, indent=4)

def load_db() -> Dict[str, dict]:
    prune_db()
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_and_sync(db: Dict[str, dict]):
    """Saves locally and triggers Git push."""
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)
    return git_sync_cloud()

# =====================================================
# FULL CRUD TOOLS
# =====================================================

@mcp.tool()
def add_event(title: str, date: str, time_str: str, description: str = "") -> str:
    """CREATE: Adds a new event and pushes to GitHub for offline reminders."""
    db = load_db()
    event_id = str(uuid.uuid4())[:8]
    db[event_id] = {
        "title": title, 
        "date": date, 
        "time": time_str, 
        "description": description, 
        "notified": False
    }
    sync = save_and_sync(db)
    status = "Synced to Cloud ☁️" if sync else "Local Only 💻 (Check Git Setup)"
    return f"✅ Event '{title}' added. Status: {status}"

@mcp.tool()
def get_events() -> str:
    """READ: Returns all active events."""
    db = load_db()
    if not db: return "Calendar is empty."
    lines = [f"ID: {eid} | {info['date']} {info.get('time','')} | {info['title']}" for eid, info in db.items()]
    return "📅 Current Schedule:\n" + "\n".join(lines)

@mcp.tool()
def update_event(event_id: str, title: str = None, date: str = None, time_str: str = None, description: str = None) -> str:
    """UPDATE: Modifies an event and re-syncs to Cloud."""
    db = load_db()
    if event_id not in db:
        return f"❌ Error: ID {event_id} not found."
    
    if title: db[event_id]['title'] = title
    if date: db[event_id]['date'] = date
    if time_str: db[event_id]['time'] = time_str
    if description: db[event_id]['description'] = description
    
    # Reset notified so the Worker checks the new time
    db[event_id]['notified'] = False
    
    sync = save_and_sync(db)
    return f"✅ Updated ID {event_id}. Cloud Sync: {'Success' if sync else 'Failed'}"

@mcp.tool()
def delete_event(event_id: str) -> str:
    """DELETE: Removes an event and updates the Cloud JSON."""
    db = load_db()
    if event_id in db:
        title = db[event_id]['title']
        del db[event_id]
        sync = save_and_sync(db)
        return f"🗑️ Deleted: {title}. Cloud Sync: {'Success' if sync else 'Failed'}"
    return f"❌ Error: ID {event_id} not found."

if __name__ == "__main__":
    prune_db()
    mcp.run(transport='stdio')