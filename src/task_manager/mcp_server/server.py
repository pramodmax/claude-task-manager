"""
MCP server for Claude Task Manager.
Run via:  task-manager mcp-server
Configure in ~/.claude/settings.json or .claude/settings.json
"""

from mcp.server.fastmcp import FastMCP

from task_manager.db import database as db

mcp = FastMCP(
    "Task Manager",
    instructions=(
        "Local task manager with Linear-like issue tracking. "
        "Use these tools to create and manage projects and issues. "
        "At the start of EVERY Claude Code session, call task_manager_create_session to register your work. "
        "Call task_manager_update_session to log progress milestones. "
        "Call task_manager_complete_session when your task is finished."
    ),
)


# ── Projects ──────────────────────────────────────────────────────────────────

@mcp.tool()
def task_manager_list_projects() -> list[dict]:
    """List all projects in the task manager."""
    return db.list_projects()


@mcp.tool()
def task_manager_create_project(
    name: str,
    description: str = "",
    color: str = "#6366f1",
    identifier: str = "",
) -> dict:
    """Create a new project. identifier is a short uppercase code like 'ENG' or 'FE'."""
    return db.create_project(name=name, description=description, color=color, identifier=identifier)


@mcp.tool()
def task_manager_update_project(
    project_id: str,
    name: str | None = None,
    description: str | None = None,
    color: str | None = None,
) -> dict | None:
    """Update a project's metadata."""
    kwargs = {k: v for k, v in locals().items() if k != "project_id" and v is not None}
    return db.update_project(project_id, **kwargs)


@mcp.tool()
def task_manager_delete_project(project_id: str) -> bool:
    """Delete a project and all its issues. Returns True if deleted."""
    return db.delete_project(project_id)


# ── Issues ────────────────────────────────────────────────────────────────────

@mcp.tool()
def task_manager_list_issues(
    project_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    assignee: str | None = None,
) -> list[dict]:
    """
    List issues with optional filters.
    status: backlog | todo | in_progress | done | cancelled
    priority: urgent | high | medium | low | no_priority
    search: substring match on title and description
    assignee: filter by assignee username (use 'claude' for Claude Code tasks)
    """
    return db.list_issues(
        project_id=project_id,
        status=status,
        priority=priority,
        search=search,
        assignee=assignee,
    )


@mcp.tool()
def task_manager_get_issue(issue_id: str) -> dict | None:
    """
    Get a single issue by its UUID or identifier (e.g. 'ENG-5').
    Returns None if not found.
    """
    return db.get_issue(issue_id)


@mcp.tool()
def task_manager_create_issue(
    title: str,
    project_id: str,
    description: str = "",
    status: str = "backlog",
    priority: str = "medium",
    assignee: str = "",
    due_date: str = "",
    estimate: int = 0,
) -> dict:
    """
    Create a new issue.
    status: backlog | todo | in_progress | done | cancelled
    priority: urgent | high | medium | low | no_priority
    due_date: ISO date string YYYY-MM-DD
    estimate: story points (integer)
    Returns the created issue dict including its generated identifier.
    """
    return db.create_issue(
        title=title,
        project_id=project_id,
        description=description,
        status=status,
        priority=priority,
        assignee=assignee,
        due_date=due_date,
        estimate=estimate,
    )


@mcp.tool()
def task_manager_update_issue(
    issue_id: str,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    assignee: str | None = None,
    due_date: str | None = None,
    estimate: int | None = None,
) -> dict | None:
    """
    Update one or more fields on an issue.
    issue_id: UUID or identifier like 'ENG-5'.
    Only pass the fields you want to change.
    Returns updated issue or None if not found.
    """
    kwargs = {k: v for k, v in locals().items() if k != "issue_id" and v is not None}
    return db.update_issue(issue_id, **kwargs)


@mcp.tool()
def task_manager_delete_issue(issue_id: str) -> bool:
    """Delete an issue by UUID or identifier. Returns True if deleted."""
    return db.delete_issue(issue_id)


# ── Labels ────────────────────────────────────────────────────────────────────

@mcp.tool()
def task_manager_list_labels(project_id: str | None = None) -> list[dict]:
    """List labels, optionally filtered by project."""
    return db.list_labels(project_id=project_id)


@mcp.tool()
def task_manager_create_label(
    name: str,
    color: str = "#6366f1",
    project_id: str | None = None,
) -> dict:
    """Create a label. project_id is optional; global labels have no project."""
    return db.create_label(name=name, color=color, project_id=project_id)


# ── Comments ──────────────────────────────────────────────────────────────────

@mcp.tool()
def task_manager_list_comments(issue_id: str) -> list[dict]:
    """List all comments on an issue."""
    return db.list_comments(issue_id)


@mcp.tool()
def task_manager_add_comment(
    issue_id: str,
    body: str,
    author: str = "claude",
) -> dict:
    """Add a comment to an issue. Use author='claude' for Claude Code comments."""
    return db.add_comment(issue_id, body=body, author=author)


@mcp.tool()
def task_manager_delete_comment(comment_id: str) -> bool:
    """Delete a comment by ID. Returns True if deleted."""
    return db.delete_comment(comment_id)


# ── Session tracking (Claude Code auto-tracking) ──────────────────────────────

@mcp.tool()
def task_manager_create_session(
    title: str,
    path: str = "",
    description: str = "",
    priority: str = "medium",
    tokens_input: int = 0,
    tokens_output: int = 0,
) -> dict:
    """
    Create a session issue to track this Claude Code session.
    Call this at the START of every session before doing any work.

    path: the current working directory (os.getcwd()). When provided, a project
          is automatically created or matched for that folder path. Each unique
          directory gets its own project, named after the folder.
    title: short description of what you're working on.
    tokens_input / tokens_output: initial token counts if known.

    Returns the created issue (including its identifier) for use in future updates.
    """
    if path:
        project = db.get_or_create_project_for_path(path)
    else:
        project = db.get_or_create_claude_project()

    issue = db.create_issue(
        title=title,
        project_id=project["id"],
        description=description,
        status="in_progress",
        priority=priority,
        assignee="claude",
        tokens_input=tokens_input,
        tokens_output=tokens_output,
    )
    from task_manager.config import SESSION_FILE
    SESSION_FILE.write_text(issue["id"])
    return issue


@mcp.tool()
def task_manager_update_session(
    progress_note: str,
    issue_id: str | None = None,
    status: str | None = None,
    tokens_input: int = 0,
    tokens_output: int = 0,
) -> dict | None:
    """
    Log a progress update to the current session issue.
    Call this at key milestones during a Claude Code session.

    progress_note: what was accomplished at this milestone.
    tokens_input / tokens_output: cumulative token counts so far (will overwrite previous).
    status: optionally change status (e.g. 'in_progress', 'done').
    """
    from task_manager.config import SESSION_FILE
    iid = issue_id
    if not iid and SESSION_FILE.exists():
        iid = SESSION_FILE.read_text().strip()
    if not iid:
        return None
    kwargs: dict = {}
    if status:
        kwargs["status"] = status
    if tokens_input:
        kwargs["tokens_input"] = tokens_input
    if tokens_output:
        kwargs["tokens_output"] = tokens_output
    if kwargs:
        db.update_issue(iid, **kwargs)
    db.add_comment(iid, progress_note, author="claude")
    return db.get_issue(iid)


@mcp.tool()
def task_manager_complete_session(
    summary: str = "",
    issue_id: str | None = None,
    tokens_input: int = 0,
    tokens_output: int = 0,
) -> dict | None:
    """
    Mark the current session issue as done.
    Call this when the Claude Code session task is fully complete.

    summary: final completion notes added as a comment.
    tokens_input / tokens_output: final cumulative token counts for the session.
    """
    from task_manager.config import SESSION_FILE
    iid = issue_id
    if not iid and SESSION_FILE.exists():
        iid = SESSION_FILE.read_text().strip()
    if not iid:
        return None
    kwargs: dict = {"status": "done"}
    if tokens_input:
        kwargs["tokens_input"] = tokens_input
    if tokens_output:
        kwargs["tokens_output"] = tokens_output
    db.update_issue(iid, **kwargs)
    if summary:
        db.add_comment(iid, summary, author="claude")
    issue = db.get_issue(iid)
    SESSION_FILE.unlink(missing_ok=True)
    return issue


@mcp.tool()
def task_manager_get_current_session() -> dict | None:
    """
    Get the current active session issue, if any.
    Returns None if no session is active.
    """
    from task_manager.config import SESSION_FILE
    if not SESSION_FILE.exists():
        return None
    iid = SESSION_FILE.read_text().strip()
    return db.get_issue(iid)
