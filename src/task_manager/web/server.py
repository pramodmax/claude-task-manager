from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from task_manager.db import database as db

app = FastAPI(title="Task Manager", docs_url=None, redoc_url=None)

_static = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static)), name="static")


@app.get("/")
def index():
    return FileResponse(str(_static / "index.html"))


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectIn(BaseModel):
    name: str
    description: str = ""
    color: str = "#6366f1"
    identifier: str = ""
    path: str = ""


@app.get("/api/projects")
def list_projects():
    return db.list_projects()


@app.get("/api/projects/{project_id}/stats")
def project_stats(project_id: str):
    stats = db.get_project_stats(project_id)
    if not stats["project"]:
        raise HTTPException(404, "Project not found")
    return stats


@app.post("/api/projects", status_code=201)
def create_project(body: ProjectIn):
    return db.create_project(**body.model_dump())


@app.put("/api/projects/{project_id}")
def update_project(project_id: str, body: ProjectIn):
    result = db.update_project(project_id, **body.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(404, "Project not found")
    return result


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: str):
    if not db.delete_project(project_id):
        raise HTTPException(404, "Project not found")


# ── Issues ────────────────────────────────────────────────────────────────────

class IssueIn(BaseModel):
    title: str
    project_id: str
    description: str = ""
    status: str = "backlog"
    priority: str = "medium"
    assignee: str = ""
    due_date: str = ""
    estimate: int = 0
    tokens_input: int = 0
    tokens_output: int = 0


class IssueUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    due_date: str | None = None
    estimate: int | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None


@app.get("/api/issues")
def list_issues(
    project_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    assignee: str | None = None,
    search: str | None = None,
):
    return db.list_issues(
        project_id=project_id,
        status=status,
        priority=priority,
        assignee=assignee,
        search=search,
    )


@app.get("/api/issues/{issue_id}")
def get_issue(issue_id: str):
    issue = db.get_issue(issue_id)
    if not issue:
        raise HTTPException(404, "Issue not found")
    return issue


@app.post("/api/issues", status_code=201)
def create_issue(body: IssueIn):
    try:
        return db.create_issue(**body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.put("/api/issues/{issue_id}")
def update_issue(issue_id: str, body: IssueUpdate):
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    result = db.update_issue(issue_id, **kwargs)
    if not result:
        raise HTTPException(404, "Issue not found")
    return result


@app.delete("/api/issues/{issue_id}", status_code=204)
def delete_issue(issue_id: str):
    if not db.delete_issue(issue_id):
        raise HTTPException(404, "Issue not found")


# ── Comments ──────────────────────────────────────────────────────────────────

class CommentIn(BaseModel):
    body: str
    author: str = "me"


@app.get("/api/issues/{issue_id}/comments")
def list_comments(issue_id: str):
    return db.list_comments(issue_id)


@app.post("/api/issues/{issue_id}/comments", status_code=201)
def add_comment(issue_id: str, body: CommentIn):
    return db.add_comment(issue_id, body.body, body.author)


@app.delete("/api/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: str):
    db.delete_comment(comment_id)


# ── Labels ────────────────────────────────────────────────────────────────────

class LabelIn(BaseModel):
    name: str
    color: str = "#6366f1"
    project_id: str | None = None


@app.get("/api/labels")
def list_labels(project_id: str | None = None):
    return db.list_labels(project_id=project_id)


@app.post("/api/labels", status_code=201)
def create_label(body: LabelIn):
    return db.create_label(**body.model_dump())


# ── Meta ──────────────────────────────────────────────────────────────────────

@app.get("/api/meta")
def meta():
    return {
        "statuses": db.STATUSES,
        "status_labels": db.STATUS_LABELS,
        "status_icons": db.STATUS_ICONS,
        "priorities": db.PRIORITIES,
        "priority_labels": db.PRIORITY_LABELS,
        "priority_icons": db.PRIORITY_ICONS,
    }
