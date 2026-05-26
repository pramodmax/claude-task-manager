# Claude Task Manager

A lightweight, local-first task manager with a Linear-inspired browser UI and native Claude Code integration via MCP.

No cloud, no sync — just a SQLite file and a local web server.

---

## Features

- **Linear-like browser UI** — dark theme, grouped issue list, Kanban board, keyboard shortcuts
- **Projects** — tasks organized by project; each unique working directory auto-creates its own project with a unique color avatar
- **Project detail** — click a project to see its filesystem path and cumulative token usage
- **File-based storage** — single SQLite database at `~/.local/share/claude-task-manager/tasks.db`
- **Claude Code MCP plugin** — exposes full CRUD as MCP tools Claude Code calls directly
- **Session auto-tracking** — Claude Code creates and updates a task for every session, organized by working directory
- **Cross-platform** — works on Mac and Linux with Python 3.11+

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        claude-task-manager                          │
│                                                                     │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐  │
│  │  Browser UI     │   │   MCP Server    │   │   CLI (click)   │  │
│  │  FastAPI +      │   │ (task-manager   │   │  session create │  │
│  │  Vanilla JS     │   │  mcp-server)    │   │  session update │  │
│  └────────┬────────┘   └────────┬────────┘   └────────┬────────┘  │
│           │                     │                     │            │
│           └─────────────────────┼─────────────────────┘            │
│                                 │                                   │
│                    ┌────────────▼────────────┐                      │
│                    │   db/database.py         │                      │
│                    │   (SQLite CRUD layer)    │                      │
│                    └────────────┬────────────┘                      │
│                                 │                                   │
│                    ┌────────────▼────────────┐                      │
│                    │  ~/.local/share/         │                      │
│                    │  claude-task-manager/    │                      │
│                    │  ├── tasks.db            │                      │
│                    │  └── current_session.txt │                      │
│                    └─────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────┘

                           ┌──────────────────┐
                           │   Claude Code    │
                           │  (claude CLI)    │
                           │                  │
                           │  MCP client ─────┼──► task-manager mcp-server
                           │  Stop hook  ─────┼──► task-manager session complete
                           └──────────────────┘
```

### Data model

```
Project  1──*  Issue  1──*  Comment
Project  1──*  Label
Issue    *──*  Label
```

**Issue statuses**: `backlog → todo → in_progress → done | cancelled`  
**Priorities**: `urgent | high | medium | low | no_priority`

---

## Installation

### Prerequisites

- Python 3.11 or later
- `uv` (recommended) or `pip`

### Mac

```bash
# Install uv if you don't have it
brew install uv

# Clone and install
git clone https://github.com/yourname/claude-task-manager
cd claude-task-manager
uv pip install -e .

# Verify
task-manager --help
```

### Linux

```bash
# Install uv
curl -Lsf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/yourname/claude-task-manager
cd claude-task-manager
uv pip install -e .

# Verify
task-manager --help
```

> **Note (external drive / cross-device):** If the project is on an external drive and uv warns about cross-device links, add `export UV_LINK_MODE=copy` to your shell profile before installing.

> **Note (Linux PATH):** Ensure `~/.local/bin` is in your `$PATH` if using uv's isolated installs.

---

## Usage

### Starting the UI

```bash
task-manager          # opens browser UI at http://localhost:7654
task-manager tui      # same, explicit command

# Custom port
task-manager tui --port 8080

# Headless (no browser auto-open)
task-manager tui --no-browser
```

The UI is served at `http://localhost:7654` by default. It opens automatically in your default browser.

### Stopping the task manager

Press `Ctrl+C` in the terminal where `task-manager` is running. The SQLite database is safely flushed before exit (WAL mode).

To run in the background and stop later:

```bash
# Start in background
task-manager tui --no-browser &
echo $! > /tmp/task-manager.pid

# Stop it
kill $(cat /tmp/task-manager.pid)
```

### Restarting

Simply stop and start again — the database persists across restarts.

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `n` | New issue |
| `p` | New project |
| `b` | Toggle board / list view |
| `/` | Focus search |
| `r` | Refresh all data |
| `Esc` | Close modal |

### Views

**List view** — issues grouped by status (In Progress → Todo → Backlog → Done → Cancelled). Click a group header to collapse/expand.

**Board view** — Kanban columns per status. Press `b` or click "Board" to toggle.

**Project view** — click any project in the sidebar to see:
- Colored letter avatar (deterministic, based on project name)
- Full filesystem path (if auto-created from a Claude Code session)
- Token usage to date (input + output tokens summed across all sessions in the project)
- Issue list filtered to that project

### CLI

```bash
# List issues
task-manager list
task-manager list --project "Engineering" --status in_progress

# Session tracking (usually called by hooks or Claude Code itself)
task-manager session create "Fix login bug"
task-manager session update "Root cause found: token expiry not handled"
task-manager session complete --summary "Fix shipped, tests green"
task-manager session current
```

---

## Docker

### Quick start with Docker Compose

```bash
git clone https://github.com/yourname/claude-task-manager
cd claude-task-manager
docker compose up -d
```

The UI is available at `http://localhost:7654`. Data is stored in a named Docker volume (`task-manager-data`) so it persists across container restarts.

### Stop and restart

```bash
docker compose stop       # stop without removing data
docker compose start      # restart

docker compose down       # stop and remove containers (data volume kept)
docker compose down -v    # stop and DELETE all data
```

### Build manually

```bash
docker build -t task-manager .
docker run -d \
  -p 7654:7654 \
  -v task-manager-data:/data \
  --name task-manager \
  task-manager
```

### Custom port

Edit `docker-compose.yml` and change `"7654:7654"` to `"YOUR_PORT:7654"`.

---

## Claude Code Integration

There are four steps to wire Claude Code up to this task manager so every session is automatically tracked.

### Step 1 — Install the task manager

Follow the [Installation](#installation) steps above, then verify:

```bash
task-manager --help
```

### Step 2 — Register the MCP server globally

Use the `claude mcp add` command with `--scope user` to register it once for all projects on your machine:

```bash
claude mcp add --scope user task-manager task-manager mcp-server
```

This writes to `~/.claude.json` — the file Claude Code CLI actually uses for user-scope MCP servers. Verify it worked:

```bash
claude mcp list
# task-manager: task-manager mcp-server - ✓ Connected
```

> **Note:** Do not add `mcpServers` to `~/.claude/settings.json` — Claude Code CLI does not read MCP servers from that file. The `claude mcp add` command is the correct way.

### Step 3 — Add the Stop hook

The Stop hook automatically marks a session complete when you exit Claude Code. Add it to `~/.claude/settings.json` (keep any existing keys alongside):

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "task-manager session complete --summary 'Session ended'"
          }
        ]
      }
    ]
  }
}
```

### Step 4 — Tell Claude to use it (global CLAUDE.md)

Claude reads `~/.claude/CLAUDE.md` at the start of every session. Without instructions here, Claude has no way of knowing it should call the task manager tools.

Add the following to `~/.claude/CLAUDE.md` (keep any existing content — just append):

```markdown
## Task tracking

A task manager MCP server (`task-manager`) is available in every session.

At the start of EVERY session call:
  task_manager_create_session(title="<short description of the task>", path=os.getcwd())

At key milestones call:
  task_manager_update_session(progress_note="<what was accomplished>", tokens_input=N, tokens_output=N)

At the end call:
  task_manager_complete_session(summary="<what was done>", tokens_input=N, tokens_output=N)
```

### Step 5 — Start the UI and verify

Open two terminals:

```bash
# Terminal 1 — keep the UI running
task-manager

# Terminal 2 — start a Claude Code session in any project
cd ~/your-project
claude
```

Claude will call `task_manager_create_session` automatically. Open `http://localhost:7654` — you should see a new project named after your folder with the session listed under it.

---

### Key file locations

| File | Purpose |
|------|---------|
| `~/.claude.json` | Global MCP server registrations (written by `claude mcp add --scope user`) |
| `~/.claude/settings.json` | Global hooks (Stop hook) |
| `~/.claude/CLAUDE.md` | Instructions Claude reads at the start of every session |
| `.mcp.json` *(per-project)* | Project-scoped MCP servers |

---

### Available MCP tools

| Tool | Description |
|------|-------------|
| `task_manager_create_session(title, path?, description?, priority?, tokens_input?, tokens_output?)` | Start a tracked session; `path` auto-creates a project for the working directory |
| `task_manager_update_session(progress_note, issue_id?, status?, tokens_input?, tokens_output?)` | Log a milestone and optionally update token counts |
| `task_manager_complete_session(summary?, issue_id?, tokens_input?, tokens_output?)` | Mark session done with final token counts |
| `task_manager_get_current_session()` | Get the active session issue |
| `task_manager_list_projects()` | List all projects |
| `task_manager_create_project(name, description?, color?, identifier?)` | Create a project |
| `task_manager_list_issues(project_id?, status?, priority?, search?, assignee?)` | List issues |
| `task_manager_get_issue(issue_id)` | Get issue by UUID or identifier (e.g. `ENG-5`) |
| `task_manager_create_issue(title, project_id, ...)` | Create an issue |
| `task_manager_update_issue(issue_id, ...)` | Update issue fields |
| `task_manager_delete_issue(issue_id)` | Delete an issue |
| `task_manager_add_comment(issue_id, body, author?)` | Add a comment |
| `task_manager_list_comments(issue_id)` | List comments |
| `task_manager_create_label(name, color?, project_id?)` | Create a label |
| `task_manager_list_labels(project_id?)` | List labels |

### How session tracking works

1. **Session start** — Claude calls `task_manager_create_session(title="…", path=os.getcwd())`. A project is auto-created (or matched) for the working directory — named after the folder with a deterministic color. A new issue is created in that project with status `in_progress` and assignee `claude`.

2. **Progress** — `task_manager_update_session("Milestone note")` appends a comment to the session issue and optionally updates cumulative token counts.

3. **Session end** — Claude calls `task_manager_complete_session(summary="…")`, or the Stop hook fires `task-manager session complete` automatically on exit.

Each unique working directory gets its own project. Clicking that project in the UI shows the folder path and cumulative token usage across all sessions run in it.

---

## Upgrading

To get the latest changes after pulling an update:

```bash
cd claude-task-manager
git pull

# Reinstall the tool so the new UI and code are picked up
uv tool install --reinstall .
```

Then restart the task manager and hard-refresh the browser:

```bash
# Stop the running instance (Ctrl+C), then:
task-manager

# In the browser:
# Mac:   Cmd+Shift+R
# Linux: Ctrl+Shift+R
```

> **Why reinstall?** `uv tool install` copies files at install time. Pulling new code or editing source files has no effect until you reinstall — the running server continues to serve the old copied files.

---

## Uninstall

```bash
# Remove the CLI tool
pip uninstall claude-task-manager       # if installed with pip
# or just remove the clone if you used `uv pip install -e .`

# Remove all data (issues, projects, comments)
rm -rf ~/.local/share/claude-task-manager

# Remove MCP config (if added to project settings)
# Edit .claude/settings.json and remove the task-manager entries
```

For Docker:

```bash
docker compose down -v   # stops containers and deletes the data volume
docker rmi task-manager  # remove the image
```

---

## Data location

| Platform | Path |
|----------|------|
| Linux / Mac | `~/.local/share/claude-task-manager/tasks.db` |
| Docker | `/data/claude-task-manager/tasks.db` (inside the volume) |
| Custom | Set `XDG_DATA_HOME` env var |

To back up or migrate: copy the `tasks.db` file.

---

## Development

```bash
# Install in editable mode
uv pip install -e .

# Run the web UI
task-manager tui

# Run the MCP server (stdio, for testing)
task-manager mcp-server
```

Dependencies: `fastapi`, `uvicorn`, `mcp[cli]`, `click` — all pure Python, no native extensions.
