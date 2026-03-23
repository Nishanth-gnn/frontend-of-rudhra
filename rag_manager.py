import os
import hashlib
import json
from datetime import datetime

REGISTRY_PATH = "registry.json"
DATA_DIR = "data"
INDEX_DIR = "index"

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)

def get_file_hash(file_bytes):
    """Generates a SHA-256 hash of the file content."""
    return hashlib.sha256(file_bytes).hexdigest()

def load_registry():
    """Loads the material registry."""
    if not os.path.exists(REGISTRY_PATH):
        return {"materials": []}
    with open(REGISTRY_PATH, "r") as f:
        return json.load(f)

def save_registry(registry):
    """Saves the material registry."""
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=4)

def check_material_exists(file_hash):
    """Checks if a hash already exists in the registry."""
    registry = load_registry()
    for item in registry["materials"]:
        if item["content_hash"] == file_hash:
            return item
    return None

def add_to_registry(file_name, file_hash):
    """Adds a new successful ingestion to the registry."""
    registry = load_registry()
    
    # Check if this exact hash is already there
    if any(m["content_hash"] == file_hash for m in registry["materials"]):
        return
    
    new_entry = {
        "source_filename": file_name,
        "content_hash": file_hash,
        "vector_db_path": os.path.join(INDEX_DIR, file_hash),
        "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    registry["materials"].append(new_entry)
    save_registry(registry)

def list_all_materials():
    """Returns the list of available materials for the UI."""
    return load_registry()["materials"]