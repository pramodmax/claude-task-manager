import os
from pathlib import Path


def get_data_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    data_dir = base / "claude-task-manager"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    return get_data_dir() / "tasks.db"


SESSION_FILE = get_data_dir() / "current_session.txt"

CLAUDE_CODE_PROJECT_NAME = "Claude Code Sessions"
CLAUDE_CODE_PROJECT_IDENTIFIER = "CC"
CLAUDE_CODE_PROJECT_COLOR = "#5e6ad2"
