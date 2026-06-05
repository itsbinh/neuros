-- NeurOS Hammerspoon Overlay
-- CMD+SHIFT+SPACE → modal input → POST to agent → display response

local hs.http = require("hs.http")
local hs.hotkey = require("hs.hotkey")
local hs.window = require("hs.window")
local hs.geometry = require("hs.geometry")
local hs.alert = require("hs.alert")
local hs.styledtext = require("hs.styledtext")

-- ── Configuration ───────────────────────────────────────────────
local AGENT_URL = "http://localhost:8080/query"
local BINDING = { "cmd", "shift" }
local KEY = "space"
local WINDOW_WIDTH = 600
local WINDOW_HEIGHT = 400

-- ── State ───────────────────────────────────────────────────────
local overlayWindow = nil
local inputField = nil
local responseLabel = nil
local isShowing = false

-- ── Build overlay window ────────────────────────────────────────
function buildOverlay()
    local webview = hs.webview.new(hs.geometry.rect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT))

    local html = [[
<!DOCTYPE html>
<html>
<head>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    background: #1a1a2e; color: #e0e0e0;
    height: 100vh; display: flex; flex-direction: column;
    padding: 16px;
  }
  h1 { font-size: 14px; color: #7f8fa6; margin-bottom: 12px; letter-spacing: 1px; }
  #input {
    width: 100%; padding: 12px; border-radius: 8px;
    border: 1px solid #333; background: #16213e; color: #fff;
    font-size: 16px; outline: none; resize: none; flex: 1;
  }
  #input:focus { border-color: #0f3460; }
  #response {
    margin-top: 12px; padding: 12px; border-radius: 8px;
    background: #0f3460; font-size: 14px; line-height: 1.5;
    max-height: 200px; overflow-y: auto; white-space: pre-wrap;
    display: none;
  }
  .typing { color: #7f8fa6; font-style: italic; }
</style>
</head>
<body>
  <h1>NEUR<span style="color:#0f3460">OS</span></h1>
  <textarea id="input" placeholder="Ask anything..." autofocus></textarea>
  <div id="response"></div>
<script>
  const input = document.getElementById("input");
  const response = document.getElementById("response");

  input.addEventListener("keydown", async (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      response.style.display = "block";
      response.innerHTML = '<span class="typing">thinking...</span>';
      try {
        const res = await fetch("http://localhost:8080/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text }),
        });
        const data = await res.json();
        response.textContent = data.text || "(no response)";
      } catch (err) {
        response.textContent = "Error: " + err.message;
      }
    }
  });

  input.focus();
</script>
</body>
</html>
    ]]

    webview:setHTML(html)
    return webview
end

-- ── Show / Hide ─────────────────────────────────────────────────
function showOverlay()
    if isShowing then
        hideOverlay()
        return
    end

    overlayWindow = hs.webview.new(hs.geometry.rect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT))
    local html = buildOverlayContent()
    overlayWindow:setHTML(html)

    -- Center on screen
    local screenFrame = hs.screen.primaryScreen():frame()
    local x = math.floor((screenFrame.w - WINDOW_WIDTH) / 2)
    local y = math.floor((screenFrame.h - WINDOW_HEIGHT) / 2)
    overlayWindow:move(hs.geometry.rect(x, y, WINDOW_WIDTH, WINDOW_HEIGHT))

    overlayWindow:show()
    isShowing = true
end

function buildOverlayContent()
    return [[
<!DOCTYPE html>
<html>
<head>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    background: #1a1a2e; color: #e0e0e0;
    height: 100vh; display: flex; flex-direction: column;
    padding: 16px;
  }
  h1 { font-size: 14px; color: #7f8fa6; margin-bottom: 12px; letter-spacing: 1px; }
  #input {
    width: 100%; padding: 12px; border-radius: 8px;
    border: 1px solid #333; background: #16213e; color: #fff;
    font-size: 16px; outline: none; resize: none; flex: 1;
  }
  #input:focus { border-color: #0f3460; }
  #response {
    margin-top: 12px; padding: 12px; border-radius: 8px;
    background: #0f3460; font-size: 14px; line-height: 1.5;
    max-height: 280px; overflow-y: auto; white-space: pre-wrap;
    display: none;
  }
  .typing { color: #7f8fa6; font-style: italic; }
  .panel { border-radius: 8px; padding: 12px; margin-top: 12px; }
  .panel.proposal { background: #2a2a3e; border-left: 4px solid #f0b400; }
  .panel.commit { background: #1f3a2a; border-left: 4px solid #28c76f; }
  .panel h2 { font-size: 13px; margin-bottom: 8px; letter-spacing: 0.5px; }
  .panel .risk { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-left: 6px; }
  .risk.low { background: #28c76f; color: #000; }
  .risk.medium { background: #f0b400; color: #000; }
  .risk.high { background: #ea5455; color: #fff; }
  .panel pre { white-space: pre-wrap; font-size: 12px; opacity: 0.85; margin: 6px 0; }
  .btn { padding: 6px 14px; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; margin-right: 6px; }
  .btn.apply { background: #28c76f; color: #000; }
  .btn.reject { background: #ea5455; color: #fff; }
  .btn.commit { background: #28c76f; color: #000; }
  .btn.skip { background: #555; color: #fff; }
</style>
</head>
<body>
  <h1>NEUR<span style="color:#0f3460">OS</span></h1>
  <textarea id="input" placeholder="Ask anything..." autofocus></textarea>
  <div id="response"></div>
<script>
  const input = document.getElementById("input");
  const response = document.getElementById("response");
  const AGENT = "http://localhost:8080/query";
  let sessionId = null;

  async function sendQuery(text) {
    response.style.display = "block";
    response.innerHTML = '<span class="typing">thinking...</span>';
    try {
      const res = await fetch(AGENT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, session_id: sessionId }),
      });
      const data = await res.json();
      if (data.session_id) sessionId = data.session_id;
      render(data.text || "(no response)");
    } catch (err) {
      response.textContent = "Error: " + err.message;
    }
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }

  function render(text) {
    const idMatch = text.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
    const riskMatch = text.match(/Risk:\s*(low|medium|high)/i);

    if (text.indexOf("📋 Proposed change") !== -1 && idMatch) {
      const risk = (riskMatch ? riskMatch[1] : "medium").toLowerCase();
      const pid = idMatch[0];
      response.innerHTML =
        '<div class="panel proposal">' +
        '<h2>⚡ Improvement Proposal <span class="risk ' + risk + '">' + risk.toUpperCase() + '</span></h2>' +
        '<pre>' + escapeHtml(text) + '</pre>' +
        '<button class="btn apply" data-id="' + pid + '">Apply</button>' +
        '<button class="btn reject" data-id="' + pid + '">Reject</button>' +
        '</div>';
      response.querySelector(".btn.apply").onclick = () => sendQuery("apply " + pid);
      response.querySelector(".btn.reject").onclick = () => sendQuery("reject " + pid);
      return;
    }

    if (text.indexOf("Tests passed") !== -1 || text.indexOf("✅ Tests") !== -1) {
      response.innerHTML =
        '<div class="panel commit">' +
        '<h2>✅ Tests Passing</h2>' +
        '<pre>' + escapeHtml(text) + '</pre>' +
        '<button class="btn commit">Commit</button>' +
        '<button class="btn skip">Skip</button>' +
        '</div>';
      response.querySelector(".btn.commit").onclick = () => sendQuery("commit");
      response.querySelector(".btn.skip").onclick = () => { response.style.display = "none"; };
      return;
    }

    response.textContent = text;
  }

  input.addEventListener("keydown", async (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      await sendQuery(text);
    }
  });

  input.focus();
</script>
</body>
</html>
    ]]
end

function hideOverlay()
    if overlayWindow then
        overlayWindow:close()
        overlayWindow = nil
    end
    isShowing = false
end

-- ── Hotkey binding ──────────────────────────────────────────────
local toggleHotkey = hs.hotkey.new(BINDING, KEY, function()
    showOverlay()
end)

hs.alert.show("NeurOS overlay loaded. CMD+SHIFT+SPACE to activate.", 2)
