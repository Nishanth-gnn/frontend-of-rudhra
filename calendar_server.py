from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Dict
import uuid
import json
import os

# Initialize the MCP Server
mcp = FastMCP("LocalCalendar")

# =====================================================
# PERSISTENT DATABASE LOGIC
# =====================================================
DB_FILE = "calendar_db.json"

def load_db() -> Dict[str, dict]:
    """Loads the calendar database from a JSON file."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_db(data: Dict[str, dict]):
    """Saves the calendar database to a JSON file."""
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# =====================================================
# CRUD OPERATIONS
# =====================================================

# --- CREATE OPERATION ---
class EventModel(BaseModel):
    title: str = Field(description="The title or name of the event")
    date: str = Field(description="The date/time of the event (e.g., '2026-03-15 10:00 AM')")
    description: str = Field(default="", description="Optional details about the event")

@mcp.tool()
def add_event(event: EventModel) -> str:
    """Creates a new event in the local calendar."""
    db = load_db()
    event_id = str(uuid.uuid4())[:8] # Generate a short unique ID
    
    db[event_id] = {
        "title": event.title,
        "date": event.date,
        "description": event.description
    }
    
    save_db(db)
    return f"Success! Event '{event.title}' added for {event.date} with ID: {event_id}"

# --- READ OPERATION ---
@mcp.tool()
def get_events() -> str:
    """Retrieves all scheduled events from the local calendar."""
    db = load_db()
    if not db:
        return "The calendar is currently empty."
    
    result = "Here are your scheduled events:\n"
    for eid, details in db.items():
        result += f"- ID: {eid} | Title: {details['title']} | Date: {details['date']} | Desc: {details['description']}\n"
    return result

# --- UPDATE OPERATION ---
class UpdateEventModel(BaseModel):
    event_id: str = Field(description="The unique ID of the event to update")
    title: str | None = Field(default=None, description="New title (optional)")
    date: str | None = Field(default=None, description="New date/time (optional)")
    description: str | None = Field(default=None, description="New description (optional)")

@mcp.tool()
def update_event(update_data: UpdateEventModel) -> str:
    """Updates an existing event in the calendar."""
    db = load_db()
    if update_data.event_id not in db:
        return f"Error: No event found with ID '{update_data.event_id}'."
    
    event = db[update_data.event_id]
    
    # Only update the fields that the LLM provided
    if update_data.title: 
        event['title'] = update_data.title
    if update_data.date: 
        event['date'] = update_data.date
    if update_data.description: 
        event['description'] = update_data.description
        
    save_db(db)
    return f"Success! Event ID '{update_data.event_id}' has been updated."

# --- DELETE OPERATION ---
class DeleteEventModel(BaseModel):
    event_id: str = Field(description="The unique ID of the event to delete")

@mcp.tool()
def delete_event(delete_data: DeleteEventModel) -> str:
    """Deletes an event from the calendar."""
    db = load_db()
    if delete_data.event_id in db:
        del db[delete_data.event_id]
        save_db(db)
        return f"Success! Event ID '{delete_data.event_id}' has been deleted."
    
    return f"Error: No event found with ID '{delete_data.event_id}'."


if __name__ == "__main__":
    # This allows the server to run via standard input/output (stdio)
    mcp.run(transport='stdio')