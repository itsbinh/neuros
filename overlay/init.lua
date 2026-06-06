local OVERLAY_HTML = [[
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body {
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont,
                 "SF Pro Text", "Helvetica Neue", sans-serif;
    -webkit-font-smoothing: antialiased;
    width: 100%; height: 100%;
  }
  #panel {
    background: #ffffff;
    border-radius: 16px;
    overflow: hidden;
    box-shadow:
      0 8px 40px rgba(0,0,0,0.18),
      0 2px 8px rgba(0,0,0,0.10),
      0 0 0 1px rgba(0,0,0,0.06);
    display: flex;
    flex-direction: column;
    -webkit-app-region: drag;
  }
  #query {
    width: 100%;
    min-height: 80px;
    background: transparent;
    border: none;
    outline: none;
    resize: none;
    color: #1d1d1f;
    font-size: 16px;
    font-weight: 400;
    line-height: 1.55;
    padding: 18px 18px 10px;
    caret-color: #6366f1;
    font-family: inherit;
    -webkit-app-region: no-drag;
  }
  #query::placeholder { color: rgba(0,0,0,0.28); }
  #query:disabled { opacity: 0.45; }
  #toolbar {
    display: flex;
    align-items: center;
    height: 48px;
    padding: 0 10px 0 12px;
    border-top: 1px solid rgba(0,0,0,0.07);
    gap: 2px;
    flex-shrink: 0;
    background: #f9f9f9;
    -webkit-app-region: drag;
  }
  .ibtn {
    display: flex; align-items: center; justify-content: center;
    width: 32px; height: 32px;
    border-radius: 8px; border: none;
    background: transparent;
    color: rgba(0,0,0,0.35);
    cursor: pointer;
    transition: color 0.12s, background 0.12s;
    flex-shrink: 0;
    -webkit-app-region: no-drag;
  }
  .ibtn:hover {
    color: rgba(0,0,0,0.75);
    background: rgba(0,0,0,0.06);
  }
  .ibtn:active { background: rgba(0,0,0,0.1); }
  #toolbar-right {
    margin-left: auto;
    display: flex; align-items: center; gap: 6px;
    -webkit-app-region: no-drag;
  }
  #spinner {
    display: none;
    color: rgba(0,0,0,0.3);
    font-size: 13px;
    width: 20px; text-align: center;
  }
  #btn-send {
    width: 32px; height: 32px;
    border-radius: 50%;
    background: #6366f1;
    color: #fff;
    border: none; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: transform 0.1s, background 0.12s;
    flex-shrink: 0;
    -webkit-app-region: no-drag;
  }
  #btn-send:hover { background: #4f46e5; transform: scale(1.05); }
  #btn-send:active { transform: scale(0.95); }
  #btn-send:disabled {
    background: rgba(99,102,241,0.3);
    cursor: not-allowed;
    transform: none;
  }
  #btn-mic {
    width: 32px; height: 32px;
    border-radius: 50%;
    background: #f0f0f0;
    color: #333;
    border: none; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: transform 0.1s, background 0.12s;
    flex-shrink: 0;
    -webkit-app-region: no-drag;
  }
  #btn-mic:hover { background: #e0e0e0; transform: scale(1.05); }
  #btn-mic:active { transform: scale(0.95); }
  #resp-divider {
    height: 1px;
    background: rgba(0,0,0,0.07);
    display: none;
  }
  #resp-wrap {
    display: none;
    padding: 14px 18px 4px;
    max-height: 340px;
    overflow-y: auto;
    background: #fff;
  }
  #resp-wrap::-webkit-scrollbar { width: 3px; }
  #resp-wrap::-webkit-scrollbar-thumb {
    background: rgba(0,0,0,0.12);
    border-radius: 2px;
  }
  #resp-text {
    color: #1d1d1f;
    font-size: 14px;
    line-height: 1.65;
    white-space: pre-wrap;
    word-break: break-word;
  }
  #resp-text.err { color: #dc2626; }
  #meta-row {
    display: none;
    padding: 8px 18px 14px;
    gap: 5px; flex-wrap: wrap; align-items: center;
    background: #fff;
  }
  .sbadge {
    background: rgba(99,102,241,0.08);
    color: rgba(99,102,241,0.9);
    font-size: 11px; font-weight: 500;
    padding: 2px 8px; border-radius: 10px;
    border: 1px solid rgba(99,102,241,0.2);
  }
  .mbadge { color: rgba(0,0,0,0.25); font-size: 11px; }
  .lbadge { color: rgba(0,0,0,0.2); font-size: 11px; margin-left: auto; }
</style>
</head>
<body>
<div id="panel">

  <textarea id="query"
    placeholder="Type your message here..."
    autocomplete="off" autocorrect="off"
    autocapitalize="off" spellcheck="false"
    rows="3"></textarea>

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

    <!-- right: spinner + mic + send -->
    <div id="toolbar-right">
      <span id="spinner">◐</span>
      <button id="btn-mic" title="Voice (Phase 8)">
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

  <div id="resp-divider"></div>
  <div id="resp-wrap"><div id="resp-text"></div></div>
  <div id="meta-row"></div>

</div>
<script>
  const q     = document.getElementById('query');
  const spin  = document.getElementById('spinner');
  const rdiv  = document.getElementById('resp-divider');
  const rwrap = document.getElementById('resp-wrap');
  const rtext = document.getElementById('resp-text');
  const meta  = document.getElementById('meta-row');
  const btnSend = document.getElementById('btn-send');

  // message bridge (polling from Lua)
  function _postMessage(type, body) {
    window.__n_msg = { type: type, body: String(body) };
  }

  // spinner
  const SF = ['◐','◓','◑','◒'];
  let si = 0, st = null;
  function startSpin() {
    spin.style.display = 'inline';
    st = setInterval(() => { spin.textContent = SF[si++ % 4]; }, 120);
  }
  function stopSpin() {
    clearInterval(st); st = null;
    spin.style.display = 'none';
  }

  // clear response area
  function hideResp() {
    rdiv.style.display = 'none';
    rwrap.style.display = 'none';
    rtext.textContent = '';
    meta.style.display = 'none';
    meta.innerHTML = '';
    _postMessage('resize', 160);
  }

  // loading state
  function setLoading(txt) {
    q.disabled = true;
    btnSend.disabled = true;
    q.value = '';
    q.placeholder = txt;
    startSpin();
    hideResp();
  }

  // called by Lua after response arrives
  function receiveResponse(text, skillUsed, latencyMs, modelUsed, isError) {
    stopSpin();
    q.disabled = false;
    btnSend.disabled = false;
    q.placeholder = 'Type your message here...';
    q.value = '';

    rdiv.style.display = 'block';
    rwrap.style.display = 'block';
    rtext.textContent = text;
    rtext.className = isError ? 'err' : '';

    meta.innerHTML = '';
    let hasMeta = false;
    if (skillUsed) {
      skillUsed.split(',').forEach(s => {
        s = s.trim(); if (!s) return;
        const b = document.createElement('span');
        b.className = 'sbadge';
        b.textContent = '⚡ ' + s;
        meta.appendChild(b);
        hasMeta = true;
      });
    }
    if (modelUsed) {
      const m = document.createElement('span');
      m.className = 'mbadge';
      m.textContent = modelUsed.split('/').pop();
      meta.appendChild(m);
      hasMeta = true;
    }
    if (latencyMs) {
      const l = document.createElement('span');
      l.className = 'lbadge';
      l.textContent = latencyMs + ' ms';
      meta.appendChild(l);
      hasMeta = true;
    }
    if (hasMeta) meta.style.display = 'flex';

    _postMessage('resize', document.getElementById('panel').scrollHeight);
    setTimeout(() => q.focus(), 40);
  }

  function setInputValue(val) { q.value = val; q.focus(); }
  function focusInput() {
    q.focus();
    // move cursor to end
    q.selectionStart = q.selectionEnd = q.value.length;
  }

  // submit helper
  function doSubmit() {
    const v = q.value.trim();
    if (!v) return;
    setLoading(v);
    _postMessage('query', v);
  }

  // textarea keydown
  q.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      doSubmit();
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      _postMessage('dismiss', '');
      return;
    }
    if (e.key === 'ArrowUp' && q.value === '') {
      e.preventDefault();
      _postMessage('historyUp', '');
      return;
    }
    if (e.key === 'ArrowDown' && q.value === '') {
      e.preventDefault();
      _postMessage('historyDown', '');
      return;
    }
  });

  // global shortcuts
  document.addEventListener('keydown', function(e) {
    // CMD+K or CTRL+C → clear
    if ((e.metaKey && e.key === 'k') || (e.ctrlKey && e.key === 'c')) {
      e.preventDefault();
      hideResp();
      q.value = '';
      q.placeholder = 'Type your message here...';
      q.focus();
    }
    // ESC anywhere → dismiss
    if (e.key === 'Escape') {
      _postMessage('dismiss', '');
    }
  });

  // button handlers
  btnSend.addEventListener('click', doSubmit);
  document.getElementById('btn-attach').addEventListener('click', () => q.focus());
  document.getElementById('btn-web').addEventListener('click', () => {
    // prefix query with "search:" hint
    if (q.value === '') q.value = 'search: ';
    q.focus();
    q.selectionStart = q.selectionEnd = q.value.length;
  });
  document.getElementById('btn-mic').addEventListener('click', () => q.focus());

  // auto focus on load
  setTimeout(() => q.focus(), 50);
</script>
</body>
</html>
]]

local AGENT_URL = "http://localhost:8080"
local SESSION_ID = "overlay-" .. tostring(os.time())

local PANEL_W     = 620
local PANEL_H_MIN = 160
local PANEL_H_MAX = 560

local wv         = nil
local isVisible  = false
local isLoading  = false
local history    = {}
local historyIdx = 0

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

local function escapeHTML(text)
    text = tostring(text or "")
    text = text:gsub("&", "&amp;")
    text = text:gsub("<", "&lt;")
    text = text:gsub(">", "&gt;")
    return text
end

local function responseText(data)
    if type(data) ~= "table" then return "(invalid response)" end
    return data.text or data.response or data.error or "(no response)"
end

local function submitQuery(text)
    if isLoading then return end
    text = (text or ""):match("^%s*(.-)%s*$")
    if text == "" then return end

    isLoading = true

    table.insert(history, text)
    historyIdx = #history

    wv:evaluateJavaScript("setLoading("..hs.json.encode(text)..")")

    local started = hs.timer.secondsSinceEpoch()
    local payload = hs.json.encode({ text = text, session_id = SESSION_ID })
    hs.http.asyncPost(
        AGENT_URL .. "/query",
        payload,
        { ["Content-Type"] = "application/json" },
        function(status, body)
            isLoading = false

            local elapsedMs = math.floor((hs.timer.secondsSinceEpoch() - started) * 1000)
            if status ~= 200 then
                wv:evaluateJavaScript(
                    "receiveResponse("..hs.json.encode(body or "error")..",'',0,'',true)"
                )
                return
            end

            local ok, data = pcall(hs.json.decode, body or "")
            if not ok then
                wv:evaluateJavaScript(
                    "receiveResponse("..hs.json.encode(body or "error")..",'',0,'',true)"
                )
                return
            end

            local model = data.model_used or data.skill_used or "agent"
            local latency = data.latency_ms or elapsedMs

            local js = string.format(
                "receiveResponse(%s,%s,%d,%s,%s)",
                hs.json.encode(responseText(data)),
                hs.json.encode(data.skill_used or ""),
                latency,
                hs.json.encode(model),
                "false"
            )
            wv:evaluateJavaScript(js)
        end
    )
end

local function buildWebview()
    local obj = hs.webview.new(panelFrame())
    obj:windowStyle({"borderless", "nonactivating"})
    obj:level(hs.drawing.windowLevels.modalPanel)
    obj:allowTextEntry(true)
    obj:html(OVERLAY_HTML)

    -- polling bridge (userContentController unavailable in this HS version)
    hs.timer.doEvery(0.05, function()
        if not isVisible or isLoading then return end
        local ok, result = pcall(
            obj.evaluateJavaScript, obj,
            'try{return JSON.stringify(window.__n_msg)}catch(e){return null}'
        )
        if not ok or not result or result == 'null' or result == 'undefined' then
            return
        end
        local msgOk, msg = pcall(hs.json.decode, result)
        if not msgOk or type(msg) ~= 'table' or not msg.type then return end
        obj:evaluateJavaScript('window.__n_msg=null')

        if msg.type == 'resize' then
            local h = tonumber(msg.body) or PANEL_H_MIN
            h = math.max(PANEL_H_MIN, math.min(h, PANEL_H_MAX))
            obj:frame(panelFrame(h))
        elseif msg.type == 'query' then
            submitQuery(msg.body)
        elseif msg.type == 'dismiss' then
            hideOverlay()
        elseif msg.type == 'historyUp' then
            historyIdx = math.min(historyIdx + 1, #history)
            if history[historyIdx] then
                obj:evaluateJavaScript(
                    'setInputValue('..hs.json.encode(history[historyIdx])..')'
                )
            end
        elseif msg.type == 'historyDown' then
            historyIdx = math.max(historyIdx - 1, 0)
            local val = history[historyIdx] or ''
            obj:evaluateJavaScript('setInputValue('..hs.json.encode(val)..')')
        end
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
    hs.timer.doEvery(30, pollHealth)
end

print("[NeurOS] ready · ⌘⇧Space")
