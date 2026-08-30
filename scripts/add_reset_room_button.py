#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_reset_room_button.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()

# Add the reset beside the existing current-room tools. The Java editor owns the
# actual state transition; the browser only confirms intent and sends command D.
button_anchor = '''          <button id="debug-clear-layer" type="button">CLEAR LAYER</button>\n          <button id="debug-save-mask" type="button">SAVE NOW</button>\n'''
button_repl = '''          <button id="debug-clear-layer" type="button">CLEAR LAYER</button>\n          <button id="debug-reset-game" type="button" title="Restore this room to the built-in/Sierra baseline; one Undo restores your current masks">RESET TO GAME</button>\n          <button id="debug-save-mask" type="button">SAVE NOW</button>\n'''
if text.count(button_anchor) != 1:
    raise RuntimeError(f'room tools button anchor: expected 1, found {text.count(button_anchor)}')
text = text.replace(button_anchor, button_repl, 1)

const_anchor = '''  const debugExportButton = document.getElementById('debug-export-bg');\n'''
const_repl = '''  const debugExportButton = document.getElementById('debug-export-bg');\n  const debugResetGameButton = document.getElementById('debug-reset-game');\n'''
if text.count(const_anchor) != 1:
    raise RuntimeError(f'reset button const anchor: expected 1, found {text.count(const_anchor)}')
text = text.replace(const_anchor, const_repl, 1)

listener_anchor = '''  debugUndoButton.addEventListener('click', () => sendEditorShortcut('u'));\n  debugRedoButton.addEventListener('click', () => sendEditorShortcut('y'));\n  debugExportButton.addEventListener('click', () => exportCleanBackground());\n'''
listener_repl = r'''  debugUndoButton.addEventListener('click', () => sendEditorShortcut('u'));
  debugRedoButton.addEventListener('click', () => sendEditorShortcut('y'));
  debugResetGameButton.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();
    const room = currentDebugRoom();
    if (!confirm('Reset ROOM ' + room + ' to the game default?\n\nYour current editable masks are kept as one UNDO step. Scripted FALL detection is not deleted.')) return;
    sendEditorShortcut('d');
    const old = debugResetGameButton.textContent;
    debugResetGameButton.textContent = 'RESET · UNDO READY';
    setTimeout(() => { debugResetGameButton.textContent = old; }, 1400);
  });
  debugExportButton.addEventListener('click', () => exportCleanBackground());
'''
if text.count(listener_anchor) != 1:
    raise RuntimeError(f'reset button listener anchor: expected 1, found {text.count(listener_anchor)}')
text = text.replace(listener_anchor, listener_repl, 1)

# A small visual warning distinguishes a room-wide reset from ordinary tools.
style_close = text.rfind('</style>')
if style_close < 0:
    raise RuntimeError('style close not found for reset button styling')
style = '''    #debug-reset-game {\n      border-color: #d08b62 !important;\n      background: #2d211b !important;\n    }\n    #debug-reset-game:hover { background: #493024 !important; }\n'''
text = text[:style_close] + style + text[style_close:]

path.write_text(text)
print('Debug RESET TO GAME button installed with confirmation and one-step Undo promise')
