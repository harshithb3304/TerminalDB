/* terminalDB — web dashboard */

const API = {
  commands:   () => fetch('/api/commands').then(r => r.json()),
  delete:     (id) => fetch(`/api/commands/${id}`, { method: 'DELETE' }).then(r => r.json()),
  searchTags: (tag) => fetch(`/api/search/tags?tag=${encodeURIComponent(tag)}`).then(r => r.json()),
  searchAI:   (q)   => fetch(`/api/search/ai?q=${encodeURIComponent(q)}`).then(r => r.json()),
};

let _allRecords = [];
let _searchMode = null; // null | 'local' | 'ai' | 'tag'

// ── Bootstrap ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadAll();
  bindEvents();
});

async function loadAll() {
  _allRecords = await API.commands();
  renderCards(_allRecords);
  updateStats(_allRecords);
}

// ── Events ────────────────────────────────────────────────────────────────
function bindEvents() {
  const input = document.getElementById('search');

  // Live local filter as user types
  input.addEventListener('input', () => {
    const q = input.value.trim();
    if (!q) { showAll(); return; }
    if (q.startsWith('#')) {
      filterByTag(q.slice(1));
    } else {
      filterLocal(q);
    }
  });

  // AI search on Enter
  input.addEventListener('keydown', async (e) => {
    if (e.key !== 'Enter') return;
    const q = input.value.trim();
    if (!q) { showAll(); return; }
    if (q.startsWith('#')) {
      await filterByTagAPI(q.slice(1));
    } else {
      await runAISearch(q);
    }
  });

  document.getElementById('btn-refresh').addEventListener('click', () => {
    document.getElementById('search').value = '';
    loadAll();
    hideError();
    hideSuggestions();
  });
}

// ── Search modes ──────────────────────────────────────────────────────────
function showAll() {
  _searchMode = null;
  renderCards(_allRecords);
  updateStats(_allRecords);
  hideSuggestions();
  hideError();
}

function filterLocal(q) {
  _searchMode = 'local';
  const ql = q.toLowerCase();
  const matched = _allRecords.filter(r => {
    const tags = (r.tags || []).map(t => t.toLowerCase());
    return (
      r.command.toLowerCase().includes(ql) ||
      (r.purpose || '').toLowerCase().includes(ql) ||
      tags.some(t => t.includes(ql))
    );
  });
  renderCards(matched);
  updateStats(matched);
  hideSuggestions();
}

function filterByTag(tag) {
  _searchMode = 'tag';
  const tl = tag.toLowerCase();
  const matched = _allRecords.filter(r =>
    (r.tags || []).some(t => t.toLowerCase().includes(tl))
  );
  renderCards(matched);
  updateStats(matched);
  hideSuggestions();
}

async function filterByTagAPI(tag) {
  _searchMode = 'tag';
  const records = await API.searchTags(tag);
  renderCards(records);
  updateStats(records);
  hideSuggestions();
}

async function runAISearch(q) {
  _searchMode = 'ai';
  hideError();
  document.getElementById('search').style.borderColor = 'var(--yellow)';

  try {
    const data = await API.searchAI(q);
    document.getElementById('search').style.borderColor = '';

    if (data.error) {
      showError(data.error);
    }

    renderCards(data.matched || [], true);
    updateStats(data.matched || []);
    renderSuggestions(data.suggestions || []);
  } catch (err) {
    document.getElementById('search').style.borderColor = '';
    showError(`Request failed: ${err.message}`);
  }
}

// ── Render ────────────────────────────────────────────────────────────────
function renderCards(records, aiMode = false) {
  const grid  = document.getElementById('grid');
  const empty = document.getElementById('empty');

  if (!records || records.length === 0) {
    grid.innerHTML = '';
    empty.classList.remove('hidden');
    document.getElementById('empty-title').textContent =
      aiMode ? 'No matches in your history' : 'No commands yet';
    document.getElementById('empty-sub').textContent =
      aiMode
        ? 'Check AI-suggested commands below.'
        : 'Run any command in your terminal — tdb will ask if you want to save it.';
    return;
  }

  empty.classList.add('hidden');
  grid.innerHTML = records.map(r => cardHTML(r)).join('');

  // Bind card actions
  grid.querySelectorAll('.btn-copy').forEach(btn => {
    btn.addEventListener('click', () => {
      navigator.clipboard.writeText(btn.dataset.cmd).then(() => toast('Copied!'));
    });
  });
  grid.querySelectorAll('.btn-delete').forEach(btn => {
    btn.addEventListener('click', () => confirmDelete(+btn.dataset.id));
  });
  grid.querySelectorAll('.tag').forEach(tag => {
    tag.addEventListener('click', () => {
      const t = tag.dataset.tag;
      document.getElementById('search').value = '#' + t;
      filterByTag(t);
    });
  });
}

function cardHTML(r) {
  const tags  = (r.tags || []).map(t =>
    `<span class="tag" data-tag="${esc(t)}">${esc(t)}</span>`
  ).join('');
  const date  = r.timestamp ? new Date(r.timestamp).toLocaleString() : '';
  return `
    <div class="card">
      <div class="card-cmd">${esc(r.command)}</div>
      ${r.purpose ? `<div class="card-purpose">${esc(r.purpose)}</div>` : ''}
      ${tags ? `<div class="card-tags">${tags}</div>` : ''}
      <div class="card-footer">
        <span class="card-meta">${date}</span>
        <span class="card-id">#${r.id}</span>
        <div class="card-actions">
          <button class="btn-copy"   data-cmd="${esc(r.command)}">&#x2398; Copy</button>
          <button class="btn-delete" data-id="${r.id}">&#x2715; Delete</button>
        </div>
      </div>
    </div>`;
}

function renderSuggestions(suggestions) {
  const section = document.getElementById('ai-section');
  const list    = document.getElementById('suggestions-list');

  if (!suggestions || suggestions.length === 0) {
    section.classList.add('hidden');
    return;
  }

  section.classList.remove('hidden');
  list.innerHTML = suggestions.map(s => `
    <div class="suggestion-item">
      <div class="suggestion-left">
        <div class="suggestion-cmd">${esc(s.command || '')}</div>
        <div class="suggestion-why">${esc(s.why || s.purpose || '')}</div>
      </div>
      <button class="btn-copy" data-cmd="${esc(s.command || '')}">&#x2398; Copy</button>
    </div>
  `).join('');

  list.querySelectorAll('.btn-copy').forEach(btn => {
    btn.addEventListener('click', () => {
      navigator.clipboard.writeText(btn.dataset.cmd).then(() => toast('Copied!'));
    });
  });
}

// ── Stats ─────────────────────────────────────────────────────────────────
function updateStats(records) {
  const uniqueTags = new Set(records.flatMap(r => r.tags || []));
  document.getElementById('stats').textContent =
    `${records.length} command${records.length !== 1 ? 's' : ''} · ${uniqueTags.size} unique tag${uniqueTags.size !== 1 ? 's' : ''}`;
}

// ── Error / Suggestions visibility ───────────────────────────────────────
function showError(msg) {
  const el = document.getElementById('error-banner');
  el.textContent = msg;
  el.classList.remove('hidden');
}
function hideError()       { document.getElementById('error-banner').classList.add('hidden'); }
function hideSuggestions() { document.getElementById('ai-section').classList.add('hidden'); }

// ── Helpers ───────────────────────────────────────────────────────────────
function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function toast(msg) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2000);
}

function confirmDelete(id) {
  if (!confirm(`Delete command #${id}?`)) return;
  API.delete(id).then(({ ok }) => {
    if (ok) {
      _allRecords = _allRecords.filter(r => r.id !== id);
      toast(`Deleted #${id}`);
      // Re-render in current mode
      if (_searchMode === 'ai' || _searchMode === 'tag') {
        renderCards(_allRecords.filter(r =>
          document.getElementById('grid').querySelector(`[data-id="${id}"]`) === null
        ));
      } else {
        const q = document.getElementById('search').value.trim();
        q ? filterLocal(q) : renderCards(_allRecords);
      }
      updateStats(_allRecords);
    }
  });
}
