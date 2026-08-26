#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_reset_sprite_button.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()

button_anchor = '''    <button id="move-sprite-button" type="button">MOVE SPRITE</button>\n    <div id="debug-move-help">Click MOVE SPRITE, click the sprite once, then drag anywhere in the game.</div>\n'''
button_repl = '''    <button id="move-sprite-button" type="button">MOVE SPRITE</button>\n    <button id="reset-sprite-button" type="button" style="width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid #ff8b8b;border-radius:7px;background:#2a1717;color:#fff;font:700 12px system-ui,-apple-system,BlinkMacSystemFont,sans-serif;cursor:pointer;">RESET SPRITE</button>\n    <div id="debug-move-help">MOVE SPRITE pins the selected sprite. RESET SPRITE removes that pin and returns it to normal AGI movement. Backspace also resets while in MOVE mode.</div>\n'''
if text.count(button_anchor) != 1:
    raise RuntimeError('MOVE SPRITE button anchor not found')
text = text.replace(button_anchor, button_repl, 1)

const_anchor = '''  const moveSpriteButton = document.getElementById('move-sprite-button');\n  const debugCopyButton = document.getElementById('debug-copy-button');\n'''
const_repl = '''  const moveSpriteButton = document.getElementById('move-sprite-button');\n  const resetSpriteButton = document.getElementById('reset-sprite-button');\n  const debugCopyButton = document.getElementById('debug-copy-button');\n'''
if text.count(const_anchor) != 1:
    raise RuntimeError('MOVE SPRITE const anchor not found')
text = text.replace(const_anchor, const_repl, 1)

listener_anchor = '''  debugCopyButton.addEventListener('click', event => {\n'''
listener_repl = '''  resetSpriteButton.addEventListener('mousedown', event => {\n    event.preventDefault();\n    event.stopPropagation();\n  });\n  resetSpriteButton.addEventListener('click', event => {\n    event.preventDefault();\n    event.stopPropagation();\n    if (!paintUiActive) {\n      sendF2();\n      setPaintUiActive(true);\n    }\n    // MOVE mode auto-selects ego; Backspace removes its room+view visual pin.\n    tapGameKey('5', 'Digit5', 53);\n    setTimeout(() => {\n      tapGameKey('Backspace', 'Backspace', 8);\n      focusGameCanvas();\n      const old = resetSpriteButton.textContent;\n      resetSpriteButton.textContent = 'SPRITE RESET';\n      setTimeout(() => { resetSpriteButton.textContent = old; }, 900);\n    }, 40);\n  });\n\n  debugCopyButton.addEventListener('click', event => {\n'''
if text.count(listener_anchor) != 1:
    raise RuntimeError('debug copy listener anchor not found')
text = text.replace(listener_anchor, listener_repl, 1)

path.write_text(text)
print('RESET SPRITE safety button installed')
