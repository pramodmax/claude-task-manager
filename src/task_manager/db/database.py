import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from task_manager.config import get_db_path

_local = threading.local()

STATUSES = ["backlog", "todo", "in_progress", "done", "cancelled"]
PRIORITIES = ["urgent", "high", "medium", "low", "no_priority"]

STATUS_LABELS = {
    "backlog": "Backlog",
    "todo": "Todo",
    "in_progress": "In Progress",
    "done": "Done",
    "cancelled": "Cancelled",
}
PRIORITY_LABELS = {
    "urgent": "Urgent",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "no_priority": "No Priority",
}
STATUS_ICONS = {
    "backlog": "○",
    "todo": "◎",
    "in_progress": "◕",
    "done": "✓",
    "cancelled": "✗",
}
PRIORITY_ICONS = {
    "urgent": "↑↑",
    "high": "↑",
    "medium": "→",
    "low": "↓",
    "no_priority": "—",
}


def _conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(str(get_db_path()), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


@contextmanager
def _tx():
    conn = _conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            color       TEXT NOT NULL DEFAULT '#6366f1',
            identifier  TEXT NOT NULL DEFAULT 'PROJ',
            path        TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        );

        CREATE TABLE IF NOT EXISTS labels (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            color      TEXT NOT NULL DEFAULT '#6366f1',
            project_id TEXT REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS issues (
            id             TEXT PRIMARY KEY,
            number         INTEGER NOT NULL,
            identifier     TEXT NOT NULL,
            title          TEXT NOT NULL,
            description    TEXT NOT NULL DEFAULT '',
            status         TEXT NOT NULL DEFAULT 'backlog',
            priority       TEXT NOT NULL DEFAULT 'medium',
            project_id     TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            assignee       TEXT NOT NULL DEFAULT '',
            due_date       TEXT NOT NULL DEFAULT '',
            estimate       INTEGER NOT NULL DEFAULT 0,
            tokens_input   INTEGER NOT NULL DEFAULT 0,
            tokens_output  INTEGER NOT NULL DEFAULT 0,
            created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        );

        CREATE TABLE IF NOT EXISTS issue_labels (
            issue_id TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            label_id TEXT NOT NULL REFERENCES labels(id) ON DELETE CASCADE,
            PRIMARY KEY (issue_id, label_id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id         TEXT PRIMARY KEY,
            issue_id   TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            body       TEXT NOT NULL,
            author     TEXT NOT NULL DEFAULT 'me',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        );

        CREATE INDEX IF NOT EXISTS idx_issues_project  ON issues(project_id);
        CREATE INDEX IF NOT EXISTS idx_issues_status   ON issues(status);
        CREATE INDEX IF NOT EXISTS idx_comments_issue  ON comments(issue_id);
    """)
    conn.commit()
    _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Add new columns to existing databases without losing data."""
    migrations = [
        "ALTER TABLE projects ADD COLUMN path TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE issues ADD COLUMN tokens_input INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE issues ADD COLUMN tokens_output INTEGER NOT NULL DEFAULT 0",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            pass  # column already exists


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Projects ──────────────────────────────────────────────────────────────────

def list_projects() -> list[dict]:
    rows = _conn().execute("SELECT * FROM projects ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_project(project_id: str) -> dict | None:
    row = _conn().execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return dict(row) if row else None


def get_project_by_name(name: str) -> dict | None:
    row = _conn().execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def get_project_by_path(path: str) -> dict | None:
    row = _conn().execute(
        "SELECT * FROM projects WHERE path = ? AND path != ''", (path,)
    ).fetchone()
    return dict(row) if row else None


def get_project_stats(project_id: str) -> dict:
    conn = _conn()
    row = conn.execute(
        """SELECT
               COUNT(*) AS total_issues,
               SUM(CASE WHEN status NOT IN ('done','cancelled') THEN 1 ELSE 0 END) AS open_issues,
               COALESCE(SUM(tokens_input), 0)  AS tokens_input,
               COALESCE(SUM(tokens_output), 0) AS tokens_output
           FROM issues WHERE project_id = ?""",
        (project_id,),
    ).fetchone()
    project = get_project(project_id)
    return {
        "project": project,
        "total_issues": row["total_issues"] or 0,
        "open_issues": row["open_issues"] or 0,
        "tokens_input": row["tokens_input"] or 0,
        "tokens_output": row["tokens_output"] or 0,
    }


def create_project(
    name: str,
    description: str = "",
    color: str = "#6366f1",
    identifier: str = "",
    path: str = "",
) -> dict:
    if not identifier:
        parts = name.split()
        identifier = "".join(w[0] for w in parts[:3]).upper() or name[:3].upper()
    pid = _new_id()
    with _tx() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description, color, identifier, path) VALUES (?,?,?,?,?,?)",
            (pid, name, description, color, identifier, path),
        )
    return get_project(pid)


def update_project(project_id: str, **kwargs) -> dict | None:
    allowed = {"name", "description", "color", "identifier", "path"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if updates:
        updates["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with _tx() as conn:
            conn.execute(
                f"UPDATE projects SET {set_clause} WHERE id = ?",
                [*updates.values(), project_id],
            )
    return get_project(project_id)


def delete_project(project_id: str) -> bool:
    with _tx() as conn:
        cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return cursor.rowcount > 0


# ── Issues ────────────────────────────────────────────────────────────────────

def _next_number(conn: sqlite3.Connection, project_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(number), 0) FROM issues WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    return row[0] + 1


def list_issues(
    project_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    assignee: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM issues WHERE 1=1"
    params: list = []
    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if assignee:
        query += " AND assignee = ?"
        params.append(assignee)
    if search:
        query += " AND (title LIKE ? OR description LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    query += """
        ORDER BY
            CASE status
                WHEN 'in_progress' THEN 0 WHEN 'todo' THEN 1
                WHEN 'backlog' THEN 2 WHEN 'done' THEN 3
                WHEN 'cancelled' THEN 4 ELSE 5
            END,
            CASE priority
                WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
                WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4
            END,
            number
    """
    return [dict(r) for r in _conn().execute(query, params).fetchall()]


def get_issue(issue_id: str) -> dict | None:
    row = _conn().execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
    if not row:
        row = _conn().execute(
            "SELECT * FROM issues WHERE identifier = ?", (issue_id,)
        ).fetchone()
    return dict(row) if row else None


def create_issue(
    title: str,
    project_id: str,
    description: str = "",
    status: str = "backlog",
    priority: str = "medium",
    assignee: str = "",
    due_date: str = "",
    estimate: int = 0,
    tokens_input: int = 0,
    tokens_output: int = 0,
    labels: list[str] | None = None,
) -> dict:
    project = get_project(project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")
    iid = _new_id()
    with _tx() as conn:
        number = _next_number(conn, project_id)
        identifier = f"{project['identifier']}-{number}"
        conn.execute(
            """INSERT INTO issues
               (id,number,identifier,title,description,status,priority,
                project_id,assignee,due_date,estimate,tokens_input,tokens_output)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (iid, number, identifier, title, description, status, priority,
             project_id, assignee, due_date, estimate, tokens_input, tokens_output),
        )
        if labels:
            for lid in labels:
                conn.execute(
                    "INSERT OR IGNORE INTO issue_labels (issue_id,label_id) VALUES (?,?)",
                    (iid, lid),
                )
    return get_issue(iid)


def update_issue(issue_id: str, **kwargs) -> dict | None:
    issue = get_issue(issue_id)
    if not issue:
        return None
    allowed = {"title", "description", "status", "priority", "assignee", "due_date", "estimate", "tokens_input", "tokens_output"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if updates:
        updates["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with _tx() as conn:
            conn.execute(
                f"UPDATE issues SET {set_clause} WHERE id = ?",
                [*updates.values(), issue["id"]],
            )
    return get_issue(issue["id"])


def delete_issue(issue_id: str) -> bool:
    issue = get_issue(issue_id)
    if not issue:
        return False
    with _tx() as conn:
        cursor = conn.execute("DELETE FROM issues WHERE id = ?", (issue["id"],))
    return cursor.rowcount > 0


# ── Labels ────────────────────────────────────────────────────────────────────

def list_labels(project_id: str | None = None) -> list[dict]:
    if project_id:
        rows = _conn().execute(
            "SELECT * FROM labels WHERE project_id = ? OR project_id IS NULL ORDER BY name",
            (project_id,),
        ).fetchall()
    else:
        rows = _conn().execute("SELECT * FROM labels ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def create_label(name: str, color: str = "#6366f1", project_id: str | None = None) -> dict:
    lid = _new_id()
    with _tx() as conn:
        conn.execute(
            "INSERT INTO labels (id,name,color,project_id) VALUES (?,?,?,?)",
            (lid, name, color, project_id),
        )
    return dict(_conn().execute("SELECT * FROM labels WHERE id = ?", (lid,)).fetchone())


# ── Comments ──────────────────────────────────────────────────────────────────

def list_comments(issue_id: str) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM comments WHERE issue_id = ? ORDER BY created_at",
        (issue_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_comment(issue_id: str, body: str, author: str = "me") -> dict:
    cid = _new_id()
    with _tx() as conn:
        conn.execute(
            "INSERT INTO comments (id,issue_id,body,author) VALUES (?,?,?,?)",
            (cid, issue_id, body, author),
        )
    return dict(_conn().execute("SELECT * FROM comments WHERE id = ?", (cid,)).fetchone())


def delete_comment(comment_id: str) -> bool:
    with _tx() as conn:
        cursor = conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    return cursor.rowcount > 0


# ── Session tracking (for Claude Code auto-tracking) ─────────────────────────

def get_or_create_claude_project() -> dict:
    from task_manager.config import (
        CLAUDE_CODE_PROJECT_COLOR,
        CLAUDE_CODE_PROJECT_IDENTIFIER,
        CLAUDE_CODE_PROJECT_NAME,
    )
    project = get_project_by_name(CLAUDE_CODE_PROJECT_NAME)
    if not project:
        project = create_project(
            name=CLAUDE_CODE_PROJECT_NAME,
            description="Auto-tracked Claude Code sessions and tasks",
            color=CLAUDE_CODE_PROJECT_COLOR,
            identifier=CLAUDE_CODE_PROJECT_IDENTIFIER,
        )
    return project


def get_or_create_project_for_path(path: str) -> dict:
    """Find or create a project matching a filesystem path (e.g. Claude Code cwd)."""
    import os
    from task_manager.config import CLAUDE_CODE_PROJECT_COLOR
    path = os.path.abspath(path)

    # Exact path match first
    project = get_project_by_path(path)
    if project:
        return project

    # Derive name from folder name
    folder = os.path.basename(path) or path
    name = folder.replace("-", " ").replace("_", " ").title()

    # Auto-generate a color from the path string (deterministic)
    colors = ["#5e6ad2","#6366f1","#0ea5e9","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899"]
    h = 0
    for c in path:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    color = colors[h % len(colors)]

    return create_project(name=name, color=color, path=path)
