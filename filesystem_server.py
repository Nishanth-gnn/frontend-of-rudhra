import os
import shutil
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Initialize MCP Server
mcp = FastMCP("filesystem")

# --- MULTI-DIRECTORY CONFIGURATION ---
# We use absolute paths for Sunita's system folders
DESKTOP_ROOT = Path(r"C:\Users\Sunita\Desktop").resolve()
DOCUMENTS_ROOT = Path(r"C:\Users\Sunita\Documents").resolve()
PROJECT_ROOT = Path(".").resolve()

ALLOWED_ROOTS = [
    DESKTOP_ROOT,
    DOCUMENTS_ROOT,
    PROJECT_ROOT,
]

# ✅ FIXED: Explicit mapping for common aliases
PATH_ALIASES = {
    "desktop": DESKTOP_ROOT,
    "documents": DOCUMENTS_ROOT,
}

def safe_path(path_str: str) -> str:
    """
    Resolves aliases like 'desktop' to absolute system paths and 
    enforces security boundaries within ALLOWED_ROOTS.
    """
    try:
        path_str = path_str.strip()
        lower_path = path_str.lower().replace("/", "\\") # Standardize slashes for Windows

        # 1. Alias Resolution (e.g., "desktop/rama.txt" -> "C:\Users\Sunita\Desktop\rama.txt")
        target_path = None
        for alias, root_path in PATH_ALIASES.items():
            if lower_path.startswith(alias):
                # Strip the alias prefix and any leading slashes
                suffix = path_str[len(alias):].lstrip("\\/")
                target_path = (root_path / suffix).resolve()
                break
        
        # 2. If no alias found, treat as standard path
        if target_path is None:
            target_path = Path(os.path.expanduser(path_str)).resolve()

        # 3. Security check: Is the resolved path inside an allowed root?
        is_allowed = any(
            target_path == root or root in target_path.parents 
            for root in ALLOWED_ROOTS
        )
        
        if not is_allowed:
            allowed_str = ", ".join([str(r) for r in ALLOWED_ROOTS])
            raise PermissionError(
                f"Access Denied: '{path_str}' resolves to '{target_path}', "
                f"which is outside permitted zones: {allowed_str}"
            )
            
        return str(target_path)
    
    except Exception as e:
        if isinstance(e, PermissionError):
            raise e
        raise ValueError(f"Invalid path format: {str(e)}")

# --- READ-ONLY TOOLS ---

@mcp.tool()
def read_text_file(path: str) -> str:
    """Reads a text file. Use 'desktop/filename.txt' for the Desktop."""
    with open(safe_path(path), "r", encoding="utf-8") as f:
        return f.read()

@mcp.tool()
def list_directory(path: str = ".") -> list:
    """Lists directory contents. Defaults to current project folder."""
    p = safe_path(path)
    items = os.listdir(p)
    return [f"[DIR] {i}" if os.path.isdir(os.path.join(p, i)) else f"[FILE] {i}" for i in items]

@mcp.tool()
def directory_tree(path: str = ".") -> str:
    """Returns a visual tree of the directory."""
    def build_tree(root, prefix=""):
        tree = []
        try:
            items = sorted(os.listdir(root))
        except PermissionError:
            return [f"{prefix}└── [ACCESS DENIED]"]
            
        for i, item in enumerate(items):
            full_item_path = os.path.join(root, item)
            connector = "└── " if i == len(items) - 1 else "├── "
            tree.append(f"{prefix}{connector}{item}")
            if os.path.isdir(full_item_path):
                extension = "    " if i == len(items) - 1 else "│   "
                tree.extend(build_tree(full_item_path, prefix + extension))
        return tree
    return "\n".join(build_tree(safe_path(path)))

# --- WRITE/DELETE TOOLS ---

@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Writes content to a file. Example: path='desktop/rama.txt'"""
    full_path = safe_path(path)
    # Ensure the parent directory exists
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"✅ Successfully wrote to: {full_path}"

@mcp.tool()
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Replaces old_text with new_text in a file."""
    full_path = safe_path(path)
    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()
    if old_text not in content:
        return "Error: old_text not found in file."
    new_content = content.replace(old_text, new_text, 1)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return f"Updated {path} successfully."

@mcp.tool()
def create_directory(path: str) -> str:
    """Creates a directory at the given path."""
    os.makedirs(safe_path(path), exist_ok=True)
    return f"Directory {path} created/verified."

@mcp.tool()
def move_file(source: str, destination: str) -> str:
    """Moves a file from source to destination."""
    src = safe_path(source)
    dst = safe_path(destination)
    shutil.move(src, dst)
    return f"Moved {source} to {destination}"

if __name__ == "__main__":
    mcp.run()