/* ── State ───────────────────────────────────────────────────────────────── */
const state = {
  projects: [],
  issues: [],
  meta: {},
  currentProjectId: null,
  navFilter: 'all',
  viewMode: 'list',
  search: '',
  collapsedGroups: new Set(),
};

/* ── API ─────────────────────────────────────────────────────────────────── */
const api = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(await r.text());
    return r.status === 204 ? null : r.json();
  },
  async put(path, body) {
    const r = await fetch(path, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async delete(path) {
    const r = await fetch(path, { method: 'DELETE' });
    if (!r.ok) throw new Error(await r.text());
  },
};

/* ── Toast ───────────────────────────────────────────────────────────────── */
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

/* ── Modal helpers ───────────────────────────────────────────────────────── */
function showModal(html) {
  closeModal();
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'modal-overlay';
  overlay.innerHTML = html;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
  document.addEventListener('keydown', onEsc);
  const first = overlay.querySelector('input, textarea, select');
  if (first) setTimeout(() => first.focus(), 50);
  return overlay;
}

function closeModal() {
  document.getElementById('modal-overlay')?.remove();
  document.removeEventListener('keydown', onEsc);
}

function onEsc(e) { if (e.key === 'Escape') closeModal(); }

/* ── Helpers ─────────────────────────────────────────────────────────────── */
const STATUS_ORDER = ['in_progress', 'todo', 'backlog', 'done', 'cancelled'];

const STATUS_ICONS = { backlog: '○', todo: '◎', in_progress: '◕', done: '✓', cancelled: '✗' };
const PRIORITY_ICONS = { urgent: '↑↑', high: '↑', medium: '→', low: '↓', no_priority: '—' };
const STATUS_LABELS = { backlog: 'Backlog', todo: 'Todo', in_progress: 'In Progress', done: 'Done', cancelled: 'Cancelled' };
const PRIORITY_LABELS = { urgent: 'Urgent', high: 'High', medium: 'Medium', low: 'Low', no_priority: 'No Priority' };

const PROJECT_COLORS = ['#5e6ad2','#6366f1','#0ea5e9','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899'];

function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDate(s) {
  if (!s) return '';
  return s.slice(0, 10);
}

function projectById(id) { return state.projects.find(p => p.id === id); }

function projectAvatarHtml(p, cls = 'project-avatar') {
  const letter = (p.name || '?')[0].toUpperCase();
  return `<div class="${cls}" style="background:${escHtml(p.color)}">${letter}</div>`;
}

function fmtTokens(n) {
  if (!n) return '0';
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return String(n);
}

/* ── Sidebar rendering ───────────────────────────────────────────────────── */
function renderSidebar() {
  const list = document.getElementById('project-list');
  list.innerHTML = state.projects.map(p => `
    <div class="nav-item ${state.currentProjectId === p.id ? 'active' : ''}" data-project="${p.id}">
      ${projectAvatarHtml(p)}
      <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(p.name)}</span>
    </div>
  `).join('');

  list.querySelectorAll('[data-project]').forEach(el => {
    el.addEventListener('click', () => {
      state.currentProjectId = el.dataset.project;
      state.navFilter = 'all';
      refreshIssues();
      updateSidebarActive();
      updateViewTitle();
      renderProjectHeader();
    });
  });

  document.querySelectorAll('[data-nav]').forEach(el => {
    el.classList.toggle('active', !state.currentProjectId && el.dataset.nav === state.navFilter);
  });
}

function updateSidebarActive() {
  document.querySelectorAll('[data-project]').forEach(el => {
    el.classList.toggle('active', el.dataset.project === state.currentProjectId);
  });
  document.querySelectorAll('[data-nav]').forEach(el => {
    el.classList.toggle('active', !state.currentProjectId && el.dataset.nav === state.navFilter);
  });
}

function updateViewTitle() {
  let title = 'All Issues';
  if (state.navFilter === 'mine') title = 'My Issues';
  else if (state.navFilter === 'backlog') title = 'Backlog';
  else if (state.currentProjectId) {
    const p = projectById(state.currentProjectId);
    title = p ? p.name : 'Issues';
  }
  document.getElementById('view-title').textContent = title;
}

/* ── Project header ──────────────────────────────────────────────────────── */
async function renderProjectHeader() {
  const header = document.getElementById('project-header');
  if (!state.currentProjectId) {
    header.classList.add('hidden');
    header.innerHTML = '';
    return;
  }
  const p = projectById(state.currentProjectId);
  if (!p) { header.classList.add('hidden'); return; }

  header.classList.remove('hidden');
  try {
    const stats = await api.get(`/api/projects/${state.currentProjectId}/stats`);
    const pathHtml = p.path
      ? `<span class="project-detail-path-value">${escHtml(p.path)}</span>`
      : `<span class="path-missing">Not recorded — Claude should pass path=os.getcwd() when starting a session</span>`;
    header.innerHTML = `
      <div class="project-detail-card">
        <div class="project-detail-title-row">
          ${projectAvatarHtml(p, 'project-header-avatar')}
          <span class="project-detail-name">${escHtml(p.name)}</span>
          <button class="btn-secondary" id="ph-edit" style="margin-left:auto">Edit</button>
          <button class="btn-danger" id="ph-delete">Delete</button>
        </div>
        <div class="project-detail-row">
          <span class="project-detail-label">Folder</span>
          ${pathHtml}
        </div>
        <div class="project-detail-stats">
          <div class="project-stat-card">
            <span class="project-stat-value">${stats.total_issues}</span>
            <span class="project-stat-label">Total Issues</span>
          </div>
          <div class="project-stat-card">
            <span class="project-stat-value">${stats.open_issues}</span>
            <span class="project-stat-label">Open</span>
          </div>
          <div class="project-stat-card">
            <span class="project-stat-value">${fmtTokens(stats.tokens_input)}</span>
            <span class="project-stat-label">Tokens In</span>
          </div>
          <div class="project-stat-card">
            <span class="project-stat-value">${fmtTokens(stats.tokens_output)}</span>
            <span class="project-stat-label">Tokens Out</span>
          </div>
        </div>
      </div>`;
    header.querySelector('#ph-edit').onclick = () => openProjectForm(p);
    header.querySelector('#ph-delete').onclick = () => confirmDeleteProject(p);
  } catch {
    header.classList.add('hidden');
  }
}

/* ── Issue list rendering ────────────────────────────────────────────────── */
function renderIssueList() {
  const el = document.getElementById('issue-list-view');
  const issues = state.issues;

  if (!issues.length) {
    el.innerHTML = `<div class="empty-state">
      <div class="empty-icon">≡</div>
      <p>No issues found</p>
      <small>Press <kbd>N</kbd> or click "+ New Issue" to create one</small>
    </div>`;
    return;
  }

  const groups = {};
  for (const issue of issues) {
    (groups[issue.status] = groups[issue.status] || []).push(issue);
  }

  el.innerHTML = STATUS_ORDER
    .filter(s => groups[s])
    .map(status => {
      const grpIssues = groups[status];
      const collapsed = state.collapsedGroups.has(status);
      const icon = STATUS_ICONS[status] || '○';
      const label = STATUS_LABELS[status] || status;
      return `
        <div class="issue-group">
          <div class="group-header" data-group="${status}">
            <span class="group-arrow ${collapsed ? 'collapsed' : ''}">▼</span>
            <span class="group-status-icon status-${status}">${icon}</span>
            <span class="group-label">${label}</span>
            <span class="group-count">${grpIssues.length}</span>
          </div>
          <div class="issue-rows" ${collapsed ? 'style="display:none"' : ''}>
            ${grpIssues.map(issue => issueRowHtml(issue)).join('')}
          </div>
        </div>`;
    }).join('');

  el.querySelectorAll('.group-header').forEach(h => {
    h.addEventListener('click', () => {
      const s = h.dataset.group;
      state.collapsedGroups.has(s) ? state.collapsedGroups.delete(s) : state.collapsedGroups.add(s);
      renderIssueList();
    });
  });

  el.querySelectorAll('.issue-row').forEach(row => {
    row.addEventListener('click', () => openIssueDetail(row.dataset.id));
  });
}

function issueRowHtml(issue) {
  const sIcon = STATUS_ICONS[issue.status] || '○';
  const pIcon = PRIORITY_ICONS[issue.priority] || '→';
  return `
    <div class="issue-row" data-id="${escHtml(issue.id)}">
      <span class="row-status-icon status-${issue.status}">${sIcon}</span>
      <span class="row-identifier monospace">${escHtml(issue.identifier)}</span>
      <span class="row-title ${issue.status === 'cancelled' ? 'status-cancelled' : ''}">${escHtml(issue.title)}</span>
      <span class="row-priority priority-${issue.priority}">${pIcon}</span>
      <span class="row-assignee">${escHtml(issue.assignee || '')}</span>
      <span class="row-due">${fmtDate(issue.due_date)}</span>
    </div>`;
}

/* ── Board rendering ─────────────────────────────────────────────────────── */
function renderBoard() {
  const el = document.getElementById('board-view');
  const grouped = {};
  for (const issue of state.issues) {
    (grouped[issue.status] = grouped[issue.status] || []).push(issue);
  }

  el.innerHTML = STATUS_ORDER.map(status => {
    const cards = (grouped[status] || []);
    const icon = STATUS_ICONS[status] || '○';
    const label = STATUS_LABELS[status] || status;
    return `
      <div class="board-col">
        <div class="board-col-header">
          <span class="status-${status}">${icon}</span>
          <span>${label}</span>
          <span class="board-col-count">${cards.length}</span>
        </div>
        <div class="board-cards">
          ${cards.map(issue => `
            <div class="board-card" data-id="${escHtml(issue.id)}">
              <div class="card-identifier">${escHtml(issue.identifier)}</div>
              <div class="card-title">${escHtml(issue.title)}</div>
              <div class="card-meta">
                <span class="card-priority priority-${issue.priority}">${PRIORITY_ICONS[issue.priority] || '→'}</span>
                ${issue.assignee ? `<span>${escHtml(issue.assignee)}</span>` : ''}
                ${issue.due_date ? `<span>${fmtDate(issue.due_date)}</span>` : ''}
              </div>
            </div>`).join('')}
        </div>
      </div>`;
  }).join('');

  el.querySelectorAll('.board-card').forEach(card => {
    card.addEventListener('click', () => openIssueDetail(card.dataset.id));
  });
}

/* ── Issue detail modal ──────────────────────────────────────────────────── */
async function openIssueDetail(issueId) {
  const issue = state.issues.find(i => i.id === issueId) || await api.get(`/api/issues/${issueId}`);
  const comments = await api.get(`/api/issues/${issueId}/comments`);
  const proj = projectById(issue.project_id);

  const overlay = showModal(`
    <div class="modal modal-wide">
      <div class="modal-header">
        <div>
          <span class="detail-identifier">${escHtml(issue.identifier)}</span>
        </div>
        <div class="header-actions" style="margin-left:auto;display:flex;gap:8px">
          <button class="btn-secondary" id="d-edit">Edit</button>
          <button class="btn-danger" id="d-delete">Delete</button>
        </div>
        <button class="modal-close" id="d-close">×</button>
      </div>
      <div class="modal-body">
        <h2 style="font-size:18px;font-weight:600;margin-bottom:12px">${escHtml(issue.title)}</h2>

        <div class="detail-meta-grid">
          <div class="detail-meta-item">
            <span class="detail-meta-label">Status</span>
            <span class="detail-meta-val status-${issue.status}">${STATUS_ICONS[issue.status]} ${STATUS_LABELS[issue.status] || issue.status}</span>
          </div>
          <div class="detail-meta-item">
            <span class="detail-meta-label">Priority</span>
            <span class="detail-meta-val priority-${issue.priority}">${PRIORITY_ICONS[issue.priority]} ${PRIORITY_LABELS[issue.priority] || issue.priority}</span>
          </div>
          <div class="detail-meta-item">
            <span class="detail-meta-label">Project</span>
            <span class="detail-meta-val">${escHtml(proj ? proj.name : '—')}</span>
          </div>
          <div class="detail-meta-item">
            <span class="detail-meta-label">Assignee</span>
            <span class="detail-meta-val">${escHtml(issue.assignee || '—')}</span>
          </div>
          <div class="detail-meta-item">
            <span class="detail-meta-label">Due Date</span>
            <span class="detail-meta-val">${fmtDate(issue.due_date) || '—'}</span>
          </div>
          <div class="detail-meta-item">
            <span class="detail-meta-label">Estimate</span>
            <span class="detail-meta-val">${issue.estimate ? issue.estimate + ' pts' : '—'}</span>
          </div>
          <div class="detail-meta-item">
            <span class="detail-meta-label">Created</span>
            <span class="detail-meta-val">${fmtDate(issue.created_at)}</span>
          </div>
          <div class="detail-meta-item">
            <span class="detail-meta-label">Updated</span>
            <span class="detail-meta-val">${fmtDate(issue.updated_at)}</span>
          </div>
        </div>

        ${issue.description ? `
          <div class="detail-section">
            <div class="detail-section-title">Description</div>
            <div class="detail-description">${escHtml(issue.description)}</div>
          </div>` : ''}

        <div class="detail-section">
          <div class="detail-section-title">Comments (${comments.length})</div>
          <div class="comment-list" id="comment-list">
            ${comments.map(c => `
              <div class="comment-item">
                <div class="comment-meta">
                  <span class="comment-author">${escHtml(c.author)}</span>
                  <span class="comment-date">${fmtDate(c.created_at)}</span>
                </div>
                <div class="comment-body">${escHtml(c.body)}</div>
              </div>`).join('')}
          </div>
          <div class="comment-form" style="margin-top:10px">
            <input class="comment-input" id="comment-input" placeholder="Add a comment…">
            <button class="btn-comment" id="comment-submit">Post</button>
          </div>
        </div>
      </div>
    </div>`);

  overlay.querySelector('#d-close').onclick = closeModal;
  overlay.querySelector('#d-edit').onclick = () => { closeModal(); openIssueForm(issue); };
  overlay.querySelector('#d-delete').onclick = () => confirmDelete(issue);

  const commentInput = overlay.querySelector('#comment-input');
  const submitComment = async () => {
    const body = commentInput.value.trim();
    if (!body) return;
    try {
      await api.post(`/api/issues/${issue.id}/comments`, { body, author: 'me' });
      commentInput.value = '';
      const comments2 = await api.get(`/api/issues/${issue.id}/comments`);
      overlay.querySelector('#comment-list').innerHTML = comments2.map(c => `
        <div class="comment-item">
          <div class="comment-meta">
            <span class="comment-author">${escHtml(c.author)}</span>
            <span class="comment-date">${fmtDate(c.created_at)}</span>
          </div>
          <div class="comment-body">${escHtml(c.body)}</div>
        </div>`).join('');
    } catch (e) { toast('Failed to post comment', 'error'); }
  };
  overlay.querySelector('#comment-submit').onclick = submitComment;
  commentInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitComment(); } });
}

/* ── Confirm delete ──────────────────────────────────────────────────────── */
function confirmDelete(issue) {
  showModal(`
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">Delete Issue</span>
        <button class="modal-close" id="c-close">×</button>
      </div>
      <div class="modal-body">
        <p class="confirm-msg">Delete <strong>${escHtml(issue.identifier)}</strong> — "${escHtml(issue.title)}"?<br>This cannot be undone.</p>
      </div>
      <div class="modal-footer">
        <button class="btn-cancel" id="c-cancel">Cancel</button>
        <button class="btn-danger" id="c-confirm">Delete</button>
      </div>
    </div>`);
  document.getElementById('c-close').onclick = closeModal;
  document.getElementById('c-cancel').onclick = closeModal;
  document.getElementById('c-confirm').onclick = async () => {
    try {
      await api.delete(`/api/issues/${issue.id}`);
      toast(`Deleted ${issue.identifier}`, 'info');
      closeModal();
      await refreshIssues();
    } catch (e) { toast('Delete failed', 'error'); }
  };
}

/* ── Issue form modal ────────────────────────────────────────────────────── */
function openIssueForm(issue = null) {
  const isEdit = !!issue;
  const statuses = ['backlog','todo','in_progress','done','cancelled'];
  const priorities = ['urgent','high','medium','low','no_priority'];

  const statusOpts = statuses.map(s =>
    `<option value="${s}" ${issue?.status === s || (!issue && s === 'backlog') ? 'selected' : ''}>${STATUS_LABELS[s]}</option>`
  ).join('');
  const priorityOpts = priorities.map(p =>
    `<option value="${p}" ${issue?.priority === p || (!issue && p === 'medium') ? 'selected' : ''}>${PRIORITY_LABELS[p]}</option>`
  ).join('');
  const projectOpts = state.projects.map(p =>
    `<option value="${p.id}" ${issue?.project_id === p.id || state.currentProjectId === p.id ? 'selected' : ''}>${escHtml(p.name)}</option>`
  ).join('');

  if (!state.projects.length) { toast('Create a project first', 'error'); return; }

  showModal(`
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">${isEdit ? 'Edit Issue' : 'New Issue'}</span>
        <button class="modal-close" id="if-close">×</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label class="form-label">Title *</label>
          <input class="form-input" id="if-title" value="${escHtml(issue?.title || '')}" placeholder="Issue title…">
        </div>
        <div class="form-group">
          <label class="form-label">Description</label>
          <textarea class="form-textarea" id="if-desc" placeholder="Add a description…">${escHtml(issue?.description || '')}</textarea>
        </div>
        <div class="form-row form-group">
          <div>
            <label class="form-label">Status</label>
            <select class="form-select" id="if-status">${statusOpts}</select>
          </div>
          <div>
            <label class="form-label">Priority</label>
            <select class="form-select" id="if-priority">${priorityOpts}</select>
          </div>
          <div>
            <label class="form-label">Project *</label>
            <select class="form-select" id="if-project">${projectOpts}</select>
          </div>
        </div>
        <div class="form-row-2 form-group">
          <div>
            <label class="form-label">Assignee</label>
            <input class="form-input" id="if-assignee" value="${escHtml(issue?.assignee || '')}" placeholder="@username">
          </div>
          <div>
            <label class="form-label">Due Date</label>
            <input class="form-input" id="if-due" type="date" value="${escHtml(issue?.due_date || '')}">
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Estimate (story points)</label>
          <input class="form-input" id="if-estimate" type="number" min="0" value="${issue?.estimate || ''}" placeholder="0" style="width:100px">
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-cancel" id="if-cancel">Cancel</button>
        <button class="btn-save" id="if-save">${isEdit ? 'Save Changes' : 'Create Issue'}</button>
      </div>
    </div>`);

  document.getElementById('if-close').onclick = closeModal;
  document.getElementById('if-cancel').onclick = closeModal;
  document.getElementById('if-save').onclick = async () => {
    const title = document.getElementById('if-title').value.trim();
    if (!title) { toast('Title is required', 'error'); return; }
    const body = {
      title,
      description: document.getElementById('if-desc').value,
      status: document.getElementById('if-status').value,
      priority: document.getElementById('if-priority').value,
      project_id: document.getElementById('if-project').value,
      assignee: document.getElementById('if-assignee').value.trim(),
      due_date: document.getElementById('if-due').value,
      estimate: parseInt(document.getElementById('if-estimate').value) || 0,
    };
    try {
      if (isEdit) {
        await api.put(`/api/issues/${issue.id}`, body);
        toast(`Updated ${issue.identifier}`, 'success');
      } else {
        const created = await api.post('/api/issues', body);
        toast(`Created ${created.identifier}`, 'success');
      }
      closeModal();
      await refreshIssues();
    } catch (e) { toast('Save failed: ' + e.message, 'error'); }
  };
}

/* ── Confirm delete project ──────────────────────────────────────────────── */
function confirmDeleteProject(project) {
  showModal(`
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">Delete Project</span>
        <button class="modal-close" id="cdp-close">×</button>
      </div>
      <div class="modal-body">
        <p class="confirm-msg">Delete project <strong>${escHtml(project.name)}</strong>?<br>
        This will permanently delete the project and <strong>all its issues and comments</strong>. This cannot be undone.</p>
      </div>
      <div class="modal-footer">
        <button class="btn-cancel" id="cdp-cancel">Cancel</button>
        <button class="btn-danger" id="cdp-confirm">Delete Project & All Issues</button>
      </div>
    </div>`);
  document.getElementById('cdp-close').onclick = closeModal;
  document.getElementById('cdp-cancel').onclick = closeModal;
  document.getElementById('cdp-confirm').onclick = async () => {
    try {
      await api.delete(`/api/projects/${project.id}`);
      toast(`Deleted project "${project.name}"`, 'info');
      state.currentProjectId = null;
      closeModal();
      await refreshAll();
    } catch (e) { toast('Delete failed: ' + e.message, 'error'); }
  };
}

/* ── Project form modal ──────────────────────────────────────────────────── */
function openProjectForm(project = null) {
  const isEdit = !!project;
  const colors = ['#5e6ad2','#6366f1','#0ea5e9','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899'];
  const currentColor = project?.color || colors[0];

  showModal(`
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">${isEdit ? 'Edit Project' : 'New Project'}</span>
        <button class="modal-close" id="pf-close">×</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label class="form-label">Name *</label>
          <input class="form-input" id="pf-name" value="${escHtml(project?.name || '')}" placeholder="Project name…">
        </div>
        <div class="form-group">
          <label class="form-label">Description</label>
          <input class="form-input" id="pf-desc" value="${escHtml(project?.description || '')}" placeholder="Optional description">
        </div>
        <div class="form-row-2 form-group">
          <div>
            <label class="form-label">Identifier (e.g. ENG)</label>
            <input class="form-input" id="pf-identifier" value="${escHtml(project?.identifier || '')}" placeholder="Auto-generated" style="text-transform:uppercase">
          </div>
          <div>
            <label class="form-label">Color</label>
            <div class="color-picker" id="pf-color-picker">
              ${colors.map(c => `<div class="color-opt ${c === currentColor ? 'selected' : ''}" data-color="${c}" style="background:${c}" title="${c}"></div>`).join('')}
            </div>
            <input type="hidden" id="pf-color" value="${currentColor}">
          </div>
        </div>
      </div>
      <div class="modal-footer">
        ${isEdit ? '<button class="btn-danger" id="pf-delete">Delete Project</button>' : ''}
        <button class="btn-cancel" id="pf-cancel">Cancel</button>
        <button class="btn-save" id="pf-save">${isEdit ? 'Save Changes' : 'Create Project'}</button>
      </div>
    </div>`);

  document.getElementById('pf-close').onclick = closeModal;
  document.getElementById('pf-cancel').onclick = closeModal;

  if (isEdit) {
    document.getElementById('pf-delete').onclick = () => confirmDeleteProject(project);
  }

  document.getElementById('pf-color-picker').addEventListener('click', e => {
    const opt = e.target.closest('.color-opt');
    if (!opt) return;
    document.querySelectorAll('.color-opt').forEach(o => o.classList.remove('selected'));
    opt.classList.add('selected');
    document.getElementById('pf-color').value = opt.dataset.color;
  });

  document.getElementById('pf-save').onclick = async () => {
    const name = document.getElementById('pf-name').value.trim();
    if (!name) { toast('Name is required', 'error'); return; }
    const body = {
      name,
      description: document.getElementById('pf-desc').value.trim(),
      identifier: document.getElementById('pf-identifier').value.trim().toUpperCase(),
      color: document.getElementById('pf-color').value,
    };
    try {
      if (isEdit) {
        await api.put(`/api/projects/${project.id}`, body);
        toast('Project updated', 'success');
      } else {
        await api.post('/api/projects', body);
        toast(`Project "${name}" created`, 'success');
      }
      closeModal();
      await refreshAll();
    } catch (e) { toast('Save failed: ' + e.message, 'error'); }
  };
}

/* ── Data loading ────────────────────────────────────────────────────────── */
async function refreshIssues() {
  const params = new URLSearchParams();
  if (state.currentProjectId) params.set('project_id', state.currentProjectId);
  if (state.navFilter === 'backlog') params.set('status', 'backlog');
  if (state.navFilter === 'mine') params.set('assignee', 'me');
  if (state.search) params.set('search', state.search);
  state.issues = await api.get('/api/issues?' + params);
  renderIssueList();
  renderBoard();
}

async function refreshAll() {
  [state.projects, state.meta] = await Promise.all([
    api.get('/api/projects'),
    api.get('/api/meta'),
  ]);
  renderSidebar();
  updateViewTitle();
  await Promise.all([refreshIssues(), renderProjectHeader()]);
}

/* ── Toggle list/board ───────────────────────────────────────────────────── */
function setViewMode(mode) {
  state.viewMode = mode;
  const listEl = document.getElementById('issue-list-view');
  const boardEl = document.getElementById('board-view');
  const btn = document.getElementById('btn-toggle-view');
  if (mode === 'board') {
    listEl.classList.add('hidden');
    boardEl.classList.remove('hidden');
    btn.textContent = '≡ List';
    btn.classList.add('active');
  } else {
    boardEl.classList.add('hidden');
    listEl.classList.remove('hidden');
    btn.textContent = '⊞ Board';
    btn.classList.remove('active');
  }
}

/* ── Keyboard shortcuts ──────────────────────────────────────────────────── */
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
  if (document.getElementById('modal-overlay')) return;
  if (e.key === 'n') openIssueForm();
  if (e.key === 'p') openProjectForm();
  if (e.key === 'b') setViewMode(state.viewMode === 'list' ? 'board' : 'list');
  if (e.key === '/') { e.preventDefault(); document.getElementById('search-input').focus(); }
  if (e.key === 'r') refreshAll();
});

/* ── Event wiring ────────────────────────────────────────────────────────── */
document.getElementById('btn-new-issue').onclick = () => openIssueForm();
document.getElementById('btn-new-project').onclick = () => openProjectForm();
document.getElementById('btn-toggle-view').onclick = () => setViewMode(state.viewMode === 'list' ? 'board' : 'list');

document.querySelectorAll('[data-nav]').forEach(el => {
  el.addEventListener('click', () => {
    state.navFilter = el.dataset.nav;
    state.currentProjectId = null;
    updateSidebarActive();
    updateViewTitle();
    renderProjectHeader();
    refreshIssues();
  });
});

let searchTimer;
document.getElementById('search-input').addEventListener('input', e => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.search = e.target.value.trim();
    refreshIssues();
  }, 250);
});

/* ── Auto-refresh (keeps UI in sync with MCP server writes) ──────────────── */
setInterval(() => {
  if (document.getElementById('modal-overlay')) return; // skip while modal open
  if (document.hidden) return;                          // skip while tab hidden
  refreshAll().catch(() => {});
}, 10000);

/* ── Boot ────────────────────────────────────────────────────────────────── */
refreshAll().catch(err => console.error('Boot failed:', err));
