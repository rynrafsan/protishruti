/* Protishruti /docs: renders the published content, then fills the live panels from /api/docs/live. */
(() => {
  'use strict';
  const boot = JSON.parse(document.getElementById('boot').textContent);
  const C = boot.content;
  const META = C.meta || {};
  const SECTIONS = C.sections || [];
  const GROUPS = [['pitch', 'Pitch deck'], ['tech', 'Technical documentation']];
  let LIVE = null, liveError = null, pollTimer = null;

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = n => (n ?? 0).toLocaleString('en-IN');
  const BD = { timeZone: 'Asia/Dhaka' };
  const when = iso => iso ? new Date(iso).toLocaleString('en-GB', { ...BD, day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true }) : '';
  const clock = iso => iso ? new Date(iso).toLocaleTimeString('en-GB', { ...BD, hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
  const dur = s => s < 90 ? `${s} s` : s < 5400 ? `${Math.round(s / 60)} min` : s < 172800 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} days`;
  const ICON = {
    link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7L12 6.3M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg>',
    play: '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>',
  };

  function toast(msg) {
    const t = document.createElement('div');
    t.className = 'toast'; t.setAttribute('role', 'status'); t.textContent = msg;
    document.body.append(t);
    setTimeout(() => t.remove(), 2200);
  }
  async function copy(text, msg) {
    try { await navigator.clipboard.writeText(text); toast(msg); }
    catch { window.prompt('Copy this link:', text); }
  }

  /* ---------------- ribbon for signed-in admins ---------------- */
  function statusText(st) {
    if (st.state === 'open') return st.end ? `Open to the public until ${when(st.end)} (GMT+6).` : 'Open to the public, no end date.';
    if (st.state === 'scheduled') return `Closed to the public. Opens ${when(st.start)} (GMT+6).`;
    if (st.state === 'ended') return `Closed to the public since ${when(st.end)} (GMT+6).`;
    return 'Turned off. Only signed-in admins can see this page.';
  }
  function renderRibbon() {
    if (!boot.admin) return;
    const r = $('#ribbon');
    r.className = 'ribbon' + (boot.preview ? ' draft' : '');
    r.innerHTML = boot.preview
      ? `<span><b>Draft preview.</b> Visitors do not see these changes until you publish.</span><a href="/docs/admin">Back to the editor</a>`
      : `<span>Signed in as ${esc(boot.admin.name)} (${boot.admin.role === 'super' ? 'Super Admin' : 'Admin'}). ${esc(statusText(boot.status))}</span><a href="/docs/admin">Admin panel</a>`;
  }

  /* ---------------- content ---------------- */
  const visible = SECTIONS.filter(s => s.visible !== false);
  const byGroup = g => visible.filter(s => s.group === g);

  function figuresHTML(figs) {
    if (!figs || !figs.length) return '';
    return `<div class="figures">${figs.map(f => `<div class="figure"><b>${esc(f.value)}</b><span>${esc(f.label)}</span>${f.source ? `<a href="${esc(f.source)}">Source</a>` : ''}</div>`).join('')}</div>`;
  }
  function initials(name) {
    return esc(name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase());
  }
  function teamHTML(s) {
    const members = (s.members || []).map(m => `
      <article class="member">
        <span class="photo">${m.photo ? `<img src="${esc(m.photo)}" alt="${esc(m.name)}" width="150" height="200" loading="lazy">` : `<span class="initials" aria-hidden="true">${initials(m.name)}</span>`}</span>
        <b>${esc(m.name)}</b><span class="role">${esc(m.role)}</span>
        ${m.bio ? `<p>${esc(m.bio)}</p>` : ''}
        ${m.email ? `<a href="mailto:${esc(m.email)}">${esc(m.email)}</a>` : ''}
      </article>`).join('');
    return `${s.team_name ? `<p class="team-name">${esc(s.team_name)}</p>` : ''}<div class="team">${members}</div>`;
  }
  function videoHTML(url) {
    const m = (url || '').match(/(?:v=|youtu\.be\/|embed\/)([A-Za-z0-9_-]{11})/);
    if (!m) return '';
    return `<div class="video" data-yt="${m[1]}"><button type="button" style="background-image:url(https://i.ytimg.com/vi/${m[1]}/hqdefault.jpg)" aria-label="Play the pitch video"><span>${ICON.play} Play the video</span></button></div>`;
  }
  function changelogHTML(s) {
    return `<div class="changes">${(s.entries || []).map(e => `<div class="change"><h3>${esc(e.version)}<span>${esc(e.date)}</span></h3><div class="body">${e.notes || ''}</div></div>`).join('')}</div>`;
  }
  function sectionHTML(s) {
    let extra = '';
    if (s.type === 'team') extra = teamHTML(s);
    if (s.type === 'diagram') extra = `<div class="diagram-tools"><span>Diagram</span><span><button type="button" data-act="wide">Full size</button> <button type="button" data-act="source">Source</button></span></div>
      <div class="diagram" data-src="${esc(s.mermaid || '')}"><pre>${esc(s.mermaid || '')}</pre></div>${s.caption ? `<p class="caption">${esc(s.caption)}</p>` : ''}`;
    if (s.type === 'changelog') extra = changelogHTML(s);
    return `<section class="sec ${s.group}" id="${esc(s.id)}" aria-labelledby="h-${esc(s.id)}">
      <h2 id="h-${esc(s.id)}"><button class="anchor" type="button" data-anchor="${esc(s.id)}" aria-label="Copy link to ${esc(s.title)}">${ICON.link}</button>${esc(s.title)}</h2>
      ${s.kicker ? `<p class="kicker">${esc(s.kicker)}</p>` : ''}
      ${figuresHTML(s.figures)}
      ${videoHTML(s.video_url)}
      ${s.body ? `<div class="body">${s.body}</div>` : ''}
      ${extra}
      ${s.live ? `<div class="live" data-live="${esc(s.live)}" data-sec="${esc(s.id)}"><p class="wait">Reading live data from this server…</p></div>` : ''}
    </section>`;
  }
  function heroHTML() {
    const first = g => (byGroup(g)[0] || {}).id;
    const v = C._version ? `Version ${C._version}${C._published_at ? `, published ${when(C._published_at)}` : ''}` : 'Repository default';
    return `<header class="hero" id="top">
      <h1>প্রতিশ্রুতি<small>Protishruti${META.version_label ? ' · ' + esc(META.version_label) : ''}</small></h1>
      <p class="tagline">${esc(META.tagline)}</p>
      <div class="summary">${META.summary || ''}</div>
      <dl class="datapage" aria-label="Facts about this system">
        <div><dt>Documentation</dt><dd>${esc(v)}</dd></div>
        <div><dt>Rules running</dt><dd data-hero="rules">…</dd></div>
        <div><dt>Sourced passages</dt><dd data-hero="passages">…</dd></div>
        <div><dt>Rule benchmark</dt><dd data-hero="bench">…</dd></div>
        <div><dt>Server</dt><dd data-hero="server">…</dd></div>
        <div><dt>Data</dt><dd>Fictional SPECIMEN only</dd></div>
      </dl>
      <p class="entry">${first('pitch') ? `<a href="#${first('pitch')}">Two-minute read <span>the pitch</span></a>` : ''}${first('tech') ? `<a href="#${first('tech')}">Ten-minute evaluation <span>architecture, live data, benchmarks</span></a>` : ''}</p>
    </header>`;
  }
  function render() {
    document.title = `${META.title || 'Protishruti'} — docs`;
    $('#appLink').href = META.app_url || '/';
    let html = heroHTML();
    for (const [g, label] of GROUPS) {
      const list = byGroup(g);
      if (!list.length) continue;
      html += `<p class="group-title" id="group-${g}">${label}</p>` + list.map(sectionHTML).join('');
    }
    html += `<footer class="foot"><span>Legal information, not legal advice.</span>${META.repo_url ? `<a href="${esc(META.repo_url)}">Source code</a>` : ''}<a href="/api/docs">API reference</a><a href="/docs/export.md">Markdown</a><a href="/docs/admin">Admin</a></footer>`;
    $('#doc').innerHTML = html;
    $$('#doc a[href^="http"]').forEach(a => { a.target = '_blank'; a.rel = 'noopener noreferrer'; });
    $$('.body table').forEach(t => { if (!t.parentElement.classList.contains('tablewrap')) { const w = document.createElement('div'); w.className = 'tablewrap'; t.replaceWith(w); w.append(t); } });
    renderRail();
  }

  /* ---------------- rail + scroll spy ---------------- */
  function renderRail() {
    let html = '';
    for (const [g, label] of GROUPS) {
      const list = byGroup(g);
      if (!list.length) continue;
      html += `<h2>${label}</h2><ol>${list.map(s => `<li><a href="#${esc(s.id)}" data-id="${esc(s.id)}">${esc(s.title)}</a></li>`).join('')}</ol>`;
    }
    html += `<p class="meta">${C._version ? `Version ${C._version}` : 'Repository default'}${C._published_at ? ` · ${when(C._published_at)}` : ''}</p>`;
    $('#rail').innerHTML = html;
    const links = new Map($$('#rail a').map(a => [a.dataset.id, a]));
    let current = null;
    const obs = new IntersectionObserver(entries => {
      for (const e of entries) if (e.isIntersecting) {
        if (current) current.removeAttribute('aria-current');
        current = links.get(e.target.id);
        if (current) { current.setAttribute('aria-current', 'true'); current.scrollIntoView({ block: 'nearest' }); }
      }
    }, { rootMargin: '-20% 0px -70% 0px' });
    $$('.sec').forEach(s => obs.observe(s));
    $('#rail').addEventListener('click', e => { if (e.target.closest('a')) closeRail(); });
  }
  function closeRail() { $('#rail').classList.remove('open'); $('#contentsBtn').setAttribute('aria-expanded', 'false'); }
  $('#contentsBtn').addEventListener('click', () => {
    const open = $('#rail').classList.toggle('open');
    $('#contentsBtn').setAttribute('aria-expanded', String(open));
  });

  /* ---------------- live data ---------------- */
  const chip = (st, text) => `<span class="chip st-${esc(st)}">${esc(text || st)}</span>`;
  // rows: arrays of cell HTML; each cell carries its column name so phones can show rows as cards
  const table = (head, rows) => `<div class="tablewrap"><table><thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((c, i) => `<td data-label="${esc(head[i])}">${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  const kv = pairs => `<dl class="kv">${pairs.filter(Boolean).map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join('')}</dl>`;
  const feature = name => (LIVE.features || []).find(f => f.name.startsWith(name)) || {};

  function benchRules() {
    const b = LIVE.benchmarks;
    if (b.state === 'running' || b.state === 'not started') return '<p class="wait">Running the benchmark on this server…</p>';
    if (b.state === 'error') return `<p class="muted">The benchmark could not run here: ${esc(b.error)}</p>`;
    const r = b.rules;
    return `<p>${r.cases} synthetic cases (seed ${r.seed}), one planted mismatch each, run through the rules on this server. Clean cases with a false alarm: <b>${r.false_alarms} of ${r.clean_cases}</b>.</p>
      <div class="bench">${r.per_rule.map(x => `<div class="${x.found < x.cases ? 'miss' : ''}"><b>${esc(x.rule)}</b><span>${x.found}/${x.cases}</span></div>`).join('')}</div>
      ${(() => { const have = new Set(r.per_rule.map(x => x.rule)), miss = Array.from({ length: 12 }, (_, i) => `R${String(i + 1).padStart(2, '0')}`).filter(x => !have.has(x));
        return miss.length ? `<p class="muted">Not in this benchmark yet: ${miss.join(', ')} (the generator plants pre-departure mismatches only).</p>` : ''; })()}`;
  }
  function benchRag() {
    const b = LIVE.benchmarks;
    if (b.state !== 'done') return '';
    const q = b.rag, row = (label, x) => [label, x.questions, `${x.hit1}/${x.questions}`, `${x.hit3}/${x.questions}`, x.mrr.toFixed(2), `${x.key_fact}/${x.questions}`];
    return table(['Question set', 'Questions', 'Right passage first', 'In top 3', 'MRR', 'Key fact in answer'],
      [row('Tuning set', q.tuning), row('Held-out set', q.held_out)]) +
      `<p class="muted">Off-topic questions refused: <b>${q.off_topic.refused} of ${q.off_topic.questions}</b>. Offline answers, no AI calls, about ${q.tuning.ms} ms per question. Measured ${when(b.measured_at)} in ${b.seconds} s.</p>`;
  }
  const RENDER = {
    demo() {
      const s = LIVE.system;
      return kv([['App', `<a href="${esc(META.app_url || '/')}">Open Protishruti</a>`],
        ['Voice notes', esc(feature('Voice note').status === 'live' ? `On · ${s.asr}` : 'Off on this server')],
        ['AI provider', esc(s.ai_key_set ? `${s.ai_provider} · ${s.ai_model}` : 'Offline mode (no AI key)')],
        ['WhatsApp', esc(s.whatsapp ? 'Connected' : 'Built, not connected here')],
        ['API reference', '<a href="/api/docs">/api/docs</a>']]);
    },
    traction() {
      const ev = Object.fromEntries(LIVE.usage.events.map(e => [e.label, e.count]));
      return `<h4>Rule benchmark</h4>${benchRules()}<h4>Rights Q&amp;A evaluation</h4>${benchRag() || '<p class="wait">Running…</p>'}
        <h4>This server since ${esc(when(LIVE.usage.since))}</h4>${kv([['Promise checks', num(ev['Promise checks'])], ['Rights questions', num(ev['Rights questions answered'])], ['Voice notes', num(ev['Voice notes transcribed'])], ['Docs views', num(ev['Docs page views'])]])}`;
    },
    features(sec) {
      const rows = LIVE.features.map(f => [esc(f.name), chip(f.status), esc(f.detail), `<code>${esc(f.module)}</code>`]);
      const planned = (sec.planned || []).map(p => [esc(p.name), chip(p.status), esc(p.note)]);
      return `<h4>Current, as running now</h4>${table(['Feature', 'Status', 'On this server', 'Code'], rows)}
        ${planned.length ? `<h4>Next</h4>${table(['Feature', 'Status', 'Note'], planned)}` : ''}`;
    },
    stack() {
      const s = LIVE.system;
      return kv([['App version', esc(s.version)], ['Commit', esc(s.commit || 'not reported')], ['Host', esc(s.host)], ['Python', esc(s.python)],
        ['AI provider', esc(s.ai_provider)], ['AI model', esc(s.ai_model)], ['Speech model', esc(s.asr || 'off')],
        ['Rights answers', s.rag_generate && s.ai_key_set ? 'AI-written, grounding-checked' : 'Quoted from sources']]);
    },
    api() {
      const rows = LIVE.endpoints.map(e => [`<span class="method ${esc(e.method)}">${esc(e.method)}</span>`, `<span class="path">${esc(e.path)}</span>`, esc(e.description || e.summary), esc(e.auth)]);
      return `<p>${LIVE.endpoints.length} endpoints, read from the app's OpenAPI schema. Try them at <a href="/api/docs">/api/docs</a>.</p>${table(['Method', 'Path', 'What it does', 'Auth'], rows)}`;
    },
    data() {
      const k = LIVE.knowledge;
      return kv([['Knowledge-base passages', num(k.passages)], ['Files', num(k.files.length)], ['Suggested questions', num(k.faq)],
        ['Contextual retrieval', k.contextual ? 'On (AI-written context per passage)' : 'Headings only'],
        ['Fee caps', `${k.fee_countries} countries, as of ${esc(k.fee_as_of)}`], ['Agency list', `${k.agencies} entries (sample)`],
        ['Watchlist corridors', num(k.watchlist)], ['Search vocabulary', `${num(k.vocab)} character n-grams`]]) +
        `<h4>Knowledge-base files</h4>${table(['File', 'Passages'], k.files.map(f => [`<span lang="bn">${esc(f.title)}</span>`, f.passages]))}`;
    },
    ai() {
      return `<h4>Rule benchmark</h4>${benchRules()}<h4>Retrieval and answers</h4>${benchRag() || '<p class="wait">Running…</p>'}`;
    },
    performance() {
      const u = LIVE.usage;
      const rows = u.routes.slice(0, 10).map(r => [`<span class="method ${esc(r.method)}">${esc(r.method)}</span> <span class="path">${esc(r.path)}</span>`, num(r.count), r.p50_ms ?? '–', r.p95_ms ?? '–', r.errors]);
      const b = LIVE.benchmarks;
      return kv([['Up for', dur(u.uptime_s)], ['Requests served', num(u.requests)], ['Server errors', num(u.server_errors)],
        ['Offline rights answer', b.state === 'done' ? `${b.rag.tuning.ms} ms per question` : '…']]) +
        (rows.length ? `<h4>Response times on this server (milliseconds)</h4>${table(['Route', 'Requests', 'Median', '95th percentile', 'Errors'], rows)}` : '<p class="muted">No requests counted yet.</p>');
    },
    security() {
      const s = LIVE.system;
      return kv([['Real personal data', s.allow_real_data ? 'Allowed' : 'Not allowed (SPECIMEN only)'], ['User accounts', `${s.accounts} (by design)`],
        ['AI key', s.ai_key_set ? 'Set in the server environment' : 'Not set'], ['Promise Record chain', s.chain_valid ? 'Intact' : 'Broken'],
        ['Docs admin sign-in', s.admin_signin ? 'Enabled' : 'Disabled (no password set)']]);
    },
    analytics() {
      const u = LIVE.usage;
      const rows = u.events.map(e => [esc(e.label), num(e.count)]);
      return `<p>Since ${esc(when(u.since))} (up ${dur(u.uptime_s)}): ${num(u.requests)} requests, ${num(u.server_errors)} server errors.</p>${table(['Event', 'Count'], rows)}`;
    },
    summary() { return ''; },
  };
  function fillLive() {
    for (const box of $$('[data-live]')) {
      const kind = box.dataset.live, sec = SECTIONS.find(s => s.id === box.dataset.sec) || {};
      let inner;
      if (liveError && !LIVE) inner = `<p class="muted">Live data could not be loaded: ${esc(liveError)}</p>`;
      else if (!LIVE) continue;
      else { try { inner = (RENDER[kind] || (() => ''))(sec); } catch (e) { inner = `<p class="muted">Could not show this panel: ${esc(e.message)}</p>`; } }
      box.innerHTML = `<div class="live-head"><b><span class="pulse" aria-hidden="true"></span>Live from this server</b><span>${LIVE ? 'Updated ' + clock(LIVE.generated_at) : ''}</span></div>${inner}`;
      $$('a[href^="http"]', box).forEach(a => { a.target = '_blank'; a.rel = 'noopener noreferrer'; });
    }
    if (LIVE) {
      const f = LIVE.features.find(x => x.name.startsWith('Rules engine'));
      const set = (k, v) => { const d = $(`[data-hero="${k}"]`); if (d) d.innerHTML = v; };
      set('rules', f ? esc(f.name.match(/\d+/)[0]) + ' (R01–R12)' : '–');
      set('passages', `${num(LIVE.knowledge.passages)} in ${LIVE.knowledge.files.length} files`);
      const b = LIVE.benchmarks;
      if (b.state === 'done') {
        const found = b.rules.per_rule.reduce((a, x) => a + x.found, 0), total = b.rules.per_rule.reduce((a, x) => a + x.cases, 0);
        set('bench', `${found}/${total} found, ${b.rules.false_alarms} false alarms`);
      } else set('bench', b.state === 'error' ? 'Not available' : 'Running…');
      set('server', `<span class="dot" aria-hidden="true"></span>Up ${dur(LIVE.usage.uptime_s)} · ${esc(LIVE.system.host)}`);
    }
  }
  async function loadLive() {
    try {
      const r = await fetch('/api/docs/live', { headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!r.ok) throw new Error(r.status === 403 ? 'the docs are closed right now' : `server answered ${r.status}`);
      LIVE = await r.json(); liveError = null;
    } catch (e) { liveError = e.message; }
    fillLive();
    clearTimeout(pollTimer);
    const busy = LIVE && LIVE.benchmarks && LIVE.benchmarks.state === 'running';
    pollTimer = setTimeout(() => { if (!document.hidden) loadLive(); else document.addEventListener('visibilitychange', loadLive, { once: true }); }, busy ? 2500 : 30000);
  }

  /* ---------------- diagrams (Mermaid, loaded only when one scrolls into view) ---------------- */
  let mermaidP = null, diagramN = 0;
  function mermaid() {
    mermaidP = mermaidP || import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs').then(m => {
      m.default.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'base', fontFamily: 'Hind Siliguri, system-ui, sans-serif',
        themeVariables: { primaryColor: '#F8FAF7', primaryBorderColor: '#1B6B53', primaryTextColor: '#1F2D28', lineColor: '#586A63',
          secondaryColor: '#F3E8C8', tertiaryColor: '#EEF4F0', clusterBkg: '#EEF4F0', clusterBorder: '#B9C9C0', fontSize: '15px',
          fontFamily: 'Hind Siliguri, system-ui, sans-serif' },
        flowchart: { curve: 'basis', htmlLabels: true, padding: 12 } });
      return m.default;
    });
    return mermaidP;
  }
  async function drawDiagram(box) {
    if (box.dataset.done) return;
    box.dataset.done = '1';
    try {
      const m = await mermaid();
      const { svg } = await m.render(`dgm-${++diagramN}`, box.dataset.src);
      box.innerHTML = svg;
    } catch (e) {
      box.insertAdjacentHTML('afterbegin', `<p class="muted">The diagram drawing library did not load (${esc(e.message || 'offline')}); its source is shown instead.</p>`);
    }
  }
  function watchDiagrams() {
    const obs = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { drawDiagram(e.target); obs.unobserve(e.target); } }), { rootMargin: '300px' });
    $$('.diagram').forEach(d => obs.observe(d));
  }
  const drawAll = () => Promise.all($$('.diagram').map(drawDiagram));

  /* ---------------- search ---------------- */
  const q = $('#q'), results = $('#results');
  let sel = -1;
  const PARTS = 'h2, .kicker, .figure, .body, .live, .team, .changes > .change > h3, .caption';
  function sectionText(sec) {
    return $$(PARTS, sec).filter(e => !e.parentElement.closest('.body, .live')).map(e => e.innerText).join(' \n ').replace(/[ \t]+/g, ' ');
  }
  function search(term) {
    const words = term.toLowerCase().split(/\s+/).filter(w => w.length > 1);
    if (!words.length) return [];
    const re = w => new RegExp((/^[a-z0-9]/.test(w) ? '(^|[^a-z0-9])' : '') + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    const out = [];
    for (const sec of $$('.sec')) {
      const title = $('h2', sec).innerText, kicker = $('.kicker', sec)?.innerText || '';
      const text = sectionText(sec), flat = text.replace(/\s*\n\s*/g, ' · ');
      if (!words.every(w => re(w).test(text))) continue;
      let score = flat.toLowerCase().includes(words.join(' ')) ? 6 : 0;
      for (const w of words) score += (re(w).test(title) ? 12 : 0) + (re(w).test(kicker) ? 4 : 0) + Math.min(8, (text.match(re(w)) || []).length);
      const m = re(words[0]).exec(flat), at = m ? m.index : 0, start = Math.max(0, at - 50);
      let snip = esc((start ? '…' : '') + flat.slice(start, at + 120) + '…');
      for (const w of words) snip = snip.replace(re(w), x => x.replace(/^([^a-z0-9]?)(.*)$/is, (_, pre, word) => `${pre}<mark>${word}</mark>`));
      out.push({ id: sec.id, title, snip, score });
    }
    return out.sort((a, b) => b.score - a.score).slice(0, 8);
  }
  function showResults() {
    const term = q.value.trim();
    if (!term) { results.hidden = true; q.setAttribute('aria-expanded', 'false'); return; }
    const hits = search(term);
    sel = hits.length ? 0 : -1;
    results.innerHTML = hits.length ? hits.map((h, i) => `<a href="#${esc(h.id)}" role="option" aria-selected="${i === 0}"><b>${esc(h.title)}</b><span>${h.snip}</span></a>`).join('')
      : `<p>Nothing found for “${esc(term)}”.</p>`;
    results.hidden = false; q.setAttribute('aria-expanded', 'true');
  }
  q.addEventListener('input', showResults);
  q.addEventListener('keydown', e => {
    const items = $$('a', results);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!items.length) return;
      sel = (sel + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      items.forEach((a, i) => a.setAttribute('aria-selected', String(i === sel)));
    } else if (e.key === 'Enter' && items[sel]) { e.preventDefault(); items[sel].click(); }
    else if (e.key === 'Escape') { q.value = ''; showResults(); q.blur(); }
  });
  results.addEventListener('click', e => {
    const a = e.target.closest('a');
    if (!a) return;
    results.hidden = true;
    const target = document.getElementById(a.getAttribute('href').slice(1));
    if (target) setTimeout(() => { target.setAttribute('tabindex', '-1'); target.focus({ preventScroll: true }); }, 50);
  });
  document.addEventListener('click', e => { if (!e.target.closest('.search')) results.hidden = true; });

  /* ---------------- export menu ---------------- */
  const exportBtn = $('#exportBtn'), exportMenu = $('#exportMenu');
  const shareURL = () => location.origin + '/docs' + location.hash;
  exportBtn.addEventListener('click', () => { exportMenu.hidden = !exportMenu.hidden; exportBtn.setAttribute('aria-expanded', String(!exportMenu.hidden)); });
  document.addEventListener('click', e => { if (!e.target.closest('.menu')) { exportMenu.hidden = true; exportBtn.setAttribute('aria-expanded', 'false'); } });
  exportMenu.addEventListener('click', async e => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (!act) return;
    exportMenu.hidden = true;
    if (act === 'pdf') { toast('Preparing diagrams…'); await drawAll(); setTimeout(() => window.print(), 300); }
    if (act === 'link') copy(shareURL(), 'Link copied');
  });

  /* ---------------- section actions ---------------- */
  $('#doc').addEventListener('click', e => {
    const anchor = e.target.closest('[data-anchor]');
    if (anchor) { history.replaceState(null, '', '#' + anchor.dataset.anchor); copy(shareURL(), 'Link to this section copied'); return; }
    const tool = e.target.closest('.diagram-tools button');
    if (tool) {
      const box = tool.closest('.sec').querySelector('.diagram');
      if (tool.dataset.act === 'wide') { const w = box.classList.toggle('wide'); tool.textContent = w ? 'Fit to width' : 'Full size'; }
      if (tool.dataset.act === 'source') {
        const showing = box.dataset.showSource === '1';
        if (showing) { box.dataset.done = ''; box.dataset.showSource = ''; drawDiagram(box); tool.textContent = 'Source'; }
        else { box.innerHTML = `<pre>${esc(box.dataset.src)}</pre>`; box.dataset.showSource = '1'; tool.textContent = 'Diagram'; }
      }
      return;
    }
    const play = e.target.closest('.video button');
    if (play) {
      const v = play.parentElement;
      v.innerHTML = `<iframe src="https://www.youtube-nocookie.com/embed/${v.dataset.yt}?autoplay=1&rel=0" title="Pitch video" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>`;
    }
  });

  /* ---------------- present mode ---------------- */
  let slides = [], at = 0, presentEl = null, lastFocus = null;
  function buildSlides() {
    const pitch = byGroup('pitch');
    slides = [{ cover: true }].concat(pitch);
  }
  function slideHTML(i) {
    const s = slides[i];
    if (s.cover) return `<div class="slide title" tabindex="-1"><h1>প্রতিশ্রুতি</h1><p>${esc(META.tagline)}</p><p class="count" style="margin-top:28px">Protishruti${META.version_label ? ' · ' + esc(META.version_label) : ''}</p></div>`;
    let extra = '';
    if (s.type === 'team') extra = teamHTML(s);
    if (s.live === 'traction' && LIVE) extra += `<div class="live">${RENDER.traction()}</div>`;
    return `<div class="slide" tabindex="-1" aria-label="${esc(s.title)}"><h2>${esc(s.title)}</h2>
      ${s.kicker ? `<p class="big">${esc(s.kicker)}</p>` : ''}${figuresHTML(s.figures)}${s.body ? `<div class="body">${s.body}</div>` : ''}${extra}</div>`;
  }
  function showSlide(i) {
    at = Math.max(0, Math.min(slides.length - 1, i));
    presentEl.querySelector('.stage').innerHTML = slideHTML(at);
    presentEl.querySelector('.bar i').style.width = `${(at / (slides.length - 1)) * 100}%`;
    presentEl.querySelector('.pos').textContent = `${at + 1} of ${slides.length}`;
    presentEl.querySelector('.slide').focus();
  }
  function openPresent(start = 0) {
    buildSlides();
    lastFocus = document.activeElement;
    presentEl = document.createElement('div');
    presentEl.className = 'present';
    presentEl.setAttribute('role', 'dialog'); presentEl.setAttribute('aria-modal', 'true'); presentEl.setAttribute('aria-label', 'Pitch presentation');
    presentEl.innerHTML = `<div class="stage" style="display:grid;min-height:0"></div><div class="controls"><button data-p="prev" aria-label="Previous slide">←</button><span class="pos"></span><span class="bar"><i></i></span><button data-p="next" aria-label="Next slide">→</button><button data-p="full">Full screen</button><button data-p="close">Exit</button></div>`;
    document.body.append(presentEl);
    document.body.style.overflow = 'hidden';
    presentEl.addEventListener('click', e => {
      const p = e.target.closest('[data-p]')?.dataset.p;
      if (p === 'prev') showSlide(at - 1);
      if (p === 'next') showSlide(at + 1);
      if (p === 'full') document.fullscreenElement ? document.exitFullscreen() : presentEl.requestFullscreen?.();
      if (p === 'close') closePresent();
    });
    showSlide(start);
  }
  function closePresent() {
    if (!presentEl) return;
    if (document.fullscreenElement) document.exitFullscreen();
    presentEl.remove(); presentEl = null; document.body.style.overflow = '';
    (lastFocus || $('#presentBtn')).focus();
  }
  $('#presentBtn').addEventListener('click', () => openPresent(0));
  document.addEventListener('keydown', e => {
    if (presentEl) {
      if (['ArrowRight', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); showSlide(at + 1); }
      else if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); showSlide(at - 1); }
      else if (e.key === 'Home') showSlide(0);
      else if (e.key === 'End') showSlide(slides.length - 1);
      else if (e.key === 'Escape' && !document.fullscreenElement) closePresent();
      else if (e.key === 'f') document.fullscreenElement ? document.exitFullscreen() : presentEl.requestFullscreen?.();
      return;
    }
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
    if (e.key === '/' && !typing) { e.preventDefault(); q.focus(); }
    if (e.key === 'Escape') closeRail();
  });

  /* ---------------- start ---------------- */
  renderRibbon();
  render();
  watchDiagrams();
  loadLive();
  if (location.hash === '#present') openPresent(0);
  else if (location.hash) { const t = document.getElementById(decodeURIComponent(location.hash.slice(1))); if (t) setTimeout(() => t.scrollIntoView(), 0); }
})();
