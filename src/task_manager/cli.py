import json
import sys

import click

from task_manager.db import database as db
from task_manager.db.database import init_db


def _extract_tokens_from_transcript(transcript_path: str) -> tuple[int, int]:
    """Sum input/output token usage from a Claude Code transcript JSONL file."""
    if not transcript_path:
        return 0, 0
    try:
        from pathlib import Path
        total_input = total_output = 0
        for line in Path(transcript_path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            usage = event.get("message", {}).get("usage", {})
            total_input += usage.get("input_tokens", 0)
            total_output += usage.get("output_tokens", 0)
        return total_input, total_output
    except Exception:
        return 0, 0


@click.group(invoke_without_command=True)
@click.version_option(package_name="claude-task-manager", prog_name="task-manager")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Claude Task Manager — Linear-like task management for your local machine."""
    if ctx.invoked_subcommand is None:
        _launch_web()


@main.command()
@click.option("--port", default=7654, show_default=True, help="HTTP port")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically")
def tui(port: int, no_browser: bool) -> None:
    """Launch the browser-based UI (local web server)."""
    _launch_web(port=port, open_browser=not no_browser)


def _launch_web(port: int = 7654, open_browser: bool = True) -> None:
    import threading
    import webbrowser
    import uvicorn
    init_db()
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    click.echo(f"Task Manager running at http://localhost:{port}  (Ctrl+C to stop)")
    from task_manager.web.server import app
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")


@main.command("mcp-server")
def mcp_server_cmd() -> None:
    """Start the MCP server for Claude Code integration (stdio transport)."""
    init_db()
    from task_manager.mcp_server.server import mcp
    mcp.run()


# ── Session commands (used by Claude Code hooks) ──────────────────────────────

@main.group()
def session() -> None:
    """Manage Claude Code session tracking."""


@session.command("create")
@click.argument("title")
@click.option("--description", "-d", default="", help="Session description")
def session_create(title: str, description: str) -> None:
    """Create a new tracked session issue in the Claude Code project."""
    init_db()
    project = db.get_or_create_claude_project()
    issue = db.create_issue(
        title=title,
        project_id=project["id"],
        description=description,
        status="in_progress",
        priority="medium",
        assignee="claude",
    )
    from task_manager.config import SESSION_FILE
    SESSION_FILE.write_text(issue["id"])
    click.echo(json.dumps({"id": issue["id"], "identifier": issue["identifier"], "title": issue["title"]}))


@session.command("update")
@click.argument("message")
@click.option("--status", default=None, help="New status")
def session_update(message: str, status: str | None) -> None:
    """Add a progress comment to the current session issue."""
    init_db()
    from task_manager.config import SESSION_FILE
    if not SESSION_FILE.exists():
        click.echo("No active session", err=True)
        sys.exit(1)
    issue_id = SESSION_FILE.read_text().strip()
    kwargs = {}
    if status:
        kwargs["status"] = status
    if kwargs:
        db.update_issue(issue_id, **kwargs)
    comment = db.add_comment(issue_id, message, author="claude")
    click.echo(json.dumps({"comment_id": comment["id"]}))


@session.command("complete")
@click.option("--summary", "-s", default="", help="Completion summary")
@click.option("--tokens-input", type=int, default=0, help="Total input tokens used")
@click.option("--tokens-output", type=int, default=0, help="Total output tokens used")
@click.option("--from-hook", is_flag=True, help="Read Claude Code Stop hook JSON from stdin and auto-extract token counts")
def session_complete(summary: str, tokens_input: int, tokens_output: int, from_hook: bool) -> None:
    """Mark the current session issue as done."""
    init_db()
    if from_hook:
        try:
            hook_data = json.load(sys.stdin)
            transcript_path = hook_data.get("transcript_path", "")
            tokens_input, tokens_output = _extract_tokens_from_transcript(transcript_path)
        except Exception:
            pass
    from task_manager.config import SESSION_FILE
    if not SESSION_FILE.exists():
        sys.exit(0)
    issue_id = SESSION_FILE.read_text().strip()
    if summary:
        db.add_comment(issue_id, summary, author="claude")
    kwargs: dict = {"status": "done"}
    if tokens_input:
        kwargs["tokens_input"] = tokens_input
    if tokens_output:
        kwargs["tokens_output"] = tokens_output
    db.update_issue(issue_id, **kwargs)
    SESSION_FILE.unlink(missing_ok=True)
    click.echo(f"Session {issue_id} marked complete (in={tokens_input} out={tokens_output})")


@session.command("current")
def session_current() -> None:
    """Show the current active session issue."""
    init_db()
    from task_manager.config import SESSION_FILE
    if not SESSION_FILE.exists():
        click.echo("No active session")
        sys.exit(0)
    issue_id = SESSION_FILE.read_text().strip()
    issue = db.get_issue(issue_id)
    if issue:
        click.echo(json.dumps(issue))
    else:
        click.echo("Session issue not found", err=True)


# ── Quick issue commands ───────────────────────────────────────────────────────

@main.command("list")
@click.option("--project", "-p", default=None, help="Filter by project name or ID")
@click.option("--status", "-s", default=None, help="Filter by status")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def list_issues(project: str | None, status: str | None, as_json: bool) -> None:
    """List issues."""
    init_db()
    project_id = None
    if project:
        proj = db.get_project_by_name(project) or db.get_project(project)
        if proj:
            project_id = proj["id"]
    issues = db.list_issues(project_id=project_id, status=status)
    if as_json:
        click.echo(json.dumps(issues))
    else:
        for issue in issues:
            click.echo(
                f"{issue['identifier']:10} [{issue['status']:12}] [{issue['priority']:11}] {issue['title']}"
            )
