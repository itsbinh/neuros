local OVERLAY_HTML = [[
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy"
      content="default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; connect-src *;">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root {
    --panel-bg: #ffffff;
    --text: #1d1d1f;
    --muted: rgba(0,0,0,0.38);
    --muted-soft: rgba(0,0,0,0.25);
    --hover: rgba(0,0,0,0.07);
    --active: rgba(0,0,0,0.12);
    --accent: #6366f1;
    --accent-hover: #4f46e5;
    --danger: #ef4444;
    --code-bg: rgba(0,0,0,0.055);
    --border: rgba(0,0,0,0.1);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --panel-bg: #1c1c1e;
      --text: #f5f5f7;
      --muted: rgba(255,255,255,0.42);
      --muted-soft: rgba(255,255,255,0.28);
      --hover: rgba(255,255,255,0.08);
      --active: rgba(255,255,255,0.14);
      --accent: #818cf8;
      --accent-hover: #a5b4fc;
      --danger: #f87171;
      --code-bg: rgba(255,255,255,0.09);
      --border: rgba(255,255,255,0.12);
    }
  }
  html, body {
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont,
                 "SF Pro Text", "Helvetica Neue", sans-serif;
    -webkit-font-smoothing: antialiased;
    width: 100%; height: 100%;
  }
  #panel {
    background: var(--panel-bg);
    border-radius: 16px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    -webkit-app-region: drag;
  }
  #input-card {
    -webkit-app-region: no-drag;
  }
  #query {
    width: 100%;
    min-height: 76px;
    background: transparent;
    border: none;
    outline: none;
    resize: none;
    color: var(--text);
    font-size: 16px;
    font-weight: 400;
    line-height: 1.55;
    padding: 18px 18px 10px;
    caret-color: var(--accent);
    font-family: inherit;
    -webkit-app-region: no-drag;
    display: block;
  }
  #query::placeholder { color: var(--muted-soft); }
  #query:disabled { opacity: 0.45; }
  #toolbar {
    display: flex;
    align-items: center;
    height: 46px;
    padding: 0 8px;
    gap: 2px;
    flex-shrink: 0;
    background: transparent;
    -webkit-app-region: drag;
  }
  .ibtn {
    display: flex; align-items: center; justify-content: center;
    width: 32px; height: 32px;
    border-radius: 8px; border: none;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    transition: color 0.12s, background 0.12s;
    flex-shrink: 0;
    -webkit-app-region: no-drag;
  }
  .ibtn:hover {
    color: var(--text);
    background: var(--hover);
  }
  .ibtn:active { background: var(--active); }
  #toolbar-right {
    margin-left: auto;
    display: flex; align-items: center; gap: 6px;
    -webkit-app-region: no-drag;
  }
  #model-select {
    width: 138px;
    height: 30px;
    margin-left: 4px;
    padding: 0 24px 0 8px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--panel-bg);
    color: var(--muted);
    font: 500 11px/1 -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    outline: none;
    cursor: pointer;
    -webkit-app-region: no-drag;
  }
  #model-select:hover,
  #model-select:focus {
    color: var(--text);
    background: var(--hover);
  }
  #spinner {
    display: none;
    width: 14px; height: 14px;
    font-size: 0;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: border-spin 0.72s linear infinite;
  }
  @keyframes border-spin { to { transform: rotate(360deg); } }
  #status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--muted-soft);
    border: 1px solid var(--border);
    flex-shrink: 0;
  }
  #status-dot[data-state="online"] { background: #22c55e; border-color: rgba(34,197,94,0.55); }
  #status-dot[data-state="offline"] { background: var(--danger); border-color: rgba(239,68,68,0.55); }
  #btn-send {
    width: 32px; height: 32px;
    border-radius: 50%;
    background: var(--accent);
    color: #fff;
    border: none; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: transform 0.1s, background 0.12s;
    flex-shrink: 0;
    -webkit-app-region: no-drag;
  }
  #btn-send:hover { background: var(--accent-hover); transform: scale(1.05); }
  #btn-send:active { transform: scale(0.95); }
  #btn-send:disabled {
    background: rgba(99,102,241,0.3);
    cursor: not-allowed;
    transform: none;
  }
  #btn-send[data-mode="stop"] { background: var(--danger); }
  #btn-send[data-mode="stop"]:hover { background: #dc2626; transform: scale(1.05); }
  #btn-send[data-mode="stop"]:active { transform: scale(0.95); }
  #btn-mic {
    width: 32px; height: 32px;
    border-radius: 50%;
    background: transparent;
    color: var(--muted);
    border: none; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: transform 0.1s, background 0.12s, color 0.12s;
    flex-shrink: 0;
    -webkit-app-region: no-drag;
  }
  #btn-mic:hover { background: var(--hover); transform: scale(1.05); }
  #btn-mic:active { transform: scale(0.95); }
  #btn-mic.active {
    background: rgba(239,68,68,0.12);
    color: var(--danger);
  }
  #btn-mic.active:hover { background: rgba(239,68,68,0.18); }
  #resp-wrap {
    display: none;
    padding: 12px 18px 4px;
    background: var(--panel-bg);
    overflow-y: auto;
  }
  #resp-wrap::-webkit-scrollbar { width: 3px; }
  #resp-wrap::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 2px;
  }
  #messages {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .msg {
    color: var(--text);
    font-size: 14px;
    line-height: 1.65;
    word-break: break-word;
  }
  .msg.user {
    color: var(--muted);
    font-size: 12px;
    line-height: 1.45;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }
  .msg.assistant.err { color: #dc2626; }
  .msg p { margin: 0 0 9px; }
  .msg p:last-child { margin-bottom: 0; }
  .msg ul { margin: 0 0 9px 18px; }
  .msg li { margin: 2px 0; }
  .msg pre {
    margin: 8px 0;
    padding: 10px 12px;
    border-radius: 8px;
    background: var(--code-bg);
    border: 1px solid var(--border);
    overflow-x: auto;
    white-space: pre;
  }
  .msg code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 12px;
  }
  .msg p code {
    background: var(--code-bg);
    border-radius: 5px;
    padding: 1px 4px;
  }
  #hint {
    display: block;
    padding: 0 18px 12px;
    color: var(--muted-soft);
    font-size: 11px;
    line-height: 1.3;
  }
  #meta-row {
    display: none;
    padding: 6px 18px 14px;
    gap: 5px; flex-wrap: wrap; align-items: center;
  }
  .sbadge {
    background: rgba(99,102,241,0.08);
    color: rgba(99,102,241,0.9);
    font-size: 11px; font-weight: 500;
    padding: 2px 8px; border-radius: 10px;
    border: 1px solid rgba(99,102,241,0.2);
  }
  .mbadge { color: var(--muted-soft); font-size: 11px; }
  .lbadge { color: var(--muted-soft); font-size: 11px; margin-left: auto; }
</style>
</head>
<body>
<div id="panel">

  <div id="input-card">
    <textarea id="query"
      placeholder="Type your message here..."
      autocomplete="off" autocorrect="off"
      autocapitalize="off" spellcheck="false"
      rows="3"></textarea>
  </div>

  <div id="toolbar">
    <!-- left: attach + web -->
    <button class="ibtn" id="btn-attach" title="Attach file">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
        <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19
                 a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
      </svg>
    </button>
    <button class="ibtn" id="btn-web" title="Web search">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
        <circle cx="12" cy="12" r="10"/>
        <path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0
                 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/>
      </svg>
    </button>
    <select id="model-select" title="Model"></select>

    <!-- right: spinner + mic + send -->
    <div id="toolbar-right">
      <span id="status-dot" title="Agent status"></span>
      <span id="spinner">◐</span>
      <button id="btn-mic" title="Voice input">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
          <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/>
          <path d="M19 10v2a7 7 0 01-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="23"/>
          <line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
      </button>
      <button id="btn-send" title="Send (Enter)">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2.5" stroke-linecap="round"
             stroke-linejoin="round">
          <line x1="12" y1="19" x2="12" y2="5"/>
          <polyline points="5 12 12 5 19 12"/>
        </svg>
      </button>
    </div>
  </div>

  <div id="resp-wrap"><div id="messages"></div></div>
  <div id="meta-row"></div>
  <div id="hint">Enter sends · Shift+Enter newline · ↑/↓ history · ⌘K clears</div>

</div>
<script>
  const AGENT_URL  = 'http://localhost:8080';
  const SESSION_ID = localStorage.getItem('neuros.sessionId') || (() => {
    const id = 'overlay-' + Date.now();
    localStorage.setItem('neuros.sessionId', id);
    return id;
  })();

  const q       = document.getElementById('query');
  const spin    = document.getElementById('spinner');
  const rwrap   = document.getElementById('resp-wrap');
  const messages = document.getElementById('messages');
  const meta    = document.getElementById('meta-row');
  const btnSend = document.getElementById('btn-send');
  const btnMic  = document.getElementById('btn-mic');
  const statusDot = document.getElementById('status-dot');
  const modelSelect = document.getElementById('model-select');
  const hint = document.getElementById('hint');

  const SEND_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>`;
  const STOP_SVG = `<svg width="11" height="11" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2.5" fill="currentColor"/></svg>`;

  // JS-side history
  let _hist = [], _histIdx = 0;

  function startSpin() { spin.style.display = 'inline-block'; }
  function stopSpin() { spin.style.display = 'none'; }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[ch]));
  }

  function inlineMarkdown(s) {
    return escapeHtml(s)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  }

  function renderMarkdown(src) {
    const parts = [];
    let last = 0;
    const fence = /```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/g;
    let match;
    while ((match = fence.exec(src)) !== null) {
      parts.push({ type: 'text', value: src.slice(last, match.index) });
      parts.push({ type: 'code', lang: match[1] || '', value: match[2] });
      last = fence.lastIndex;
    }
    parts.push({ type: 'text', value: src.slice(last) });

    return parts.map(part => {
      if (part.type === 'code') {
        const lang = part.lang ? ` class="language-${escapeHtml(part.lang)}"` : '';
        return `<pre><code${lang}>${escapeHtml(part.value)}</code></pre>`;
      }
      const blocks = part.value.split(/\n{2,}/).filter(b => b.trim() !== '');
      return blocks.map(block => {
        const lines = block.split('\n');
        if (lines.every(line => /^\s*[-*]\s+/.test(line))) {
          return '<ul>' + lines.map(line => `<li>${inlineMarkdown(line.replace(/^\s*[-*]\s+/, ''))}</li>`).join('') + '</ul>';
        }
        return '<p>' + lines.map(inlineMarkdown).join('<br>') + '</p>';
      }).join('');
    }).join('');
  }

  function addMessage(role, text) {
    const el = document.createElement('div');
    el.className = 'msg ' + role;
    el.innerHTML = role === 'assistant' ? renderMarkdown(text || '') : escapeHtml(text || '');
    messages.appendChild(el);
    rwrap.style.display = 'block';
    hint.style.display = 'none';
    return el;
  }

  async function refreshHealth() {
    try {
      const resp = await fetch(AGENT_URL + '/health', { cache: 'no-store' });
      statusDot.dataset.state = resp.ok ? 'online' : 'offline';
      statusDot.title = resp.ok ? 'Agent online' : 'Agent offline';
      if (resp.ok && modelSelect.disabled) loadModels();
    } catch (e) {
      statusDot.dataset.state = 'offline';
      statusDot.title = 'Agent offline: ' + e.name + ': ' + e.message;
    }
  }

  function selectedModelName() {
    return modelSelect.value || null;
  }

  async function loadModels() {
    try {
      const resp = await fetch(AGENT_URL + '/models', { cache: 'no-store' });
      if (!resp.ok) throw new Error('models unavailable');
      const models = await resp.json();
      modelSelect.innerHTML = '';
      const saved = localStorage.getItem('neuros.modelName') || '';
      let selected = '';
      models.forEach(model => {
        const opt = document.createElement('option');
        opt.value = model.name;
        opt.textContent = model.name;
        modelSelect.appendChild(opt);
        if (model.name === saved || (!selected && model.default)) selected = model.name;
      });
      if (selected) modelSelect.value = selected;
      modelSelect.disabled = models.length === 0;
    } catch {
      modelSelect.innerHTML = '<option value="">default</option>';
      modelSelect.disabled = true;
    }
  }

  function restoreSendBtn() {
    btnSend.innerHTML = SEND_SVG;
    delete btnSend.dataset.mode;
    btnSend.disabled = false;
  }

  function hideResp() {
    rwrap.style.display = 'none';
    messages.innerHTML = '';
    meta.style.display = 'none';
    meta.innerHTML = '';
    hint.style.display = 'block';
    window.__n_msg = { type: 'resize', body: '160' };
  }

  function setInputValue(val) { q.value = val; q.focus(); }
  function appendInputValue(val) {
    const prefix = q.value && !q.value.endsWith('\n') ? '\n' : '';
    q.value = q.value + prefix + val;
    focusInput();
  }
  function appendAttachment(name, content) {
    appendInputValue(`Attached file: ${name}\n\n\`\`\`\n${content}\n\`\`\``);
  }
  function focusInput() {
    q.focus();
    q.selectionStart = q.selectionEnd = q.value.length;
  }

  let _abort = null;

  async function doSubmit() {
    const v = q.value.trim();
    if (!v || _abort) return;

    _hist.push(v);
    _histIdx = _hist.length;

    q.disabled = true;
    q.value = '';
    q.placeholder = v.length > 60 ? v.slice(0, 57) + '…' : v;
    startSpin();
    btnSend.innerHTML = STOP_SVG;
    btnSend.dataset.mode = 'stop';

    addMessage('user', v);
    const assistantEl = addMessage('assistant', '');
    meta.style.display = 'none';
    meta.innerHTML = '';

    _abort = new AbortController();
    let modelUsed = '', latencyMs = 0, skillUsed = '', fullText = '';

    try {
      await refreshHealth();
      if (statusDot.dataset.state === 'offline') throw new Error('Agent offline');

      const body = JSON.stringify({
        text: v,
        session_id: SESSION_ID,
        model_name: selectedModelName(),
      });

      const resp = await fetch(AGENT_URL + '/query/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        signal: _abort.signal,
      });
      if (!resp.ok) throw new Error('Agent returned ' + resp.status);

      // WKWebView's ReadableStream support over HTTP is unreliable — if
      // resp.body is missing, fall back to reading the whole text and parsing
      // SSE frames at once.
      if (!resp.body || typeof resp.body.getReader !== 'function') {
        const text = await resp.text();
        for (const line of text.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          let evt; try { evt = JSON.parse(line.slice(6)); } catch { continue; }
          if (evt.token !== undefined) fullText += evt.token;
          if (evt.done) {
            modelUsed = evt.model || '';
            latencyMs = evt.latency_ms || 0;
            skillUsed = evt.skill_used || '';
          }
        }
        assistantEl.innerHTML = renderMarkdown(fullText);
      } else {
        const reader = resp.body.getReader();
        const dec = new TextDecoder();
        let buf = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          const lines = buf.split('\n');
          buf = lines.pop();
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            let evt; try { evt = JSON.parse(line.slice(6)); } catch { continue; }
            if (evt.token !== undefined) {
              fullText += evt.token;
              assistantEl.innerHTML = renderMarkdown(fullText);
              rwrap.scrollTop = rwrap.scrollHeight;
            }
            if (evt.done) {
              modelUsed = evt.model || '';
              latencyMs = evt.latency_ms || 0;
              skillUsed = evt.skill_used || '';
            }
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        assistantEl.textContent =
          'Error: ' + e.name + ': ' + e.message +
          ' (origin=' + location.origin + ')';
        assistantEl.className = 'msg assistant err';
      }
    }

    _abort = null;
    stopSpin();
    restoreSendBtn();
    q.disabled = false;
    q.placeholder = 'Type your message here...';

    meta.innerHTML = '';
    let hasMeta = false;
    if (skillUsed) {
      const s = document.createElement('span');
      s.className = 'sbadge';
      s.textContent = skillUsed;
      meta.appendChild(s); hasMeta = true;
    }
    if (modelUsed) {
      const m = document.createElement('span');
      m.className = 'mbadge';
      m.textContent = modelUsed.split('/').pop();
      meta.appendChild(m); hasMeta = true;
    }
    if (latencyMs) {
      const l = document.createElement('span');
      l.className = 'lbadge';
      l.textContent = latencyMs + ' ms';
      meta.appendChild(l); hasMeta = true;
    }
    if (hasMeta) meta.style.display = 'flex';

    window.__n_msg = { type: 'resize', body: String(document.getElementById('panel').scrollHeight) };
    setTimeout(() => q.focus(), 40);
  }

  function doStop() {
    if (_abort) {
      _abort.abort();
      _abort = null;
      stopSpin();
      restoreSendBtn();
      q.disabled = false;
      q.placeholder = 'Type your message here...';
      q.focus();
    }
  }

  q.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSubmit(); return; }
    if (e.key === 'Escape') { e.preventDefault(); window.__n_msg = { type: 'dismiss', body: '' }; return; }
    if (e.key === 'ArrowUp' && q.value === '') {
      e.preventDefault();
      if (_histIdx > 0) { _histIdx--; q.value = _hist[_histIdx] || ''; }
      return;
    }
    if (e.key === 'ArrowDown' && q.value === '') {
      e.preventDefault();
      if (_histIdx < _hist.length - 1) { _histIdx++; q.value = _hist[_histIdx] || ''; }
      else { _histIdx = _hist.length; q.value = ''; }
      return;
    }
  });

  document.addEventListener('keydown', function(e) {
    if ((e.metaKey && e.key === 'k') || (e.ctrlKey && e.key === 'c')) {
      e.preventDefault();
      hideResp(); q.value = ''; q.placeholder = 'Type your message here...'; q.focus();
    }
    if (e.key === 'Escape') { e.preventDefault(); window.__n_msg = { type: 'dismiss', body: '' }; }
  });

  btnSend.addEventListener('click', function() {
    if (this.dataset.mode === 'stop') doStop(); else doSubmit();
  });

  document.getElementById('btn-attach').addEventListener('click', () => {
    window.__n_msg = { type: 'attach', body: '' };
  });

  document.getElementById('btn-web').addEventListener('click', () => {
    const v = q.value.trim();
    q.value = v.startsWith('search:') ? v : 'search: ' + v;
    doSubmit();
  });

  modelSelect.addEventListener('change', () => {
    if (modelSelect.value) localStorage.setItem('neuros.modelName', modelSelect.value);
    q.focus();
  });

  let recognition = null;
  btnMic.addEventListener('click', function() {
    if (recognition) { recognition.stop(); return; }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { btnMic.classList.toggle('active'); window.__n_msg = { type: 'mic', body: '' }; return; }
    recognition = new SR();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    recognition.onstart = () => btnMic.classList.add('active');
    recognition.onresult = (e) => {
      const t = Array.from(e.results).map(r => r[0].transcript).join('');
      if (t) { q.value += (q.value && !q.value.endsWith(' ') ? ' ' : '') + t; q.focus(); }
    };
    recognition.onend = () => { btnMic.classList.remove('active'); recognition = null; };
    recognition.onerror = () => {
      btnMic.classList.remove('active'); recognition = null;
      window.__n_msg = { type: 'mic', body: '' };
    };
    recognition.start();
  });

  refreshHealth();
  loadModels();
  setInterval(refreshHealth, 10000);
  setTimeout(() => q.focus(), 50);
</script>
</body>
</html>
]]

local AGENT_URL = "http://localhost:8080"  -- used by health poll only

local PANEL_W     = 620
local PANEL_H_MIN = 160
local PANEL_H_MAX = 560

local wv        = nil
local isVisible = false
local dragState = nil

local function panelFrame(h)
    h = h or PANEL_H_MIN
    local sf = hs.screen.mainScreen():frame()
    return {
        x = sf.x + math.floor((sf.w - PANEL_W) / 2),
        y = sf.y + math.floor((sf.h - h) / 2),
        w = PANEL_W,
        h = h
    }
end

local function appendInputValue(text)
    if not wv then return end
    wv:evaluateJavaScript('appendInputValue(' .. hs.json.encode(text or "") .. ')')
end

local function appendAttachmentContent(name, content)
    if not wv then return end
    wv:evaluateJavaScript(
        'appendAttachment(' ..
        hs.json.encode(name or "attachment") .. ',' ..
        hs.json.encode(content or "") ..
        ')'
    )
end

local function readAttachment(path)
    local attr = hs.fs.attributes(path)
    if not attr or attr.mode ~= "file" then
        return nil, "not a readable file"
    end
    if attr.size and attr.size > 200000 then
        return nil, "file is larger than 200 KB"
    end
    local fh = io.open(path, "rb")
    if not fh then
        return nil, "could not open file"
    end
    local data = fh:read("*a")
    fh:close()
    if not data then
        return nil, "could not read file"
    end
    if data:find("%z") then
        return nil, "binary files are not attached as text"
    end
    return data, nil
end

local function chooseAttachment()
    -- Lower window level so the native dialog appears above the overlay
    wv:level(hs.drawing.windowLevels.normal)
    local files = hs.dialog.chooseFileOrFolder(
        "Attach a file or image",
        os.getenv("HOME"),
        true,   -- canChooseFiles
        false,  -- canChooseDirectories
        true,   -- allowsMultipleSelection
        nil,    -- fileTypes (all)
        true    -- resolveAliases
    )
    wv:level(hs.drawing.windowLevels.modalPanel)
    if not files or #files == 0 then
        wv:evaluateJavaScript("focusInput()")
        return
    end
    for _, path in ipairs(files) do
        local content, err = readAttachment(path)
        if content then
            appendAttachmentContent(path, content)
        else
            appendInputValue("Attachment skipped: " .. path .. " (" .. (err or "unreadable") .. ")")
        end
    end
end

local function startDictation()
    if not wv then return end
    wv:evaluateJavaScript("focusInput()")
    hs.timer.doAfter(0.1, function()
        -- Press Globe/fn key twice — triggers macOS dictation when
        -- System Settings > Keyboard > Dictation shortcut = "Press Globe Key Twice"
        hs.osascript.applescript('tell application "System Events" to key code 63')
        hs.timer.doAfter(0.3, function()
            hs.osascript.applescript('tell application "System Events" to key code 63')
        end)
    end)
end


local function buildWebview()
    local obj = hs.webview.new(panelFrame())
    obj:windowStyle({"borderless", "nonactivating"})
    if obj.transparent then obj:transparent(true) end
    -- shadow(true) lets the OS render a natural panel shadow for depth
    if obj.shadow then obj:shadow(true) end
    obj:level(hs.drawing.windowLevels.modalPanel)
    obj:allowTextEntry(true)
    obj:html(OVERLAY_HTML)

    -- polling bridge: hs.webview:evaluateJavaScript is async and returns nil
    -- synchronously, so we must use the callback form to read the result.
    -- The script must be a plain expression (no top-level `return`).
    local function handleBridgeMessage(msg)
        if msg.type == 'resize' then
            local h = tonumber(msg.body) or PANEL_H_MIN
            h = math.max(PANEL_H_MIN, math.min(h, PANEL_H_MAX))
            obj:frame(panelFrame(h))
        elseif msg.type == 'dismiss' then
            hideOverlay()
        elseif msg.type == 'attach' then
            chooseAttachment()
        elseif msg.type == 'mic' then
            startDictation()
        end
    end

    hs.timer.doEvery(0.1, function()
        if not isVisible then return end
        obj:evaluateJavaScript(
            'JSON.stringify(window.__n_msg||null)',
            function(result, _err)
                if not result or result == 'null' then return end
                local msgOk, msg = pcall(hs.json.decode, result)
                if not msgOk or type(msg) ~= 'table' or not msg.type then return end
                obj:evaluateJavaScript('window.__n_msg=null')
                handleBridgeMessage(msg)
            end
        )
    end)

    return obj
end

function showOverlay()
    if not wv then wv = buildWebview() end
    wv:frame(panelFrame(PANEL_H_MIN))
    wv:show()
    local win = wv:hswindow()
    if win then win:focus() end
    hs.timer.doAfter(0.08, function()
        wv:evaluateJavaScript("focusInput()")
    end)
    isVisible = true
end

function hideOverlay()
    if wv then wv:hide() end
    isVisible = false
end

function openOverlay()
    if isVisible then hideOverlay() else showOverlay() end
end

hs.hotkey.bind({"cmd","shift"}, "space", openOverlay)

local overlayEvents = hs.eventtap.new({
    hs.eventtap.event.types.keyDown,
    hs.eventtap.event.types.leftMouseDown,
    hs.eventtap.event.types.leftMouseDragged,
    hs.eventtap.event.types.leftMouseUp
}, function(e)
    if not isVisible or not wv then return false end

    if e:getType() == hs.eventtap.event.types.keyDown then
        if e:getKeyCode() == 53 then
            hideOverlay()
            return true
        end
        return false
    end

    local pos = e:location()
    local f = wv:frame()
    local inFrame = pos.x >= f.x and pos.x <= f.x + f.w and
                    pos.y >= f.y and pos.y <= f.y + f.h

    -- Drag zone: entire panel. Clicks on buttons/textarea still pass through
    -- (we return false on mouseDown so the webview sees the event too).
    if e:getType() == hs.eventtap.event.types.leftMouseDown then
        if inFrame then
            dragState = { mouse = pos, frame = { x=f.x, y=f.y, w=f.w, h=f.h } }
        else
            dragState = nil
        end
        return false  -- always let webview see the click
    end

    if e:getType() == hs.eventtap.event.types.leftMouseDragged then
        if dragState then
            local dx = pos.x - dragState.mouse.x
            local dy = pos.y - dragState.mouse.y
            -- Use hswindow():setFrame() — wv:frame() setter is broken in HS 6936
            local win = wv:hswindow()
            if win then
                win:setFrame(hs.geometry.rect(
                    dragState.frame.x + dx,
                    dragState.frame.y + dy,
                    dragState.frame.w,
                    dragState.frame.h
                ))
            end
            return true
        end
        return false
    end

    if e:getType() == hs.eventtap.event.types.leftMouseUp then
        dragState = nil
    end

    return false
end)
overlayEvents:start()

local menubar = nil

local function pollHealth()
    hs.http.asyncGet(AGENT_URL .. "/health", nil, function(status, body)
        if not menubar then return end
        if status == 200 then
            local ok, data = pcall(hs.json.decode, body or "")
            if ok and type(data) == "table" then
                local count = 0
                if type(data.skills_loaded) == "table" then
                    count = #data.skills_loaded
                elseif type(data.skills_loaded) == "number" then
                    count = data.skills_loaded
                end
                menubar:setTitle("◉")
                menubar:setTooltip("NeurOS: " .. (data.status or "ok") .. " (" .. count .. " skills)")
                return
            end
        end
        menubar:setTitle("○")
        menubar:setTooltip("NeurOS: agent unreachable")
    end)
end

menubar = hs.menubar.new()
if menubar then
    menubar:setTitle("○")
    menubar:setTooltip("NeurOS")
    menubar:setClickCallback(openOverlay)
    pollHealth()
    hs.timer.doEvery(10, pollHealth)
end

print("[NeurOS] ready · ⌘⇧Space")
