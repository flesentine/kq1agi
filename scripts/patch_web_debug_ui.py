#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_debug_ui.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()

# Always-visible browser debug controls. DEBUG stays labelled DEBUG even while
# active; the yellow active state tells the user they are editing.
style_anchor = '''  </style>\n'''
style_repl = '''    #debug-snap-button {
      position: fixed; top: 14px; right: 86px; z-index: 10001; display: none;
      padding: 9px 13px; border: 2px solid #fff; border-radius: 8px;
      background: rgba(15, 15, 15, 0.90); color: #fff;
      font: 700 13px system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      letter-spacing: .04em; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,.45);
    }
    #debug-snap-button:hover { background: #333; }
    #debug-snap-button:active { transform: translateY(1px); }
    #paint-button.debug-active {
      border-color: #ffd84d; box-shadow: 0 0 0 2px rgba(255,216,77,.22), 0 2px 8px rgba(0,0,0,.45);
      background: rgba(70, 57, 8, .94);
    }
    #export-bg-button { right: 198px; }
    #debug-tools { display: grid; gap: 6px; margin-top: 9px; }
    #move-sprite-button, #debug-copy-button {
      width: 100%; box-sizing: border-box; padding: 9px 10px;
      border: 1px solid #aaa; border-radius: 7px; background: #222; color: #fff;
      font: 700 12px system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      cursor: pointer;
    }
    #move-sprite-button:hover, #debug-copy-button:hover { background: #383838; }
    #move-sprite-button { border-color: #ffd84d; }
    #debug-move-help { font-size: 10px; line-height: 1.25; opacity: .78; font-weight: 500; }
    #debug-copy-button { margin-top: 10px; font-size: 14px; }
  </style>\n'''
if text.count(style_anchor) != 1:
    raise RuntimeError('final style close anchor not found')
text = text.replace(style_anchor, style_repl, 1)

button_anchor = '''<button id="paint-button" type="button" title="Open debug edit mode (Tab shortcut)">DEBUG</button>\n<div id="brush-control" aria-label="Debug brush size">\n'''
button_repl = '''<button id="debug-snap-button" type="button" title="Capture the game with debug text stamped onto the image">COPY DEBUG</button>\n<button id="paint-button" type="button" title="Open debug edit mode (Tab shortcut)">DEBUG</button>\n<div id="brush-control" aria-label="Debug brush size">\n'''
if text.count(button_anchor) != 1:
    raise RuntimeError('final DEBUG button anchor not found')
text = text.replace(button_anchor, button_repl, 1)

brush_anchor = '''  <div class="brush-hint">1 px = single mask pixel · Space + drag = pan</div>\n</div>\n'''
brush_repl = '''  <div class="brush-hint">1 px = single mask pixel · Space + drag = pan</div>\n  <div id="debug-tools">\n    <button id="move-sprite-button" type="button">MOVE SPRITE</button>\n    <div id="debug-move-help">Click MOVE SPRITE, click the sprite once, then drag anywhere in the game.</div>\n  </div>\n</div>\n'''
if text.count(brush_anchor) != 1:
    raise RuntimeError('debug brush panel anchor not found')
text = text.replace(brush_anchor, brush_repl, 1)

capture_anchor = '''    <div id="debug-help">Enter = copy screenshot + issue to clipboard · Esc = cancel</div>\n'''
capture_repl = '''    <button id="debug-copy-button" type="button">COPY IMAGE + TEXT</button>\n    <div id="debug-help">Your note is stamped directly onto the screenshot. Enter = copy · Esc = cancel.</div>\n'''
if text.count(capture_anchor) != 1:
    raise RuntimeError('debug capture help anchor not found')
text = text.replace(capture_anchor, capture_repl, 1)

const_anchor = '''  const debugToast = document.getElementById('debug-toast');\n  let debugSnapshot = null;\n'''
const_repl = '''  const debugToast = document.getElementById('debug-toast');\n  const debugSnapButton = document.getElementById('debug-snap-button');\n  const moveSpriteButton = document.getElementById('move-sprite-button');\n  const debugCopyButton = document.getElementById('debug-copy-button');\n  let debugSnapshot = null;\n'''
if text.count(const_anchor) != 1:
    raise RuntimeError('debug capture const anchor not found')
text = text.replace(const_anchor, const_repl, 1)

active_old = '''  function setPaintUiActive(active) {\n    paintUiActive = !!active;\n    brushControl.style.display = paintUiActive ? 'block' : 'none';\n    paintButton.textContent = paintUiActive ? 'TEST' : 'DEBUG';\n    paintButton.title = paintUiActive ? 'Return to live test mode (Tab shortcut)' : 'Open debug edit mode (Tab shortcut)';\n  }\n'''
active_new = '''  function setPaintUiActive(active) {\n    paintUiActive = !!active;\n    brushControl.style.display = paintUiActive ? 'block' : 'none';\n    paintButton.textContent = 'DEBUG';\n    paintButton.classList.toggle('debug-active', paintUiActive);\n    paintButton.title = paintUiActive ? 'Debug edit mode is active — click to exit (Tab shortcut)' : 'Open debug edit mode (Tab shortcut)';\n  }\n'''
if text.count(active_old) != 1:
    raise RuntimeError('setPaintUiActive anchor not found')
text = text.replace(active_old, active_new, 1)

# The copied artifact remains one image: the issue text is overlaid on top of the
# game instead of living in a separate footer.
font_old = '''    const fontSize = Math.max(18, Math.round(debugSnapshot.width / 48));\n'''
font_new = '''    const fontSize = Math.max(12, Math.round(debugSnapshot.width / 55));\n'''
if text.count(font_old) != 1:
    raise RuntimeError('debug capture font size anchor not found')
text = text.replace(font_old, font_new, 1)

lines_old = '''    const lines = wrapDebugText(ctx, issue, debugSnapshot.width - padding * 2);\n    const footerHeight = padding * 2 + lineHeight * (lines.length + 2);\n\n    output.width = debugSnapshot.width;\n    output.height = debugSnapshot.height + footerHeight;\n    const out = output.getContext('2d', { alpha: false });\n    out.drawImage(debugSnapshot, 0, 0);\n    out.fillStyle = '#080808';\n    out.fillRect(0, debugSnapshot.height, output.width, footerHeight);\n    out.font = '700 ' + fontSize + 'px system-ui, -apple-system, BlinkMacSystemFont, sans-serif';\n    out.fillStyle = '#ffffff';\n    let y = debugSnapshot.height + padding + fontSize;\n    out.fillText('ISSUE:', padding, y);\n    y += lineHeight;\n    out.font = '600 ' + fontSize + 'px system-ui, -apple-system, BlinkMacSystemFont, sans-serif';\n    for (const line of lines) {\n      out.fillText(line, padding, y);\n      y += lineHeight;\n    }\n    out.font = '500 ' + Math.max(12, Math.round(fontSize * .7)) + 'px monospace';\n    out.fillStyle = '#bdbdbd';\n    out.fillText(location.href, padding, y);\n    y += Math.round(lineHeight * .85);\n    out.fillText(new Date().toISOString(), padding, y);\n'''
lines_new = '''    const lines = wrapDebugText(ctx, issue, debugSnapshot.width - padding * 2).slice(0, 3);\n    const footerHeight = padding * 2 + lineHeight * (lines.length + 3);\n\n    output.width = debugSnapshot.width;\n    output.height = debugSnapshot.height;\n    const out = output.getContext('2d', { alpha: false });\n    out.drawImage(debugSnapshot, 0, 0);\n    const overlayHeight = Math.min(debugSnapshot.height, footerHeight);\n    const overlayTop = debugSnapshot.height - overlayHeight;\n    out.fillStyle = 'rgba(0,0,0,.78)';\n    out.fillRect(0, overlayTop, output.width, overlayHeight);\n    out.font = '700 ' + fontSize + 'px system-ui, -apple-system, BlinkMacSystemFont, sans-serif';\n    out.fillStyle = '#ffffff';\n    let y = overlayTop + padding + fontSize;\n    out.fillText('ISSUE:', padding, y);\n    y += lineHeight;\n    out.font = '600 ' + fontSize + 'px system-ui, -apple-system, BlinkMacSystemFont, sans-serif';\n    for (const line of lines) {\n      out.fillText(line, padding, y);\n      y += lineHeight;\n    }\n    out.font = '500 ' + Math.max(10, Math.round(fontSize * .7)) + 'px monospace';\n    out.fillStyle = '#d0d0d0';\n    out.fillText(location.href, padding, y);\n    y += Math.round(lineHeight * .85);\n    out.fillText(new Date().toISOString(), padding, y);\n'''
if text.count(lines_old) != 1:
    raise RuntimeError('debug capture output block not found')
text = text.replace(lines_old, lines_new, 1)

listener_anchor = '''  paintButton.addEventListener('mousedown', event => {\n'''
listeners = '''  function openCopyDebugFromButton() {\n    if (!paintUiActive) {\n      sendF2();\n      setPaintUiActive(true);\n      if (paintUiActive) applyBrushSize(brushSize);\n      setTimeout(openDebugCapture, 120);\n      return;\n    }\n    openDebugCapture();\n  }\n\n  debugSnapButton.addEventListener('mousedown', event => {\n    event.preventDefault();\n    event.stopPropagation();\n  });\n  debugSnapButton.addEventListener('click', event => {\n    event.preventDefault();\n    event.stopPropagation();\n    openCopyDebugFromButton();\n  });\n\n  moveSpriteButton.addEventListener('mousedown', event => {\n    event.preventDefault();\n    event.stopPropagation();\n  });\n  moveSpriteButton.addEventListener('click', event => {\n    event.preventDefault();\n    event.stopPropagation();\n    if (!paintUiActive) {\n      sendF2();\n      setPaintUiActive(true);\n    }\n    tapGameKey('5', 'Digit5', 53);\n    focusGameCanvas();\n  });\n\n  debugCopyButton.addEventListener('click', event => {\n    event.preventDefault();\n    event.stopPropagation();\n    copyDebugCapture().catch(error => {\n      console.error(error);\n      alert('Could not copy the debug capture: ' + error.message);\n    });\n  });\n\n  paintButton.addEventListener('mousedown', event => {\n'''
if text.count(listener_anchor) != 1:
    raise RuntimeError('paint button listener anchor not found')
text = text.replace(listener_anchor, listeners, 1)

show_pair = '''        paintButton.style.display = 'block';\n        exportBgButton.style.display = 'block';\n'''
show_pair_new = '''        paintButton.style.display = 'block';\n        debugSnapButton.style.display = 'block';\n        exportBgButton.style.display = 'block';\n'''
show_count = text.count(show_pair)
if show_count < 1:
    raise RuntimeError('no game-ready button display block found')
text = text.replace(show_pair, show_pair_new)

hide_pair = '''    paintButton.style.display = 'none';\n    exportBgButton.style.display = 'none';\n'''
hide_pair_new = '''    paintButton.style.display = 'none';\n    debugSnapButton.style.display = 'none';\n    exportBgButton.style.display = 'none';\n'''
if text.count(hide_pair) != 1:
    raise RuntimeError('recovery button hide block not found')
text = text.replace(hide_pair, hide_pair_new, 1)

path.write_text(text)
print('Debug browser UI improved: always-visible DEBUG + COPY DEBUG, MOVE SPRITE button, issue text stamped over capture')
