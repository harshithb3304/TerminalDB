"""
terminalDB web dashboard — Flask backend + embedded single-page UI.
"""
import json
from pathlib import Path

from flask import Flask, jsonify, request

import db as tdb_db

# ---------------------------------------------------------------------------
# HTML — single-file SPA, no external deps
# ---------------------------------------------------------------------------

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>terminalDB</title>
<style>
  /* ── Reset & base ── */
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:       #0d1117;
    --surface:  #161b22;
    --border:   #30363d;
    --text:     #e6edf3;
    --dim:      #8b949e;
    --green:    #3fb950;
    --blue:     #58a6ff;
    --yellow:   #d29922;
    --red:      #f85149;
    --purple:   #bc8cff;
    --tag-bg:   #1f2937;
    --radius:   8px;
    --mono:     'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  }
  html, body { height: 100%; background: var(--bg); color: var(--text);
               font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

  /* ── Layout ── */
  .app { display: flex; flex-direction: column; min-height: 100vh; }
  header { background: var(--surface); border-bottom: 1px solid var(--border);
           padding: 0 24px; display: flex; align-items: center; gap: 16px;
           height: 56px; position: sticky; top: 0; z-index: 100; }
  .logo { font-family: var(--mono); font-size: 18px; font-weight: 700;
          color: var(--green); letter-spacing: -0.5px; white-space: nowrap; }
  .logo span { color: var(--dim); }
  .stats { font-size: 12px; color: var(--dim); white-space: nowrap; }
  .search-wrap { flex: 1; max-width: 480px; position: relative; }
  .search-wrap svg { position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
                     color: var(--dim); pointer-events: none; }
  #searchInput { width: 100%; background: var(--bg); border: 1px solid var(--border);
                 border-radius: 6px; padding: 7px 12px 7px 34px;
                 color: var(--text); font-size: 14px; outline: none; transition: border-color .15s; }
  #searchInput:focus { border-color: var(--blue); }
  #searchInput::placeholder { color: var(--dim); }
  .header-actions { display: flex; gap: 8px; margin-left: auto; }

  main { padding: 24px; flex: 1; }
  .grid { display: grid; gap: 12px;
          grid-template-columns: repeat(auto-fill, minmax(520px, 1fr)); }

  /* ── Command card ── */
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
          padding: 16px; display: flex; flex-direction: column; gap: 10px;
          transition: border-color .15s, box-shadow .15s; }
  .card:hover { border-color: var(--blue); box-shadow: 0 0 0 1px var(--blue)20; }
  .card-top { display: flex; align-items: flex-start; gap: 8px; }
  .cmd-text { font-family: var(--mono); font-size: 13.5px; color: var(--green);
              flex: 1; word-break: break-all; line-height: 1.5; }
  .card-actions { display: flex; gap: 6px; flex-shrink: 0; }
  .btn { border: none; border-radius: 5px; cursor: pointer; font-size: 12px;
         padding: 4px 8px; display: flex; align-items: center; gap: 4px; transition: opacity .1s; }
  .btn:hover { opacity: .8; }
  .btn-copy { background: var(--tag-bg); color: var(--blue); }
  .btn-del  { background: var(--tag-bg); color: var(--red); }
  .purpose  { font-size: 13px; color: var(--dim); line-height: 1.45; }
  .tags     { display: flex; flex-wrap: wrap; gap: 6px; }
  .tag      { font-family: var(--mono); font-size: 11px; background: var(--tag-bg);
              color: var(--blue); border-radius: 20px; padding: 2px 10px;
              border: 1px solid var(--border); }
  .clickable-tag { cursor: pointer; transition: background .15s, border-color .15s; }
  .clickable-tag:hover { background: var(--blue)22; border-color: var(--blue); }
  .card-footer { display: flex; align-items: center; justify-content: space-between; }
  .ts { font-size: 11px; color: var(--dim); font-family: var(--mono); }
  .badge-id { font-family: var(--mono); font-size: 11px; color: var(--dim);
              background: var(--bg); border: 1px solid var(--border);
              border-radius: 4px; padding: 1px 6px; }

  /* ── Empty / loading states ── */
  .empty { text-align: center; padding: 80px 20px; color: var(--dim); }
  .empty .icon { font-size: 48px; margin-bottom: 12px; }
  .empty h2 { font-size: 18px; margin-bottom: 6px; color: var(--text); }
  .empty p  { font-size: 14px; line-height: 1.5; }
  .empty code { font-family: var(--mono); background: var(--surface);
                padding: 2px 6px; border-radius: 4px; color: var(--green); }
  .spinner { display: flex; justify-content: center; padding: 60px;
             color: var(--dim); gap: 10px; align-items: center; font-size: 14px; }

  /* ── AI suggestions panel ── */
  .suggestions { background: var(--surface); border: 1px solid var(--border);
                 border-radius: var(--radius); padding: 16px 20px; margin-top: 24px; }
  .suggestions h3 { font-size: 13px; color: var(--purple); margin-bottom: 12px;
                    text-transform: uppercase; letter-spacing: .08em; }
  .sug-item { padding: 10px 0; border-bottom: 1px solid var(--border); display: flex;
              align-items: flex-start; gap: 12px; }
  .sug-item:last-child { border-bottom: none; padding-bottom: 0; }
  .sug-cmd { font-family: var(--mono); font-size: 13px; color: var(--green); flex: 1; }
  .sug-why { font-size: 12px; color: var(--dim); margin-top: 3px; }
  .btn-sug-copy { margin-left: auto; flex-shrink: 0; }

  /* ── Toast ── */
  #toast { position: fixed; bottom: 24px; right: 24px; background: var(--surface);
           border: 1px solid var(--border); border-radius: var(--radius);
           padding: 10px 16px; font-size: 13px; color: var(--text);
           box-shadow: 0 4px 16px #00000066; transform: translateY(80px);
           opacity: 0; transition: all .25s; z-index: 999; }
  #toast.show { transform: translateY(0); opacity: 1; }
  #toast.ok   { border-color: var(--green); color: var(--green); }
  #toast.err  { border-color: var(--red);   color: var(--red);   }

  /* ── Confirm overlay ── */
  .overlay { display: none; position: fixed; inset: 0; background: #00000088;
             z-index: 200; align-items: center; justify-content: center; }
  .overlay.open { display: flex; }
  .dialog { background: var(--surface); border: 1px solid var(--border);
            border-radius: var(--radius); padding: 24px; max-width: 420px; width: 90%; }
  .dialog h3 { margin-bottom: 8px; font-size: 15px; }
  .dialog p  { font-size: 13px; color: var(--dim); margin-bottom: 20px;
               font-family: var(--mono); word-break: break-all; }
  .dialog-btns { display: flex; gap: 10px; justify-content: flex-end; }
  .btn-cancel { background: var(--tag-bg); color: var(--text); }
  .btn-confirm { background: var(--red)22; color: var(--red); border: 1px solid var(--red)55; }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
</head>
<body>
<div class="app">
  <!-- Header -->
  <header>
    <div class="logo">terminal<span>DB</span></div>
    <div class="search-wrap">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
        <path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.099zm-5.242 1.656a5.5 5.5 0 1 1 0-11 5.5 5.5 0 0 1 0 11z"/>
      </svg>
      <input id="searchInput" type="text" placeholder="Search (Enter = AI)  ·  #tag = filter by tag  ·  Esc = clear" autocomplete="off"/>
    </div>
    <div class="stats" id="statsBar">Loading…</div>
    <div class="header-actions">
      <button class="btn btn-copy" onclick="refreshAll()" title="Refresh">↻ Refresh</button>
    </div>
  </header>

  <main>
    <div id="grid" class="grid"></div>
    <div id="suggestions"></div>
    <div id="empty" class="empty" style="display:none">
      <div class="icon">🗄️</div>
      <h2>No commands yet</h2>
      <p>Run any command in your terminal — tdb will ask if you want to save it.<br/><br/>
         Or run <code>python3 tdb.py add "your command"</code> manually.</p>
    </div>
    <div id="loading" class="spinner" style="display:none">⟳ Loading…</div>
  </main>
</div>

<!-- Delete confirm overlay -->
<div class="overlay" id="overlay">
  <div class="dialog">
    <h3>Delete command?</h3>
    <p id="dlgCmd"></p>
    <div class="dialog-btns">
      <button class="btn btn-cancel" onclick="closeDialog()">Cancel</button>
      <button class="btn btn-confirm" onclick="confirmDelete()">Delete</button>
    </div>
  </div>
</div>

<!-- Toast -->
<div id="toast"></div>

<script>
  let allRecords   = [];
  let pendingDelId = null;
  let searchTimer  = null;
  let aiMode       = false;

  // ── Boot ────────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', refreshAll);

  document.getElementById('searchInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      clearTimeout(searchTimer);
      const q = e.target.value.trim();
      if (q.startsWith('#')) {
        runTagSearch(q.slice(1));
      } else {
        runAISearch(q);
      }
    }
    if (e.key === 'Escape') {
      e.target.value = '';
      aiMode = false;
      renderRecords(allRecords);
      hideSuggestions();
      updateStats(allRecords);
    }
  });
  document.getElementById('searchInput').addEventListener('input', e => {
    const q = e.target.value.trim();
    clearTimeout(searchTimer);
    if (!q) { aiMode = false; renderRecords(allRecords); hideSuggestions(); updateStats(allRecords); return; }
    if (q.startsWith('#')) {
      // Live tag filter as you type
      searchTimer = setTimeout(() => runTagSearch(q.slice(1)), 200);
    } else {
      searchTimer = setTimeout(() => localFilter(q), 200);
    }
  });

  // ── Data fetching ────────────────────────────────────────────────────────
  async function refreshAll() {
    setLoading(true);
    const res  = await fetch('/api/commands');
    allRecords = await res.json();
    aiMode     = false;
    hideSuggestions();
    renderRecords(allRecords);
    updateStats(allRecords);
    setLoading(false);
  }

  async function runAISearch(q) {
    if (!q) return;
    setLoading(true);
    clearError();
    toast('Asking AI…', '');
    const res  = await fetch(`/api/search/ai?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    aiMode     = true;
    if (data.error) {
      showError(data.error);
    }
    renderRecords(data.matched);
    renderSuggestions(data.suggestions || []);
    updateStats(data.matched, !data.error);
    setLoading(false);
  }

  async function runTagSearch(tag) {
    if (!tag) { renderRecords(allRecords); updateStats(allRecords); return; }
    setLoading(true);
    const res     = await fetch(`/api/search/tags?tag=${encodeURIComponent(tag)}`);
    const records = await res.json();
    aiMode        = false;
    renderRecords(records);
    updateStats(records);
    hideSuggestions();
    setLoading(false);
  }

  function filterByTag(tag) {
    const input = document.getElementById('searchInput');
    input.value = `#${tag}`;
    runTagSearch(tag);
  }

  function localFilter(q) {
    const lq      = q.toLowerCase();
    const filtered = allRecords.filter(r =>
      r.command.toLowerCase().includes(lq) ||
      r.purpose.toLowerCase().includes(lq) ||
      r.tags.toLowerCase().includes(lq)
    );
    renderRecords(filtered);
    updateStats(filtered);
    hideSuggestions();
  }

  // ── Render ───────────────────────────────────────────────────────────────
  function renderRecords(records) {
    const grid  = document.getElementById('grid');
    const empty = document.getElementById('empty');
    if (!records || records.length === 0) {
      grid.innerHTML = '';
      if (aiMode) {
        // In AI search mode: don't block the page with "No commands yet"
        // Suggestions still render below in #suggestions div
        empty.querySelector('h2').textContent = 'No matches in your history';
        empty.querySelector('p').textContent  = 'Check AI-suggested commands below.';
      } else {
        empty.querySelector('h2').textContent = 'No commands yet';
        empty.querySelector('p').innerHTML    = 'Run any command in your terminal — tdb will ask if you want to save it.<br/><br/>Or run <code>python3 tdb.py add "your command"</code> manually.';
      }
      empty.style.display = 'block';
      return;
    }
    empty.style.display = 'none';
    grid.innerHTML = records.map(r => cardHTML(r)).join('');
  }

  function cardHTML(r) {
    let tags = [];
    try { tags = JSON.parse(r.tags); } catch { tags = []; }
    const tagsHTML = tags.map(t => `<span class="tag clickable-tag" onclick="filterByTag('${escAttr(t)}')" title="Filter by #${escHtml(t)}">#${escHtml(t)}</span>`).join('');
    const ts = r.timestamp ? r.timestamp.replace('T',' ').replace('Z','') + ' UTC' : '';
    return `
    <div class="card" id="card-${r.id}">
      <div class="card-top">
        <div class="cmd-text">$ ${escHtml(r.command)}</div>
        <div class="card-actions">
          <button class="btn btn-copy" onclick="copyCmd('${escAttr(r.command)}')" title="Copy">
            <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
              <path d="M4 2a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V2Zm2-1a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1H6ZM2 5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-1h1v1a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h1v1H2Z"/>
            </svg>
            Copy
          </button>
          <button class="btn btn-del" onclick="askDelete(${r.id}, '${escAttr(r.command)}')" title="Delete">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
              <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5Zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5Zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6Z"/>
              <path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1ZM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118ZM2.5 3h11V2h-11v1Z"/>
            </svg>
            Delete
          </button>
        </div>
      </div>
      ${r.purpose ? `<div class="purpose">${escHtml(r.purpose)}</div>` : ''}
      ${tagsHTML   ? `<div class="tags">${tagsHTML}</div>` : ''}
      <div class="card-footer">
        <span class="ts">${ts}</span>
        <span class="badge-id">#${r.id}</span>
      </div>
    </div>`;
  }

  function renderSuggestions(sugs) {
    const el = document.getElementById('suggestions');
    if (!sugs.length) { el.innerHTML = ''; return; }
    el.innerHTML = `
      <div class="suggestions">
        <h3>✦ AI-suggested commands</h3>
        ${sugs.map(s => `
          <div class="sug-item">
            <div>
              <div class="sug-cmd">$ ${escHtml(s.command)}</div>
              <div class="sug-why">${escHtml(s.why || '')}</div>
            </div>
            <button class="btn btn-copy btn-sug-copy" onclick="copyCmd('${escAttr(s.command)}')">Copy</button>
          </div>`).join('')}
      </div>`;
  }

  function hideSuggestions() {
    document.getElementById('suggestions').innerHTML = '';
  }

  function updateStats(records, isAI) {
    const tags  = new Set();
    (records || []).forEach(r => {
      try { JSON.parse(r.tags).forEach(t => tags.add(t)); } catch {}
    });
    const label = isAI ? 'AI results' : 'commands';
    document.getElementById('statsBar').textContent =
      `${(records || []).length} ${label} · ${tags.size} unique tags`;
  }

  // ── Actions ──────────────────────────────────────────────────────────────
  function copyCmd(cmd) {
    navigator.clipboard.writeText(cmd)
      .then(() => toast('Copied to clipboard', 'ok'))
      .catch(() => toast('Copy failed', 'err'));
  }

  function askDelete(id, cmd) {
    pendingDelId = id;
    document.getElementById('dlgCmd').textContent = cmd;
    document.getElementById('overlay').classList.add('open');
  }

  function closeDialog() {
    pendingDelId = null;
    document.getElementById('overlay').classList.remove('open');
  }

  async function confirmDelete() {
    if (!pendingDelId) return;
    const id = pendingDelId;
    closeDialog();
    const res = await fetch(`/api/commands/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.ok) {
      allRecords = allRecords.filter(r => r.id !== id);
      document.getElementById(`card-${id}`)?.remove();
      toast('Deleted', 'ok');
      updateStats(allRecords);
      if (!document.querySelectorAll('.card').length) {
        document.getElementById('empty').style.display = 'block';
      }
    } else {
      toast('Delete failed', 'err');
    }
  }

  // ── Error banner ─────────────────────────────────────────────────────────
  function showError(msg) {
    let el = document.getElementById('errBanner');
    if (!el) {
      el = document.createElement('div');
      el.id = 'errBanner';
      el.style.cssText = `background:#2d1414;border:1px solid var(--red);border-radius:var(--radius);
        padding:12px 16px;margin-bottom:16px;font-size:13px;color:var(--red);white-space:pre-wrap;
        font-family:var(--mono);line-height:1.5;`;
      document.querySelector('main').prepend(el);
    }
    el.innerHTML = `<strong>⚠ AI backend unavailable</strong>\n${escHtml(msg)}`;
    el.style.display = 'block';
  }
  function clearError() {
    const el = document.getElementById('errBanner');
    if (el) el.style.display = 'none';
  }

  // ── Utils ────────────────────────────────────────────────────────────────
  function setLoading(on) {
    document.getElementById('loading').style.display = on ? 'flex' : 'none';
  }

  let toastTimer;
  function toast(msg, type) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className   = `show ${type}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.className = '', 2200);
  }

  const escHtml = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const escAttr = s => String(s).replace(/'/g,"\\'").replace(/"/g,'&quot;');

  // Close overlay on backdrop click
  document.getElementById('overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeDialog();
  });
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Flask app factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    app = Flask(__name__)
    tdb_db.init_db()

    @app.route("/")
    def index():
        return _HTML, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/api/commands", methods=["GET"])
    def api_commands():
        return jsonify(tdb_db.fetch_all())

    @app.route("/api/search/ai", methods=["GET"])
    def api_search_ai():
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"matched": tdb_db.fetch_all(), "suggestions": [], "error": None})

        import llm as g
        from llm import LLMError
        all_records = tdb_db.fetch_all_for_search()

        try:
            if not all_records:
                suggestions = g.suggest_only(q)
                return jsonify({"matched": [], "suggestions": suggestions, "error": None})

            result      = g.search_with_intent(q, all_records)
            ranked_ids  = result.get("ranked_ids", [])
            suggestions = result.get("suggestions", [])

            record_map = {r["id"]: r for r in all_records}
            matched    = [record_map[rid] for rid in ranked_ids if rid in record_map]

            if not matched:
                matched = tdb_db.search_local(q)

            if not matched and not suggestions:
                suggestions = g.suggest_only(q)

            return jsonify({"matched": matched, "suggestions": suggestions, "error": None})

        except LLMError as e:
            return jsonify({"matched": tdb_db.search_local(q), "suggestions": [], "error": str(e)})

    @app.route("/api/search/tags", methods=["GET"])
    def api_search_tags():
        tag = request.args.get("tag", "").strip().lstrip("#").lower()
        if not tag:
            return jsonify(tdb_db.fetch_all())
        results = tdb_db.search_local(tag)
        return jsonify(results)

    @app.route("/api/commands/<int:record_id>", methods=["DELETE"])
    def api_delete(record_id: int):
        ok = tdb_db.delete_by_id(record_id)
        return jsonify({"ok": ok})

    return app
