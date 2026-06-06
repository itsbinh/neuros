# Native macOS App Plan

Goal: replace the Hammerspoon overlay with a native Apple Silicon macOS app shell
while keeping the existing FastAPI NeurOS agent as the backend.

This work is tracked on `feature/native-macos-app`. It is currently stacked on
`feature/model-selector`; after the model selector lands, rebase this branch onto
`main`.

## Git Workflow

- Keep one branch per coherent feature stream.
- Commit small vertical slices that build and can be tested.
- Prefer commit subjects in conventional format, for example
  `feat(macos): add menu bar app shell`.
- Before each push, run the relevant verification gate listed for that phase.
- Keep generated build products out of git.

## Phase 0: Planning Baseline

Status: in progress

Scope:
- Add this plan.
- Define phase order, commit boundaries, and verification gates.

Done when:
- The planning branch is pushed.
- The worktree is clean.

Verification:
- `git status --short --branch`

## Phase 1: Native App Skeleton

Scope:
- Add a minimal Swift/SwiftUI macOS app project under `macos/NeurOS/`.
- Create a menu bar app with no Dock icon.
- Add a status item that opens a simple floating panel.
- Add a global hotkey placeholder if feasible without extra dependencies.

Suggested commits:
- `feat(macos): add SwiftUI app skeleton`
- `feat(macos): add menu bar status item`
- `feat(macos): add floating command panel`

Done when:
- The app builds locally on Apple Silicon.
- The menu bar item opens and closes the panel.
- Existing Python tests still pass.

Verification:
- `xcodebuild -scheme NeurOS -destination 'platform=macOS' build` from `macos/NeurOS`
- `pytest -q`

## Phase 2: Agent API Client

Scope:
- Add a small native HTTP client for:
  - `GET /health`
  - `GET /models`
  - `POST /query/stream`
- Parse SSE streaming responses.
- Surface model, skill, and latency metadata.

Suggested commits:
- `feat(macos): add agent API client`
- `feat(macos): stream query responses`

Done when:
- The native app can show agent health.
- The app can send a query and stream the response.
- The selected model name is passed to the backend; endpoint URLs are never
  exposed or user-editable in the app UI.

Verification:
- Native build succeeds.
- Manual smoke test against `http://127.0.0.1:8080`.
- `pytest -q`

## Phase 3: Native Command Panel UX

Scope:
- Recreate the current overlay behavior in SwiftUI:
  - textarea-style input
  - transcript view
  - model selector
  - send/stop state
  - dark mode
  - keyboard history
  - markdown/code rendering
- Keep the panel quiet and utility-focused.

Suggested commits:
- `feat(macos): add command panel input`
- `feat(macos): render streamed transcript`
- `feat(macos): add model picker`
- `feat(macos): add keyboard history`

Done when:
- The SwiftUI panel covers the core Hammerspoon overlay workflow.
- The panel is usable without Hammerspoon.

Verification:
- Native build succeeds.
- Manual test: query, stop, model select, history, dark mode.
- `pytest -q`

## Phase 4: Backend Lifecycle

Scope:
- Decide whether the app controls the backend through launchd or a bundled
  process runner.
- Add start/stop/restart controls.
- Show backend logs or a direct log-file shortcut.
- Keep the existing launchd plist as the first bridge if that is fastest.

Suggested commits:
- `feat(macos): manage agent service`
- `feat(macos): add backend status controls`

Done when:
- The app can detect, start, stop, and restart the local agent.
- Failure states are visible without checking Terminal.

Verification:
- Manual test: stopped agent -> start -> query -> stop.
- `pytest -q`

## Phase 5: Native macOS Integrations

Scope:
- Launch at login.
- File drop/attachment support.
- Selected-text capture.
- Share extension or Services menu action.
- Notifications for long-running tasks.

Suggested commits:
- `feat(macos): add launch at login`
- `feat(macos): add file attachments`
- `feat(macos): add selected text capture`

Done when:
- Common macOS workflows do not require opening the overlay first.
- Permissions and failure states are clear.

Verification:
- Native build succeeds.
- Manual permission and workflow tests.
- `pytest -q`

## Phase 6: Hammerspoon Decommission Path

Scope:
- Keep Hammerspoon install as a fallback until the native app is stable.
- Document migration steps.
- Remove or archive Hammerspoon-only workflows when replaced.

Suggested commits:
- `docs(macos): document native app setup`
- `chore(overlay): mark Hammerspoon overlay legacy`

Done when:
- The native app is the default path.
- The old overlay is clearly labeled as legacy or removed by explicit choice.

Verification:
- Fresh setup instructions work from a clean clone.
- `pytest -q`
