import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN not configured in environment variables.")

# =====================================================
# HEADERS + SAFE REQUEST
# =====================================================

def github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

def safe_get(url: str):
    response = requests.get(url, headers=github_headers())
    if response.status_code != 200:
        return f"❌ GitHub API Error {response.status_code}:\n{response.text}"
    return response.json()

# =====================================================
# GITHUB TOOLS
# =====================================================

def get_authenticated_user():
    """Helper function to get the authenticated user's login. Not exposed to LLM directly."""
    data = safe_get("https://api.github.com/user")
    if isinstance(data, str):
        raise Exception(data)
    return data["login"]

def list_github_repos():
    """Lists all GitHub repositories owned by the authenticated user."""
    data = safe_get("https://api.github.com/user/repos")
    if isinstance(data, str):
        return data

    return [
        {
            "name": repo["name"],
            "language": repo["language"],
            "created_at": repo["created_at"],
            "updated_at": repo["updated_at"]
        }
        for repo in data
    ]

def count_github_repos():
    """Returns the total number of GitHub repositories owned by the user."""
    repos = list_github_repos()
    if isinstance(repos, str):
        return repos
    return len(repos)

def get_repo_details(repo_name: str):
    """Gets detailed information (stars, forks, description) about a specific GitHub repository."""
    owner = get_authenticated_user()
    data = safe_get(f"https://api.github.com/repos/{owner}/{repo_name}")

    if isinstance(data, str):
        return data

    return {
        "name": data["name"],
        "description": data["description"],
        "language": data["language"],
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "created_at": data["created_at"],
        "updated_at": data["updated_at"]
    }

def list_repo_files(repo_name: str, path: str = ""):
    """Lists the files and directories inside a specific GitHub repository. Optionally provide a folder path."""
    owner = get_authenticated_user()
    data = safe_get(f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}")

    if isinstance(data, str):
        return data

    if isinstance(data, dict):
        return [data["name"]]

    return [{"name": file["name"], "type": file["type"]} for file in data]

def read_repo_file(repo_name: str, file_path: str):
    """Reads and decodes the text content of a specific file in a GitHub repository."""
    owner = get_authenticated_user()
    data = safe_get(f"https://api.github.com/repos/{owner}/{repo_name}/contents/{file_path}")

    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return "⚠ Provided path is a directory, not a file."
    if data.get("type") != "file":
        return "⚠ Not a readable file."

    try:
        return base64.b64decode(data["content"]).decode("utf-8")
    except Exception:
        return "❌ Could not decode file."

def detect_repo_tech_stack(repo_name: str):
    """Detects and returns the programming languages and tech stack used in a specific GitHub repository."""
    owner = get_authenticated_user()
    return safe_get(f"https://api.github.com/repos/{owner}/{repo_name}/languages")

# =====================================================
# TOOL REGISTRY
# =====================================================

TOOLS = {
    "list_github_repos": list_github_repos,
    "count_github_repos": count_github_repos,
    "get_repo_details": get_repo_details,
    "list_repo_files": list_repo_files,
    "read_repo_file": read_repo_file,
    "detect_repo_tech_stack": detect_repo_tech_stack,
}