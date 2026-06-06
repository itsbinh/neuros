-- NeurOS Hammerspoon Overlay — single webview panel
-- CMD+SHIFT+SPACE → unified input/response panel

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
    background: #1c1c1e;
    border-radius: 16px;
    overflow: hidden;
    box-shadow:
      0 24px 64px rgba(0,0,0,0.6),
      0 4px 16px rgba(0,0,0,0.4),
      inset 0 1px 0 rgba(255,255,255,0.06);
  }
  #query {
    width: 100%;
    min-height: 80px;
    background: transparent;
    border: none;
    outline: none;
    resize: none;
    color: #f2f2f7;
    font-size: 16px;
    font-weight: 400;
    line-height: 1.55;
    padding: 16px 16px 10px;
    caret-color: #a78bfa;
    font-family: inherit;
  }
  #query::placeholder { color: rgba(235,235,245,0.28); }
  #query:disabled { opacity: 0.4; }
  #toolbar {
    display: flex;
    align-items: center;
    height: 46px;
    padding: 0 12px 0 14px;
    border-top: 1px solid rgba(255,255,255,0.07);
    gap: 2px;
    flex-shrink: 0;
  }
  .ibtn {
    display: flex; align-items: center; justify-content: center;
    width: 30px; height: 30px;
    border-radius: 7px; border: none;
    background: transparent;
    color: rgba(255,255,255,0.32);
    cursor: pointer;
    transition: color 0.12s, background 0.12s;
    flex-shrink: 0;
  }
  .ibtn:hover {
    color: rgba(255,255,255,0.75);
    background: rgba(255,255,255,0.07);
  }
  .sep {
    width: 1px; height: 15px;
    background: rgba(255,255,255,0.1);
    margin: 0 5px; flex-shrink: 0;
  }
  #toolbar-right {
    margin-left: auto;
    display: flex; align-items: center; gap: 8px;
  }
  #spinner {
    display: none;
    color: rgba(255,255,255,0.3);
    font-size: 13px;
    width: 20px; text-align: center;
  }
  #btn-mic {
    width: 32px; height: 32px;
    border-radius: 50%;
    background: #fff;
    color: #1a1a1a;
    border: none; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: transform 0.1s, background 0.12s;
    flex-shrink: 0;
  }
  #btn-mic:hover { background: #ececec; transform: scale(1.05); }
  #btn-mic:active { transform: scale(0.95); }
  #resp-divider {
    height: 1px;
    background: rgba(255,255,255,0.07);
    display: none;
  }
  #resp-wrap {
    display: none;
    padding: 14px 16px 4px;
    max-height: 320px;
    overflow-y: auto;
  }
  #resp-wrap::-webkit-scrollbar { width: 3px; }
  #resp-wrap::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.12);
    border-radius: 2px;
  }
  #resp-text {
    color: #e5e5ea;
    font-size: 14px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
  }
  #resp-text.err { color: #ff453a; }
  #meta-row {
    display: none;
    padding: 8px 16px 14px;
    gap: 5px; flex-wrap: wrap; align-items: center;
  }
  .sbadge {
    background: rgba(167,139,250,0.12);
    color: rgba(167,139,250,0.85);
    font-size: 11px; font-weight: 500;
    padding: 2px 8px; border-radius: 10px;
    border: 1px solid rgba(167,139,250,0.2);
  }
  .mbadge { color: rgba(235,235,245,0.2); font-size: 11px; }
  .lbadge { color: rgba(235,235,245,0.18); font-size: 11px; margin-left: auto; }
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
    <button class="ibtn" id="btn-attach" title="Attach">
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
    <div class="sep"></div>
    <button class="ibtn" id="btn-gear" title="Settings">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010
                 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33
                 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65
                 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0
                 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65
                 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9
                 a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83
                 l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3
                 a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0
                 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65
                 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0
                 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
      </svg>
    </button>
    <div class="sep"></div>
    <button class="ibtn" id="btn-code" title="Git status">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
        <polyline points="16 18 22 12 16 6"/>
        <polyline points="8 6 2 12 8 18"/>
      </svg>
    </button>

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
    </div>
  </div>

  <div id="resp-divider"></div>
  <div id="resp-wrap"><div id="resp-text"></div></div>
  <div id="meta-row"></div>

</div>
<script>
  const q      = document.getElementById('query');
  const spin   = document.getElementById('spinner');
  const rdiv   = document.getElementById('resp-divider');
  const rwrap  = document.getElementById('resp-wrap');
  const rtext  = document.getElementById('resp-text');
  const meta   = document.getElementById('meta-row');

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
  function hideResp() {
    rdiv.style.display = 'none';
    rwrap.style.display = 'none';
    rtext.textContent = '';
    meta.style.display = 'none';
    meta.innerHTML = '';
    window.webkit.messageHandlers.resize.postMessage(130);
  }

  function setLoading(txt) {
    q.disabled = true;
    q.value = '';
    q.placeholder = txt;
    startSpin();
    hideResp();
  }

  function receiveResponse(text, skillUsed, latencyMs, modelUsed, isError) {
    stopSpin();
    q.disabled = false;
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

    window.webkit.messageHandlers.resize.postMessage(
      document.getElementById('panel').scrollHeight
    );
    setTimeout(() => q.focus(), 40);
  }

  function setInputValue(val) { q.value = val; q.focus(); }
  function focusInput() { q.focus(); }

  q.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const v = q.value.trim();
      if (!v) return;
      setLoading(v);
      window.webkit.messageHandlers.query.postMessage(v);
    }
    if (e.key === 'Escape')
      window.webkit.messageHandlers.dismiss.postMessage('');
    if (e.key === 'ArrowUp' && q.value === '') {
      e.preventDefault();
      window.webkit.messageHandlers.historyUp.postMessage('');
    }
    if (e.key === 'ArrowDown' && q.value === '') {
      e.preventDefault();
      window.webkit.messageHandlers.historyDown.postMessage('');
    }
  });

  document.addEventListener('keydown', function(e) {
    if (e.metaKey && e.key === 'k') {
      hideResp(); q.value = '';
      q.placeholder = 'Type your message here...';
      q.focus();
    }
  });

  document.getElementById('btn-gear').onclick = () => {
    setLoading('open settings');
    window.webkit.messageHandlers.query.postMessage('open settings');
  };
  document.getElementById('btn-code').onclick = () => {
    setLoading('git status');
    window.webkit.messageHandlers.query.postMessage('git status');
  };
  document.getElementById('btn-attach').onclick = () => q.focus();
  document.getElementById('btn-web').onclick    = () => q.focus();
  document.getElementById('btn-mic').onclick    = () => q.focus();

  setTimeout(() => q.focus(), 40);
</script>
</body>
</html>
]]

-- ── Constants ────────────────────────────────────────────────────

local AGENT_URL = "http://localhost:8080"
local SESSION_ID = "overlay-" .. tostring(os.time())

-- ── Panel dimensions ─────────────────────────────────────────────

local PANEL_W   = 680
local PANEL_TOP = 52
local PANEL_H_MIN = 130
local PANEL_H_MAX = 520

-- ── State ────────────────────────────────────────────────────────

local wv         = nil
local isVisible  = false
local isLoading  = false
local history    = {}
local historyIdx = 0

-- ── Helpers ──────────────────────────────────────────────────────

local function panelFrame(h)
    local sf = hs.screen.mainScreen():frame()
    return {
        x = sf.x + math.floor((sf.w - PANEL_W) / 2),
        y = sf.y + PANEL_TOP,
        w = PANEL_W,
        h = h or PANEL_H_MIN
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

-- ── Submit query (HTTP unchanged, UI calls replaced) ─────────────

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

-- ── Webview creation (once) ──────────────────────────────────────

local function buildWebview()
    local obj = hs.webview.new(panelFrame())
    obj:windowStyle({})
    obj:level(hs.drawing.windowLevels.modalPanel)
    obj:allowTextEntry(true)
    obj:html(OVERLAY_HTML)

    -- resize message from JS
    obj:userContentController():addScriptMessageHandler(
        hs.webview.usercontent.new("resize"),
        function(msg)
            local h = tonumber(msg.body) or PANEL_H_MIN
            h = math.max(PANEL_H_MIN, math.min(h, PANEL_H_MAX))
            obj:setFrame(panelFrame(h))
        end
    )

    -- query submitted from JS
    obj:userContentController():addScriptMessageHandler(
        hs.webview.usercontent.new("query"),
        function(msg)
            submitQuery(msg.body)
        end
    )

    -- dismiss from JS (ESC key)
    obj:userContentController():addScriptMessageHandler(
        hs.webview.usercontent.new("dismiss"),
        function(_) hideOverlay() end
    )

    -- history navigation
    obj:userContentController():addScriptMessageHandler(
        hs.webview.usercontent.new("historyUp"),
        function(msg)
            historyIdx = math.min(historyIdx + 1, #history)
            if history[historyIdx] then
                obj:evaluateJavaScript(
                    "setInputValue("..hs.json.encode(history[historyIdx])..")"
                )
            end
        end
    )

    obj:userContentController():addScriptMessageHandler(
        hs.webview.usercontent.new("historyDown"),
        function(msg)
            historyIdx = math.max(historyIdx - 1, 0)
            local val = history[historyIdx] or ""
            obj:evaluateJavaScript("setInputValue("..hs.json.encode(val)..")")
        end
    )

    return obj
end

-- ── Show / hide ──────────────────────────────────────────────────

function showOverlay()
    if not wv then wv = buildWebview() end
    wv:setFrame(panelFrame(PANEL_H_MIN))
    wv:show()
    wv:hswindow():focus()
    hs.timer.doAfter(0.05, function()
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

-- ── Click outside to dismiss ─────────────────────────────────────

local clickWatcher = hs.eventtap.new(
    { hs.eventtap.event.types.leftMouseDown },
    function(e)
        if not isVisible or not wv then return false end
        local pos = e:location()
        local f   = wv:frame()
        if pos.x < f.x or pos.x > f.x + f.w or
           pos.y < f.y or pos.y > f.y + f.h then
            hideOverlay()
        end
        return false
    end
)
clickWatcher:start()

-- ── Hotkeys ──────────────────────────────────────────────────────

hs.hotkey.bind({ "cmd", "shift" }, "space", openOverlay)

-- ── Menubar with health polling ──────────────────────────────────

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
