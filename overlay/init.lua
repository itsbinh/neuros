-- NeurOS Hammerspoon Overlay — Spotlight-style command bar
-- CMD+SHIFT+SPACE → frosted webview → POST /query → render response

local AGENT_URL = "http://localhost:8080"
local SESSION_ID = "overlay-" .. tostring(os.time())

local WIDTH = 680
local HEIGHT_COLLAPSED = 64
local HEIGHT_EXPANDED = 320
local TOP_OFFSET = 46

local overlay = nil
local clickWatcher = nil
local menubar = nil

-- ── Geometry ────────────────────────────────────────────────────
local function getOverlayFrame(height)
    local screen = hs.screen.mainScreen():frame()
    local x = screen.x + math.floor((screen.w - WIDTH) / 2)
    local y = screen.y + TOP_OFFSET
    return { x = x, y = y, w = WIDTH, h = height or HEIGHT_COLLAPSED }
end

-- ── HTML payload ────────────────────────────────────────────────
local function buildHTML()
    return [[
<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body {
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
    color: #f2f2f7;
    height: 100vh;
    overflow: hidden;
  }
  #container {
    background: rgba(28, 28, 30, 0.97);
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 16px 60px rgba(0,0,0,0.6);
    width: 100%;
    min-height: 64px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  #input-row {
    display: flex;
    align-items: center;
    height: 64px;
    padding: 0 20px;
    gap: 12px;
  }
  #icon {
    font-size: 18px;
    color: #8e8e93;
    width: 22px;
    text-align: center;
    font-family: "Menlo", monospace;
  }
  #query {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: #f2f2f7;
    font-size: 18px;
    font-weight: 400;
    caret-color: #0a84ff;
  }
  #query::placeholder { color: #636366; }
  #spinner {
    font-size: 16px;
    color: #0a84ff;
    width: 20px;
    text-align: center;
    font-family: "Menlo", monospace;
    display: none;
  }
  #response-area {
    border-top: 1px solid rgba(255,255,255,0.06);
    padding: 14px 20px 12px 20px;
    font-size: 14px;
    line-height: 1.5;
    color: #e5e5ea;
    max-height: 220px;
    overflow-y: auto;
    white-space: pre-wrap;
    display: none;
  }
  #meta-row {
    display: none;
    padding: 8px 20px 12px 20px;
    font-size: 11px;
    color: #8e8e93;
    align-items: center;
    gap: 8px;
    border-top: 1px solid rgba(255,255,255,0.04);
  }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    background: rgba(10, 132, 255, 0.18);
    color: #64b5ff;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.3px;
  }
  .badge.error { background: rgba(255, 69, 58, 0.18); color: #ff6961; }
  .latency { margin-left: auto; font-variant-numeric: tabular-nums; }
  #response-area::-webkit-scrollbar { width: 6px; }
  #response-area::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
</style></head>
<body>
  <div id="container">
    <div id="input-row">
      <div id="icon">&gt;_</div>
      <input id="query" type="text" autofocus autocomplete="off" spellcheck="false" placeholder="Ask NeurOS..." />
      <div id="spinner">&#9680;</div>
    </div>
    <div id="response-area"></div>
    <div id="meta-row">
      <span id="skill-badge" class="badge"></span>
      <span class="latency" id="latency"></span>
    </div>
  </div>

<script>
  const AGENT = "__AGENT_URL__";
  const SESSION_ID = "__SESSION_ID__";

  const input = document.getElementById("query");
  const spinner = document.getElementById("spinner");
  const responseArea = document.getElementById("response-area");
  const metaRow = document.getElementById("meta-row");
  const skillBadge = document.getElementById("skill-badge");
  const latencyEl = document.getElementById("latency");

  const history = [];
  let historyIdx = -1;
  let spinnerTimer = null;
  const FRAMES = ["◐","◓","◑","◒"];
  let frameIdx = 0;

  function notify(name, payload) {
    try {
      if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers[name]) {
        window.webkit.messageHandlers[name].postMessage(payload || {});
      }
    } catch (e) {}
  }

  function startSpinner() {
    spinner.style.display = "block";
    spinnerTimer = setInterval(() => {
      spinner.textContent = FRAMES[frameIdx];
      frameIdx = (frameIdx + 1) % FRAMES.length;
    }, 150);
  }
  function stopSpinner() {
    if (spinnerTimer) clearInterval(spinnerTimer);
    spinnerTimer = null;
    spinner.style.display = "none";
  }

  function expand() {
    notify("resize", { h: 320 });
  }
  function collapse() {
    responseArea.style.display = "none";
    metaRow.style.display = "none";
    notify("resize", { h: 64 });
  }

  async function send(text) {
    startSpinner();
    input.disabled = true;
    const t0 = performance.now();
    try {
      const res = await fetch(AGENT + "/query", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ text: text, session_id: SESSION_ID })
      });
      const data = await res.json();
      const dt = Math.round(performance.now() - t0);
      renderResponse(data, dt);
    } catch (err) {
      renderError(err.message);
    } finally {
      stopSpinner();
      input.disabled = false;
      input.focus();
    }
  }

  function renderResponse(data, dt) {
    expand();
    responseArea.style.display = "block";
    metaRow.style.display = "flex";
    if (data.error) {
      responseArea.textContent = data.error;
      skillBadge.className = "badge error";
      skillBadge.textContent = "error";
    } else {
      responseArea.textContent = data.response || "(no response)";
      skillBadge.className = "badge";
      skillBadge.textContent = data.skill_used || "agent";
    }
    const lat = data.latency_ms != null ? data.latency_ms : dt;
    latencyEl.textContent = lat + " ms";
  }

  function renderError(msg) {
    expand();
    responseArea.style.display = "block";
    metaRow.style.display = "flex";
    responseArea.textContent = "Error: " + msg;
    skillBadge.className = "badge error";
    skillBadge.textContent = "network";
    latencyEl.textContent = "";
  }

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const t = input.value.trim();
      if (!t) return;
      history.unshift(t);
      if (history.length > 20) history.pop();
      historyIdx = -1;
      input.value = "";
      send(t);
    } else if (e.key === "Escape") {
      e.preventDefault();
      notify("dismiss", {});
    } else if (e.key === "ArrowUp") {
      if (history.length === 0) return;
      e.preventDefault();
      historyIdx = Math.min(historyIdx + 1, history.length - 1);
      input.value = history[historyIdx];
    } else if (e.key === "ArrowDown") {
      if (history.length === 0) return;
      e.preventDefault();
      historyIdx = Math.max(historyIdx - 1, -1);
      input.value = historyIdx === -1 ? "" : history[historyIdx];
    } else if (e.key === "k" && e.metaKey) {
      e.preventDefault();
      input.value = "";
      collapse();
    }
  });

  setTimeout(() => input.focus(), 30);
</script>
</body></html>
]]
end

local function renderHTML()
    local html = buildHTML()
    html = html:gsub("__AGENT_URL__", AGENT_URL)
    html = html:gsub("__SESSION_ID__", SESSION_ID)
    return html
end

-- ── Overlay lifecycle ───────────────────────────────────────────
local function dismissOverlay()
    if clickWatcher then
        clickWatcher:stop()
        clickWatcher = nil
    end
    if overlay then
        overlay:delete()
        overlay = nil
    end
end

local function resizeOverlay(h)
    if not overlay then return end
    local f = getOverlayFrame(h)
    overlay:frame(f)
end

local function handleMessage(message)
    if type(message) ~= "table" then return end
    local body = message.body
    local name = message.name
    if name == "dismiss" then
        dismissOverlay()
    elseif name == "resize" then
        local h = HEIGHT_COLLAPSED
        if type(body) == "table" and body.h then h = body.h end
        resizeOverlay(h)
    end
end

local function openOverlay()
    if overlay then
        dismissOverlay()
        return
    end

    local frame = getOverlayFrame(HEIGHT_COLLAPSED)
    local prefs = { developerExtrasEnabled = false }
    local ucc = hs.webview.usercontent.new("neuros")
    ucc:setCallback(handleMessage)

    overlay = hs.webview.new(frame, prefs, ucc)
        :allowTextEntry(true)
        :transparent(true)
        :windowStyle({ "borderless", "closable", "nonactivating" })
        :level(hs.drawing.windowLevels.modalPanel)
        :shadow(true)
        :closeOnEscape(true)
        :html(renderHTML())
        :bringToFront(true)
        :show()

    hs.timer.doAfter(0.05, function()
        if overlay then overlay:hswindow():focus() end
    end)

    -- click-outside dismiss
    clickWatcher = hs.eventtap.new(
        { hs.eventtap.event.types.leftMouseDown, hs.eventtap.event.types.rightMouseDown },
        function(event)
            if not overlay then return false end
            local pos = event:location()
            local f = overlay:frame()
            local inside = pos.x >= f.x and pos.x <= f.x + f.w
                       and pos.y >= f.y and pos.y <= f.y + f.h
            if not inside then
                hs.timer.doAfter(0, dismissOverlay)
            end
            return false
        end
    ):start()
end

-- ── Hotkeys ─────────────────────────────────────────────────────
hs.hotkey.bind({ "cmd", "shift" }, "space", openOverlay)

-- ── Menubar with health polling ─────────────────────────────────
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

hs.alert.show("NeurOS overlay ready · ⌘⇧Space", 1.5)
