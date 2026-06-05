# NeurOS Hammerspoon Overlay

Invocation surface for NeurOS on macOS. Binds `CMD+SHIFT+SPACE` to open a modal input that POSTs queries to the local agent.

## Install

```bash
make overlay-install
```

Then reload Hammerspoon: `CMD+SHIFT+R`.

## Usage

1. Press `CMD+SHIFT+SPACE`
2. Type your query
3. Press `Enter` to send → NeurOS responds in the overlay window
4. Press `Escape` or click outside to dismiss

## Configuration

Edit `init.lua` to adjust:
- Agent URL (default: `http://localhost:8000`)
- Window size and position
- Key bindings
- Font and colors
