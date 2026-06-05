-- NeurOS Hammerspoon Overlay
-- CMD+SHIFT+SPACE → modal input → POST to agent → display response

local hs.http = require("hs.http")
local hs.hotkey = require("hs.hotkey")
local hs.window = require("hs.window")
local hs.geometry = require("hs.geometry")
local hs.alert = require("hs.alert")
local hs.styledtext = require("hs.styledtext")

-- ── Configuration ───────────────────────────────────────────────
local AGENT_URL = "http://localhost:8000/query"
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
        const res = await fetch("http://localhost:8000/query", {
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
        const res = await fetch("http://localhost:8000/query", {
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
