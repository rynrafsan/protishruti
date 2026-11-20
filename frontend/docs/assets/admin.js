/* Protishruti /docs admin: sign in, visibility + schedule, section editor, publish, versions, activity. */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const BD = { timeZone: 'Asia/Dhaka' };
  const when = iso => iso ? new Date(iso).toLocaleString('en-GB', { ...BD, day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true }) : '';
  const clock = iso => iso ? new Date(iso).toLocaleTimeString('en-GB', { ...BD, hour: '2-digit', minute: '2-digit' }) : '';
  const app = $('#app');
  const LIVE_KINDS = [['', 'None'], ['demo', 'Demo links and switches'], ['traction', 'Benchmarks + usage (pitch)'], ['features', 'Feature matrix'],
    ['stack', 'Stack and versions'], ['api', 'Endpoint list'], ['data', 'Knowledge base and data'], ['ai', 'AI benchmarks'],
    ['performance', 'Response times'], ['security', 'Security settings'], ['analytics', 'Usage counts']];
  const TYPES = [['richtext', 'Text'], ['team', 'Team'], ['diagram', 'Diagram (Mermaid)'], ['changelog', 'Changelog']];
  const S = { info: null, content: null, rev: 0, sel: 'meta', unsaved: false, saving: false, tab: 'visibility', timer: null };

  function toast(msg, err = false) {
    const t = document.createElement('div');
    t.className = 'toast' + (err ? ' err' : ''); t.textContent = msg;
    $('.toast-zone').append(t);
    setTimeout(() => t.remove(), err ? 6000 : 2600);
  }
  async function api(method, url, body, isForm = false) {
    const opt = { method, headers: { 'X-Docs-Admin': '1', Accept: 'application/json' }, credentials: 'same-origin' };
    if (body !== undefined) {
      if (isForm) opt.body = body;
      else { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; }
    }
    const r = await fetch(url, opt);
    let data = null;
    try { data = await r.json(); } catch { /* not JSON */ }
    if (r.status === 401 && !url.endsWith('/login')) { S.info.user = null; renderSignIn('Your session ended. Sign in again.'); throw new Error('Signed out'); }
    if (!r.ok) {
      const d = data && data.detail;
      throw new Error(typeof d === 'string' ? d : (d && d.message) || `Server answered ${r.status}`);
    }
    return data;
  }

  /* ================= sign in ================= */
  function renderSignIn(note = '') {
    $('#who').hidden = $('#signOut').hidden = true;
    const enabled = S.info && (S.info.roles_enabled.admin || S.info.roles_enabled.super);
    app.innerHTML = `<form class="signin" id="signin">
      <h1>Sign in to edit the docs</h1>
      ${enabled ? `<p>Use the Admin or Super Admin password set on the server.</p>
        <label class="f"><span>Your name</span><input type="text" name="name" autocomplete="name" maxlength="40" placeholder="Shown in the version history"></label>
        <label class="f"><span>Password</span><input type="password" name="password" autocomplete="current-password" required></label>
        <button class="btn primary" type="submit" style="width:100%">Sign in</button>`
        : `<p>Admin sign-in is switched off on this server. Set <code>DOCS_ADMIN_PASSWORD</code> (and optionally <code>DOCS_SUPERADMIN_PASSWORD</code>), 12 characters or more, in the server's environment and restart it.</p>`}
      <p class="msg ${note ? 'warn' : ''}" id="signinMsg">${esc(note)}</p>
    </form>`;
    const f = $('#signin');
    f.addEventListener('submit', async e => {
      e.preventDefault();
      const btn = $('button', f); btn.disabled = true;
      try {
        await api('POST', '/api/docs/admin/login', { name: f.name.value, password: f.password.value });
        await start();
      } catch (err) { const m = $('#signinMsg'); m.className = 'msg err'; m.textContent = err.message; btn.disabled = false; f.password.select(); }
    });
    (f.name || f).focus?.();
  }
  $('#signOut').addEventListener('click', async () => {
    if (S.unsaved && !confirm('You have unsaved changes. Sign out anyway?')) return;
    await api('POST', '/api/docs/admin/logout', {}).catch(() => {});
    S.info.user = null; S.unsaved = false; renderSignIn('Signed out.');
  });

  /* ================= shell ================= */
  const isSuper = () => S.info.user && S.info.user.role === 'super';
  function renderShell() {
    const u = S.info.user;
    $('#who').innerHTML = `<b>${esc(u.name)}</b> · ${u.role === 'super' ? 'Super Admin' : 'Admin'}`;
    $('#who').hidden = $('#signOut').hidden = false;
    const tabs = [['visibility', 'Visibility'], ['content', 'Content'], ['versions', 'Versions']].concat(isSuper() ? [['activity', 'Activity']] : []);
    app.innerHTML = `<div class="tabs" role="tablist">${tabs.map(([k, l]) => `<button role="tab" data-tab="${k}" aria-selected="${S.tab === k}">${l}</button>`).join('')}</div><div id="tab"></div>`;
    $('.tabs').addEventListener('click', e => {
      const b = e.target.closest('[data-tab]');
      if (!b) return;
      S.tab = b.dataset.tab;
      $$('.tabs button').forEach(x => x.setAttribute('aria-selected', String(x === b)));
      renderTab();
    });
    renderTab();
  }
  function renderTab() {
    ({ visibility: renderVisibility, content: renderContent, versions: renderVersions, activity: renderActivity })[S.tab]();
  }
  function storageNote() {
    const st = S.info.storage, gh = S.info.github;
    if (gh.enabled) return `<p class="msg ok">Changes are also committed to GitHub (<b>${esc(gh.repo)}</b>, branch <b>${esc(gh.branch)}</b>), so they survive restarts. The host redeploys after each commit.</p>`;
    if (st.on_render && !st.custom_dir) return `<p class="msg warn">This server's disk is wiped whenever it restarts (Render's free plan restarts it after 15 idle minutes). To keep visibility changes, also set <code>DOCS_PUBLIC</code>, <code>DOCS_OPEN_FROM</code> and <code>DOCS_OPEN_UNTIL</code> in Render. To keep content edits, download <code>content.json</code> and commit it, or set <code>DOCS_GITHUB_REPO</code> and <code>DOCS_GITHUB_TOKEN</code> so publishing commits for you.</p>`;
    return `<p class="hint">Saved on this server in <code>${esc(st.dir)}</code>. To make content permanent, download <code>content.json</code> and commit it as <code>${esc(st.default_file)}</code>.</p>`;
  }

  /* ================= visibility ================= */
  function stateBox(st) {
    const cls = st.state === 'open' ? 'open' : st.state === 'scheduled' ? 'wait' : 'closed';
    const head = { open: 'Open to the public now', scheduled: 'Closed now, opens on schedule', ended: 'Closed: the window has ended', off: 'Turned off' }[st.state];
    const sub = st.state === 'open' ? (st.end ? `Closes ${when(st.end)} (GMT+6).` : 'No end date.')
      : st.state === 'scheduled' ? `Opens ${when(st.start)} (GMT+6).` : st.state === 'ended' ? `Closed since ${when(st.end)} (GMT+6).` : 'Only signed-in admins can open /docs. Visitors see a "not available" page (HTTP 403).';
    return `<div class="state ${cls}" role="status"><span class="light" aria-hidden="true"></span><div><b>${head}</b><span>${esc(sub)}</span></div></div>`;
  }
  const local = iso => iso ? iso.slice(0, 16) : '';
  function renderVisibility() {
    const s = S.info.settings;
    $('#tab').innerHTML = `${stateBox(S.info.status)}
      <form id="vis">
        <section class="card"><h2>Public access</h2><p>The master switch. Off hides /docs from everyone except signed-in admins, whatever the schedule says.</p>
          <label class="switch"><input type="checkbox" name="enabled" ${s.enabled ? 'checked' : ''}> Show /docs to the public</label></section>
        <section class="card"><h2>Publishing window</h2><p>Bangladesh time (GMT+6). The end minute is included.</p>
          <label class="check"><input type="checkbox" name="schedule" ${s.schedule ? 'checked' : ''}> Only show between these times</label>
          <div class="row"><label class="f"><span>Opens</span><input type="datetime-local" name="start" value="${local(s.start)}"></label>
            <label class="f"><span>Closes</span><input type="datetime-local" name="end" value="${local(s.end)}"></label></div>
          <div class="quick"><span>Or open now for</span>${[[24, '1 day'], [72, '3 days'], [168, '7 days'], [720, '30 days']].map(([h, l]) => `<button class="btn small" type="button" data-hours="${h}">${l}</button>`).join('')}</div></section>
        <section class="card"><h2>Message when closed</h2>
          <label class="f"><input type="text" name="closed_message" maxlength="300" value="${esc(s.closed_message)}"><small>Shown on the "not available" page.</small></label></section>
        <div class="btns"><button class="btn primary" type="submit">Save visibility</button>
          ${isSuper() ? '<button class="btn" type="button" id="resetVis">Reset to server defaults</button>' : ''}
          <span class="hint">Last change: ${esc(s.updated_by || '')} ${s.updated_at ? '· ' + esc(when(s.updated_at)) : ''} (${esc(s.source)})</span></div>
        <p class="msg" id="visMsg"></p>
      </form>${storageNote()}`;
    const f = $('#vis');
    const save = async body => {
      const m = $('#visMsg');
      try {
        const r = await api('PUT', '/api/docs/admin/settings', body);
        S.info.settings = r.settings; S.info.status = r.status;
        renderVisibility();
        const mm = $('#visMsg');
        mm.className = 'msg ok'; mm.textContent = 'Saved.' + syncText(r.github);
        if (r.github && !r.github.ok) mm.className = 'msg warn';
      } catch (e) { m.className = 'msg err'; m.textContent = e.message; }
    };
    f.addEventListener('submit', e => {
      e.preventDefault();
      save({ enabled: f.enabled.checked, schedule: f.schedule.checked, start: f.start.value || null, end: f.end.value || null, closed_message: f.closed_message.value });
    });
    $$('[data-hours]', f).forEach(b => b.addEventListener('click', () => save({ duration_hours: Number(b.dataset.hours), closed_message: f.closed_message.value })));
    $('#resetVis')?.addEventListener('click', async () => {
      if (!confirm('Reset visibility to the server defaults (environment variables)?')) return;
      try { const r = await api('POST', '/api/docs/admin/settings/reset', {}); S.info.settings = r.settings; S.info.status = r.status; renderVisibility(); toast('Reset to defaults'); }
      catch (e) { toast(e.message, true); }
    });
  }
  function syncText(g) {
    if (!g) return '';
    if (g.ok && g.unchanged) return ' GitHub already had this version.';
    if (g.ok) return ` Committed to GitHub (${g.commit}); the server redeploys in a few minutes.`;
    return ` Saved here, but the GitHub commit failed: ${g.error}`;
  }

  /* ================= content editor ================= */
  async function loadDraft() {
    const d = await api('GET', '/api/docs/admin/draft');
    S.content = d.content; S.rev = d.content._rev || 0; S.info.dirty = d.dirty; S.unsaved = false;
    const backup = localStorage.getItem('pdocs-backup');
    if (backup) {
      try {
        const b = JSON.parse(backup);
        if (b.rev === S.rev && confirm('You have changes from an earlier session that were never saved to the server. Restore them?')) { S.content = b.content; S.unsaved = true; }
        else localStorage.removeItem('pdocs-backup');
      } catch { localStorage.removeItem('pdocs-backup'); }
    }
  }
  async function renderContent() {
    if (!S.content) {
      $('#tab').innerHTML = '<p class="loading">Loading the draft…</p>';
      try { await loadDraft(); } catch (e) { $('#tab').innerHTML = `<p class="msg err">${esc(e.message)}</p>`; return; }
    }
    $('#tab').innerHTML = `<div class="bar"><span class="status" id="saveStatus"></span>
        <div class="btns">
          <button class="btn" id="saveBtn">Save draft</button>
          <a class="btn" href="/docs?preview=draft" target="_blank" rel="noopener" id="previewBtn">Preview</a>
          <button class="btn gold" id="pubBtn">Publish…</button>
          <details class="menu"><summary class="btn" aria-label="More actions">More</summary>
            <div class="menu-list">
              <a href="/api/docs/admin/export.json?which=draft" download>Download draft as content.json</a>
              <a href="/api/docs/admin/export.json?which=published" download>Download published content.json</a>
              <button data-more="discard">Discard draft changes</button>
              ${isSuper() ? '<button data-more="reset">Reset draft to repository default</button>' : ''}
            </div></details>
        </div></div>
      <div id="pubBox"></div>
      <div class="editor"><nav class="list" id="list" aria-label="Sections"></nav><section class="pane" id="pane"></section></div>`;
    $('#saveBtn').addEventListener('click', () => saveDraft());
    $('#previewBtn').addEventListener('click', async e => { if (S.unsaved) { e.preventDefault(); await saveDraft(); window.open('/docs?preview=draft', '_blank', 'noopener'); } });
    $('#pubBtn').addEventListener('click', showPublish);
    $('.bar details').addEventListener('click', async e => {
      const act = e.target.closest('[data-more]')?.dataset.more;
      if (!act) return;
      e.target.closest('details').open = false;
      if (act === 'discard' && confirm('Throw away every change that is not published?')) {
        try { await api('POST', '/api/docs/admin/discard', {}); localStorage.removeItem('pdocs-backup'); S.content = null; renderContent(); toast('Draft discarded'); } catch (err) { toast(err.message, true); }
      }
      if (act === 'reset' && confirm('Replace the draft with the content committed in the repository (data/docs/content.json)? Publish afterwards to make it live.')) {
        try { await api('POST', '/api/docs/admin/reset-content', {}); S.content = null; renderContent(); toast('Draft reset'); } catch (err) { toast(err.message, true); }
      }
    });
    renderList(); renderPane(); updateStatus();
  }
  function updateStatus() {
    const el = $('#saveStatus');
    if (!el) return;
    const c = S.content;
    if (S.saving) el.innerHTML = 'Saving…';
    else if (S.unsaved) el.innerHTML = '<span class="dirty-dot"></span><b>Unsaved changes</b> (saved automatically after a few seconds)';
    else el.innerHTML = `${c._saved_at ? `Draft saved ${esc(clock(c._saved_at))}${c._saved_by ? ' by ' + esc(c._saved_by) : ''}` : 'No draft changes yet'} · ${S.info.dirty ? '<b>not published yet</b>' : 'same as the published page'} · published version ${S.info.published_version}`;
  }
  function changed() {
    S.unsaved = true; updateStatus();
    try { localStorage.setItem('pdocs-backup', JSON.stringify({ rev: S.rev, content: S.content })); } catch { /* storage full or blocked */ }
    clearTimeout(S.timer);
    S.timer = setTimeout(() => saveDraft(true), 5000);
  }
  async function saveDraft(auto = false) {
    clearTimeout(S.timer);
    if (S.saving || (!S.unsaved && auto)) return true;
    S.saving = true; updateStatus();
    try {
      const r = await api('PUT', '/api/docs/admin/draft', { content: S.content, base_rev: S.rev });
      S.rev = r.rev; S.content._rev = r.rev; S.content._saved_at = r.saved_at; S.content._saved_by = S.info.user.name;
      S.info.dirty = r.dirty; S.unsaved = false;
      localStorage.removeItem('pdocs-backup');
      if (!auto) toast('Draft saved');
      return true;
    } catch (e) {
      toast(e.message, true);
      return false;
    } finally { S.saving = false; updateStatus(); }
  }
  function showPublish() {
    const box = $('#pubBox');
    box.innerHTML = `<section class="card"><h2>Publish the draft</h2><p>Visitors to /docs will see this version right away (if /docs is open). The current version stays in the history.</p>
      <label class="f"><span>What changed (optional)</span><input type="text" id="pubNote" maxlength="200" placeholder="e.g. Added team photos"></label>
      <div class="btns"><button class="btn gold" id="pubGo">Publish now</button><button class="btn" id="pubCancel">Cancel</button></div><p class="msg" id="pubMsg"></p></section>`;
    $('#pubNote').focus();
    $('#pubCancel').addEventListener('click', () => { box.innerHTML = ''; });
    $('#pubGo').addEventListener('click', async () => {
      const m = $('#pubMsg'), btn = $('#pubGo');
      btn.disabled = true;
      if (S.unsaved && !(await saveDraft())) { btn.disabled = false; return; }
      try {
        const r = await api('POST', '/api/docs/admin/publish', { note: $('#pubNote').value });
        S.info.published_version = r.version; S.info.dirty = false; updateStatus();
        m.className = 'msg ' + (r.github && !r.github.ok ? 'warn' : 'ok');
        m.innerHTML = `Published version ${r.version}. <a href="/docs" target="_blank" rel="noopener">Open /docs</a>.${esc(syncText(r.github))}`;
      } catch (e) { m.className = 'msg err'; m.textContent = e.message; }
      btn.disabled = false;
    });
  }

  /* ---------- section list: select, reorder (drag or buttons), hide ---------- */
  const secs = () => S.content.sections;
  function renderList() {
    const groups = [['pitch', 'Pitch deck'], ['tech', 'Technical documentation']];
    let html = `<div class="item" data-sel="meta" tabindex="0" aria-current="${S.sel === 'meta'}"><span class="grip"></span><span class="t">Page header</span></div>`;
    for (const [g, label] of groups) {
      html += `<h3>${label}</h3>`;
      secs().forEach((s, i) => {
        if (s.group !== g) return;
        html += `<div class="item ${s.visible === false ? 'hidden' : ''}" data-sel="${i}" tabindex="0" draggable="true" aria-current="${S.sel === i}">
          <span class="grip" aria-hidden="true">⋮⋮</span><span class="t" title="${esc(s.title)}">${esc(s.title)}</span>
          <span class="mv"><button data-mv="-1" aria-label="Move ${esc(s.title)} up">↑</button><button data-mv="1" aria-label="Move ${esc(s.title)} down">↓</button>
          <button data-vis aria-label="${s.visible === false ? 'Show' : 'Hide'} ${esc(s.title)}" title="${s.visible === false ? 'Hidden: click to show' : 'Visible: click to hide'}">${s.visible === false ? '◌' : '●'}</button></span></div>`;
      });
    }
    html += `<div class="btns" style="margin:12px 4px 4px"><button class="btn small" id="addSec">Add section</button></div>`;
    const list = $('#list');
    list.innerHTML = html;
    list.onclick = e => {
      const item = e.target.closest('.item');
      if (e.target.closest('#addSec')) return addSection();
      if (!item) return;
      const i = item.dataset.sel === 'meta' ? 'meta' : Number(item.dataset.sel);
      if (e.target.closest('[data-mv]')) return move(i, Number(e.target.closest('[data-mv]').dataset.mv));
      if (e.target.closest('[data-vis]')) { secs()[i].visible = secs()[i].visible === false; changed(); renderList(); if (S.sel === i) renderPane(); return; }
      select(i);
    };
    list.onkeydown = e => { const item = e.target.closest('.item'); if (item && (e.key === 'Enter' || e.key === ' ') && e.target === item) { e.preventDefault(); item.click(); } };
    let from = null;
    $$('.item[draggable]', list).forEach(el => {
      el.addEventListener('dragstart', e => { from = Number(el.dataset.sel); el.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(from)); });
      el.addEventListener('dragend', () => { el.classList.remove('dragging'); $$('.drop', list).forEach(x => x.classList.remove('drop')); });
      el.addEventListener('dragover', e => { e.preventDefault(); el.classList.add('drop'); });
      el.addEventListener('dragleave', () => el.classList.remove('drop'));
      el.addEventListener('drop', e => {
        e.preventDefault();
        const to = Number(el.dataset.sel);
        if (from === null || from === to) return;
        const arr = secs(), selected = typeof S.sel === 'number' ? arr[S.sel] : null;
        const [item] = arr.splice(from, 1), at = to > from ? to - 1 : to;
        item.group = arr[at]?.group || item.group;
        arr.splice(at, 0, item);
        if (selected) S.sel = arr.indexOf(selected);
        changed(); renderList(); renderPane();
      });
    });
  }
  function move(i, dir) {
    const arr = secs(), g = arr[i].group;
    let j = i + dir;
    while (j >= 0 && j < arr.length && arr[j].group !== g) j += dir;
    if (j < 0 || j >= arr.length) return;
    [arr[i], arr[j]] = [arr[j], arr[i]];
    if (S.sel === i) S.sel = j; else if (S.sel === j) S.sel = i;
    changed(); renderList();
    $(`.item[data-sel="${j}"] [data-mv="${dir}"]`)?.focus();
  }
  function select(i) { S.sel = i; renderList(); renderPane(); $('#pane').scrollIntoView({ block: 'nearest' }); }
  function addSection() {
    const title = prompt('Title of the new section');
    if (!title) return;
    let id = title.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'section';
    while (secs().some(s => s.id === id)) id += '-2';
    const group = typeof S.sel === 'number' ? secs()[S.sel].group : 'tech';
    secs().push({ id, group, type: 'richtext', title, kicker: '', body: '', visible: true, live: '', figures: [], video_url: '' });
    changed(); select(secs().length - 1);
  }

  /* ---------- rich text editor ---------- */
  function rte(html, onChange, opts = {}) {
    const wrap = document.createElement('div');
    wrap.className = 'rte-wrap';
    wrap.innerHTML = `<div class="rte-tools" role="toolbar" aria-label="Formatting">
      <button type="button" data-c="bold" title="Bold"><b>B</b></button><button type="button" data-c="italic" title="Italic"><i>I</i></button>
      <span class="sep"></span><button type="button" data-b="h3" title="Heading">H3</button><button type="button" data-b="h4" title="Small heading">H4</button><button type="button" data-b="p" title="Paragraph">¶</button>
      <span class="sep"></span><button type="button" data-c="insertUnorderedList" title="Bullet list">• List</button><button type="button" data-c="insertOrderedList" title="Numbered list">1. List</button>
      <button type="button" data-b="blockquote" title="Quote">❝</button><button type="button" data-x="link" title="Link">Link</button><button type="button" data-x="code" title="Code">Code</button>
      ${opts.short ? '' : '<button type="button" data-x="table" title="Insert a table">Table</button>'}<button type="button" data-x="clear" title="Clear formatting">Clear</button>
      <span class="sep"></span><button type="button" data-x="html" aria-pressed="false" title="Edit the HTML">HTML</button></div>
      <div class="rte ${opts.short ? 'short' : ''}" contenteditable="true" role="textbox" aria-multiline="true" aria-label="${esc(opts.label || 'Text')}" data-placeholder="${esc(opts.placeholder || 'Write here…')}"></div>`;
    const ed = $('.rte', wrap);
    ed.innerHTML = html || '';
    let src = null;
    const emit = () => onChange(src ? src.value : ed.innerHTML);
    ed.addEventListener('input', emit);
    ed.addEventListener('paste', e => { e.preventDefault(); document.execCommand('insertText', false, e.clipboardData.getData('text/plain')); });
    ed.addEventListener('focus', () => document.execCommand('defaultParagraphSeparator', false, 'p'));
    $('.rte-tools', wrap).addEventListener('mousedown', e => { if (e.target.closest('button')) e.preventDefault(); });
    $('.rte-tools', wrap).addEventListener('click', e => {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.dataset.x === 'html') {
        if (src) { ed.innerHTML = src.value; src.remove(); src = null; ed.hidden = false; b.setAttribute('aria-pressed', 'false'); }
        else { src = document.createElement('textarea'); src.className = 'code'; src.value = ed.innerHTML; src.addEventListener('input', emit); ed.hidden = true; ed.after(src); b.setAttribute('aria-pressed', 'true'); src.focus(); }
        return;
      }
      if (src) return;
      ed.focus();
      if (b.dataset.c) document.execCommand(b.dataset.c);
      if (b.dataset.b) document.execCommand('formatBlock', false, b.dataset.b);
      if (b.dataset.x === 'link') { const u = prompt('Link address (https://…, mailto:… or #section)'); if (u) document.execCommand('createLink', false, u.trim()); }
      if (b.dataset.x === 'code') { const t = String(getSelection()); document.execCommand('insertHTML', false, `<code>${esc(t || 'code')}</code>`); }
      if (b.dataset.x === 'table') document.execCommand('insertHTML', false, '<table><thead><tr><th>Heading</th><th>Heading</th></tr></thead><tbody><tr><td>Cell</td><td>Cell</td></tr></tbody></table><p></p>');
      if (b.dataset.x === 'clear') { document.execCommand('removeFormat'); document.execCommand('formatBlock', false, 'p'); }
      emit();
    });
    return wrap;
  }

  /* ---------- editor pane ---------- */
  const field = (label, html, hint = '') => `<label class="f"><span>${label}</span>${html}${hint ? `<small>${hint}</small>` : ''}</label>`;
  const input = (name, value, attrs = '') => `<input type="text" data-k="${name}" value="${esc(value)}" ${attrs}>`;
  function bindInputs(root, obj, after) {
    $$('[data-k]', root).forEach(el => {
      const ev = el.type === 'checkbox' || el.tagName === 'SELECT' ? 'change' : 'input';
      el.addEventListener(ev, () => { obj[el.dataset.k] = el.type === 'checkbox' ? el.checked : el.value; changed(); after && after(el.dataset.k); });
    });
  }
  function renderPane() {
    const pane = $('#pane');
    if (S.sel === 'meta' || !secs()[S.sel]) { S.sel = 'meta'; return renderMeta(pane); }
    const s = secs()[S.sel];
    s.figures = s.figures || [];
    pane.innerHTML = `<h2>${esc(s.title)}<button class="btn small danger" id="delSec">Delete section</button></h2>
      <div class="row">${field('Title', input('title', s.title, 'maxlength="120"'))}${field('Link id', input('id', s.id, 'maxlength="41" pattern="[a-z0-9][a-z0-9-]*"'), 'Lowercase letters, digits and dashes; used in /docs#' + esc(s.id))}</div>
      <div class="row">
        ${field('Part', `<select data-k="group"><option value="pitch" ${s.group === 'pitch' ? 'selected' : ''}>Pitch deck</option><option value="tech" ${s.group === 'tech' ? 'selected' : ''}>Technical documentation</option></select>`)}
        ${field('Kind', `<select data-k="type">${TYPES.map(([v, l]) => `<option value="${v}" ${s.type === v ? 'selected' : ''}>${l}</option>`).join('')}</select>`)}
        ${field('Live panel', `<select data-k="live">${LIVE_KINDS.map(([v, l]) => `<option value="${v}" ${s.live === v ? 'selected' : ''}>${l}</option>`).join('')}</select>`, 'Data read from the running server, shown under the text')}
      </div>
      <label class="check"><input type="checkbox" data-k="visible" ${s.visible !== false ? 'checked' : ''}> Visible on /docs</label>
      ${field('Headline', `<textarea data-k="kicker" maxlength="220" rows="2">${esc(s.kicker)}</textarea>`, 'One sentence. In the pitch it is the slide headline.')}
      <fieldset><legend>Key figures (up to 4, each with a source)</legend><div id="figs"></div><button class="btn small" type="button" id="addFig">Add a figure</button><p></p></fieldset>
      <div class="f"><span style="display:block;font-weight:600;font-size:15px;margin-bottom:5px">Text</span><div id="bodyEd"></div></div>
      <div id="typeEd"></div>
      ${field('YouTube video (optional)', input('video_url', s.video_url || '', 'placeholder="https://youtu.be/…"'), 'Shown as a click-to-play video in this section. Use an Unlisted or Public link.')}`;
    bindInputs(pane, s, k => {
      if (k === 'title') { $('h2', pane).firstChild.textContent = s.title; $(`.item[data-sel="${S.sel}"] .t`).textContent = s.title; }
      if (k === 'group') renderList();
      if (k === 'type' || k === 'live') renderTypeEditor(s);
      if (k === 'visible') renderList();
    });
    $('#bodyEd').append(rte(s.body, v => { s.body = v; changed(); }, { label: 'Section text' }));
    renderFigures(s);
    $('#addFig').addEventListener('click', () => { if (s.figures.length >= 4) return toast('Four figures at most', true); s.figures.push({ value: '', label: '', source: '' }); changed(); renderFigures(s); });
    $('#delSec').addEventListener('click', () => {
      if (!confirm(`Delete the section "${s.title}"? You can still discard the draft afterwards to get it back.`)) return;
      secs().splice(S.sel, 1); S.sel = 'meta'; changed(); renderList(); renderPane();
    });
    renderTypeEditor(s);
  }
  function renderFigures(s) {
    const box = $('#figs');
    box.innerHTML = s.figures.map((f, i) => `<div class="sub" data-i="${i}"><div class="row">
      ${field('Figure', `<input type="text" data-f="value" maxlength="24" value="${esc(f.value)}" placeholder="1.13 million">`)}
      ${field('What it means', `<input type="text" data-f="label" maxlength="140" value="${esc(f.label)}">`)}
      ${field('Source link', `<input type="url" data-f="source" value="${esc(f.source)}" placeholder="https://…">`)}</div>
      <button class="btn small danger" type="button" data-del>Remove</button></div>`).join('');
    $$('.sub', box).forEach(row => {
      const f = s.figures[Number(row.dataset.i)];
      $$('[data-f]', row).forEach(el => el.addEventListener('input', () => { f[el.dataset.f] = el.value; changed(); }));
      $('[data-del]', row).addEventListener('click', () => { s.figures.splice(Number(row.dataset.i), 1); changed(); renderFigures(s); });
    });
  }
  function renderTypeEditor(s) {
    const box = $('#typeEd');
    box.innerHTML = '';
    if (s.type === 'team') teamEditor(s, box);
    if (s.type === 'diagram') diagramEditor(s, box);
    if (s.type === 'changelog') changelogEditor(s, box);
    if (s.live === 'features') plannedEditor(s, box);
  }
  function initials(n) { return esc((n || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase()); }
  function teamEditor(s, box) {
    s.members = s.members || [];
    const fs = document.createElement('fieldset');
    fs.innerHTML = `<legend>Team</legend>${field('Team name', `<input type="text" id="teamName" maxlength="80" value="${esc(s.team_name || '')}">`)}<div id="members"></div>
      <button class="btn small" type="button" id="addMember">Add a member</button><p class="hint">Photos are cropped to 3:4 (passport-photo shape), resized and stripped of location data when you upload them.</p>`;
    box.append(fs);
    $('#teamName').addEventListener('input', e => { s.team_name = e.target.value; changed(); });
    const draw = () => {
      $('#members').innerHTML = s.members.map((m, i) => `<div class="sub" data-i="${i}"><div class="member-ed">
        <div><span class="photo">${m.photo ? `<img src="${esc(m.photo)}" alt="">` : `<span class="initials">${initials(m.name)}</span>`}</span>
          <div class="photo-btns"><label class="btn small">Upload photo<input type="file" accept="image/*" data-up hidden></label>${m.photo ? '<button class="btn small" type="button" data-rmphoto>Remove photo</button>' : ''}</div></div>
        <div><div class="row">${field('Full name', `<input type="text" data-m="name" maxlength="80" value="${esc(m.name)}">`)}${field('Role', `<input type="text" data-m="role" maxlength="120" value="${esc(m.role)}" placeholder="e.g. ML engineer">`)}</div>
          <div class="row">${field('Email', `<input type="email" data-m="email" maxlength="254" value="${esc(m.email)}">`)}${field('One line about them', `<input type="text" data-m="bio" maxlength="220" value="${esc(m.bio || '')}">`)}</div>
          <div class="btns"><button class="btn small" type="button" data-mm="-1">Move up</button><button class="btn small" type="button" data-mm="1">Move down</button><button class="btn small danger" type="button" data-rm>Remove member</button></div></div>
      </div></div>`).join('');
      $$('#members .sub').forEach(row => {
        const i = Number(row.dataset.i), m = s.members[i];
        $$('[data-m]', row).forEach(el => el.addEventListener('input', () => { m[el.dataset.m] = el.value; changed(); if (el.dataset.m === 'name' && !m.photo) $('.initials', row).textContent = initials(m.name).replace(/&amp;/g, '&'); }));
        $('[data-rm]', row).addEventListener('click', () => { if (confirm(`Remove ${m.name || 'this member'}?`)) { s.members.splice(i, 1); changed(); draw(); } });
        $$('[data-mm]', row).forEach(b => b.addEventListener('click', () => { const j = i + Number(b.dataset.mm); if (j < 0 || j >= s.members.length) return; [s.members[i], s.members[j]] = [s.members[j], s.members[i]]; changed(); draw(); }));
        $('[data-rmphoto]', row)?.addEventListener('click', () => { m.photo = ''; changed(); draw(); });
        $('[data-up]', row).addEventListener('change', async e => {
          const file = e.target.files[0];
          if (!file) return;
          const fd = new FormData(); fd.append('file', file);
          try { const r = await api('POST', '/api/docs/admin/photo', fd, true); m.photo = r.photo; changed(); draw(); toast(`Photo ready (${r.kb} KB)`); }
          catch (err) { toast(err.message, true); }
        });
      });
    };
    draw();
    $('#addMember').addEventListener('click', () => { s.members.push({ id: '', name: '', role: '', email: '', bio: '', photo: '' }); changed(); draw(); $('#members .sub:last-child input').focus(); });
  }
  let mermaidP = null;
  function diagramEditor(s, box) {
    const fs = document.createElement('fieldset');
    fs.innerHTML = `<legend>Diagram</legend>${field('Mermaid source', `<textarea class="code" id="mmSrc" spellcheck="false">${esc(s.mermaid || '')}</textarea>`, 'Mermaid flowchart syntax. <a href="https://mermaid.js.org/syntax/flowchart.html" target="_blank" rel="noopener">Syntax guide</a>.')}
      ${field('Caption', `<input type="text" id="mmCap" maxlength="300" value="${esc(s.caption || '')}">`)}
      <button class="btn small" type="button" id="mmPrev">Preview the diagram</button><div class="diagram diagram-preview" id="mmOut" hidden></div><p></p>`;
    box.append(fs);
    $('#mmSrc').addEventListener('input', e => { s.mermaid = e.target.value; changed(); });
    $('#mmCap').addEventListener('input', e => { s.caption = e.target.value; changed(); });
    $('#mmPrev').addEventListener('click', async () => {
      const out = $('#mmOut'); out.hidden = false; out.textContent = 'Drawing…';
      try {
        mermaidP = mermaidP || import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs').then(m => { m.default.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'base', themeVariables: { primaryColor: '#F8FAF7', primaryBorderColor: '#1B6B53', lineColor: '#586A63', clusterBkg: '#EEF4F0', fontFamily: 'Hind Siliguri, sans-serif' } }); return m.default; });
        const m = await mermaidP;
        out.innerHTML = (await m.render('prev' + Date.now(), s.mermaid || '')).svg;
      } catch (e) { out.innerHTML = `<p class="msg err">${esc(e.message || 'Could not draw this diagram.')}</p>`; }
    });
  }
  function changelogEditor(s, box) {
    s.entries = s.entries || [];
    const fs = document.createElement('fieldset');
    fs.innerHTML = '<legend>Changelog entries (newest first)</legend><div id="entries"></div><button class="btn small" type="button" id="addEntry">Add an entry at the top</button><p></p>';
    box.append(fs);
    const draw = () => {
      const wrap = $('#entries'); wrap.innerHTML = '';
      s.entries.forEach((e, i) => {
        const row = document.createElement('div'); row.className = 'sub';
        row.innerHTML = `<div class="row">${field('Version', `<input type="text" data-e="version" maxlength="30" value="${esc(e.version)}">`)}${field('Date', `<input type="text" data-e="date" maxlength="30" value="${esc(e.date)}">`)}</div><div class="notes"></div><div class="btns" style="margin-top:8px"><button class="btn small danger" type="button" data-rm>Remove entry</button></div>`;
        $$('[data-e]', row).forEach(el => el.addEventListener('input', () => { e[el.dataset.e] = el.value; changed(); }));
        $('.notes', row).append(rte(e.notes, v => { e.notes = v; changed(); }, { short: true, label: 'Notes' }));
        $('[data-rm]', row).addEventListener('click', () => { if (confirm('Remove this entry?')) { s.entries.splice(i, 1); changed(); draw(); } });
        wrap.append(row);
      });
    };
    draw();
    $('#addEntry').addEventListener('click', () => { s.entries.unshift({ version: '', date: new Date().toLocaleDateString('en-GB', { ...BD, day: 'numeric', month: 'short', year: 'numeric' }), notes: '' }); changed(); draw(); });
  }
  function plannedEditor(s, box) {
    s.planned = s.planned || [];
    const fs = document.createElement('fieldset');
    fs.innerHTML = '<legend>Upcoming and planned features</legend><p class="hint" style="margin-top:0">Current features are read from the running app; list what is coming here.</p><div id="planned"></div><button class="btn small" type="button" id="addPlan">Add a feature</button><p></p>';
    box.append(fs);
    const draw = () => {
      $('#planned').innerHTML = s.planned.map((p, i) => `<div class="sub" data-i="${i}"><div class="row">
        ${field('Feature', `<input type="text" data-p="name" maxlength="120" value="${esc(p.name)}">`)}
        ${field('Status', `<select data-p="status">${['upcoming', 'planned', 'research'].map(v => `<option ${p.status === v ? 'selected' : ''}>${v}</option>`).join('')}</select>`)}</div>
        ${field('Note', `<input type="text" data-p="note" maxlength="300" value="${esc(p.note)}">`)}
        <div class="btns"><button class="btn small" type="button" data-pm="-1">Move up</button><button class="btn small" type="button" data-pm="1">Move down</button><button class="btn small danger" type="button" data-rm>Remove</button></div></div>`).join('');
      $$('#planned .sub').forEach(row => {
        const i = Number(row.dataset.i), p = s.planned[i];
        $$('[data-p]', row).forEach(el => el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', () => { p[el.dataset.p] = el.value; changed(); }));
        $('[data-rm]', row).addEventListener('click', () => { s.planned.splice(i, 1); changed(); draw(); });
        $$('[data-pm]', row).forEach(b => b.addEventListener('click', () => { const j = i + Number(b.dataset.pm); if (j < 0 || j >= s.planned.length) return; [s.planned[i], s.planned[j]] = [s.planned[j], s.planned[i]]; changed(); draw(); }));
      });
    };
    draw();
    $('#addPlan').addEventListener('click', () => { s.planned.push({ name: '', status: 'planned', note: '' }); changed(); draw(); });
  }
  function renderMeta(pane) {
    const m = S.content.meta;
    pane.innerHTML = `<h2>Page header</h2><p class="hint" style="margin:-8px 0 16px">The top of /docs: what a judge reads first.</p>
      <div class="row">${field('Product name', input('title', m.title, 'maxlength="120"'))}${field('Version label', input('version_label', m.version_label || '', 'maxlength="40"'))}</div>
      ${field('One-line description', `<textarea data-k="tagline" maxlength="240" rows="2">${esc(m.tagline)}</textarea>`)}
      <div class="f"><span style="display:block;font-weight:600;font-size:15px;margin-bottom:5px">30-second summary</span><div id="sumEd"></div></div>
      <div class="row">${field('App link', input('app_url', m.app_url || '/'))}${field('Source code link', input('repo_url', m.repo_url || ''))}</div>`;
    bindInputs(pane, m);
    $('#sumEd').append(rte(m.summary, v => { m.summary = v; changed(); }, { short: true, label: 'Summary' }));
  }

  /* ================= versions + activity ================= */
  async function renderVersions() {
    $('#tab').innerHTML = '<p class="loading">Loading…</p>';
    try {
      const { versions } = await api('GET', '/api/docs/admin/versions');
      const gh = S.info.github;
      $('#tab').innerHTML = `<section class="card"><h2>Published versions on this server</h2><p>${isSuper() ? 'Restoring copies a version into the draft; publish it to make it live.' : 'A Super Admin can restore an older version.'}
        ${gh.enabled ? ` Older versions: the history of <a href="https://github.com/${esc(gh.repo)}/commits/${esc(gh.branch)}/data/docs/content.json" target="_blank" rel="noopener">data/docs/content.json on GitHub</a>.` : ''}</p>
        ${versions.length ? `<table class="plain"><thead><tr><th>Version</th><th>Published</th><th>By</th><th>Note</th><th>Sections</th>${isSuper() ? '<th></th>' : ''}</tr></thead><tbody>
        ${versions.map(v => `<tr><td>${v.version}</td><td>${esc(when(v.published_at))}</td><td>${esc(v.by)}</td><td>${esc(v.note)}</td><td>${v.sections}</td>${isSuper() ? `<td><button class="btn small" data-restore="${v.version}">Restore into draft</button></td>` : ''}</tr>`).join('')}</tbody></table>`
        : '<p class="hint">Nothing has been published from this server yet. /docs shows the content committed in the repository.</p>'}</section>`;
      $$('[data-restore]').forEach(b => b.addEventListener('click', async () => {
        if (!confirm(`Replace the current draft with version ${b.dataset.restore}?`)) return;
        try { await api('POST', `/api/docs/admin/versions/${b.dataset.restore}/restore`, {}); S.content = null; toast(`Version ${b.dataset.restore} is now the draft`); }
        catch (e) { toast(e.message, true); }
      }));
    } catch (e) { $('#tab').innerHTML = `<p class="msg err">${esc(e.message)}</p>`; }
  }
  async function renderActivity() {
    try {
      const { entries } = await api('GET', '/api/docs/admin/audit');
      $('#tab').innerHTML = `<section class="card"><h2>Activity on this server</h2><p>Sign-ins, saves, publishes and visibility changes, newest first.</p>
        ${entries.length ? `<table class="plain"><thead><tr><th>When</th><th>Who</th><th>What</th><th>Detail</th></tr></thead><tbody>${entries.map(e => `<tr><td>${esc(when(e.at))}</td><td>${esc(e.by)}</td><td>${esc(e.action)}</td><td>${esc(e.detail)}</td></tr>`).join('')}</tbody></table>` : '<p class="hint">Nothing yet.</p>'}</section>`;
    } catch (e) { $('#tab').innerHTML = `<p class="msg err">${esc(e.message)}</p>`; }
  }

  /* ================= start ================= */
  async function start() {
    S.info = await api('GET', '/api/docs/admin/me');
    if (!S.info.user) return renderSignIn();
    S.content = null;
    renderShell();
  }
  window.addEventListener('beforeunload', e => { if (S.unsaved) { e.preventDefault(); e.returnValue = ''; } });
  start().catch(e => { app.innerHTML = `<p class="msg err">${esc(e.message)}</p>`; });
})();
