import os
import shutil
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Initialize MCP Server
mcp = FastMCP("filesystem")

# --- MULTI-DIRECTORY CONFIGURATION ---
ALLOWED_ROOTS = [
    Path(r"C:\Users\Sunita\Desktop").resolve(),
    Path(r"C:\Users\Sunita\Documents").resolve(),
    Path(".").resolve(),
]

# ✅ NEW: Generic alias map (clean + extendable)
PATH_ALIASES = {
    "desktop": Path(r"C:\Users\Sunita\Desktop").resolve(),
    "documents": Path(r"C:\Users\Sunita\Documents").resolve(),
}

def safe_path(path: str) -> str:
    """
    Checks if the requested path is within any of the ALLOWED_ROOTS.
    Supports both absolute paths and relative paths.
    """
    try:
        path = path.strip()

        # ✅ NEW: alias resolution (generalized, not overfitted)
        lower_path = path.lower()
        for alias, root in PATH_ALIASES.items():
            if lower_path.startswith(alias):
                suffix = path[len(alias):].lstrip("\\/")
                path = str(root / suffix)
                break

        # 1. Resolve path
        requested_path = Path(os.path.expanduser(path)).resolve()
        
        # 2. Security check
        is_allowed = any(
            requested_path == root or root in requested_path.parents 
            for root in ALLOWED_ROOTS
        )
        
        if not is_allowed:
            allowed_str = ", ".join([str(r) for r in ALLOWED_ROOTS])
            raise PermissionError(
                f"Access Denied: '{path}' is outside permitted zones. "
                f"Allowed roots are: {allowed_str}"
            )
            
        return str(requested_path)
    
    except Exception as e:
        if isinstance(e, PermissionError):
            raise e
        raise ValueError(f"Invalid path format: {str(e)}")

# --- READ-ONLY TOOLS ---

@mcp.tool()
def read_text_file(path: str) -> str:
    with open(safe_path(path), "r", encoding="utf-8") as f:
        return f.read()

@mcp.tool()
def list_directory(path: str = ".") -> list:
    p = safe_path(path)
    items = os.listdir(p)
    return [f"[DIR] {i}" if os.path.isdir(os.path.join(p, i)) else f"[FILE] {i}" for i in items]

@mcp.tool()
def directory_tree(path: str = ".") -> str:
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
    full_path = safe_path(path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Successfully wrote to {path}"

@mcp.tool()
def edit_file(path: str, old_text: str, new_text: str) -> str:
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
    os.makedirs(safe_path(path), exist_ok=True)
    return f"Directory {path} created/verified."

@mcp.tool()
def move_file(source: str, destination: str) -> str:
    src = safe_path(source)
    dst = safe_path(destination)
    shutil.move(src, dst)
    return f"Moved {source} to {destination}"

if __name__ == "__main__":
    mcp.run()