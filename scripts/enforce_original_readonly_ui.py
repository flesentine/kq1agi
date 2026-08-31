#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: enforce_original_readonly_ui.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()

# The source-selector UX already disables primary paint controls. Extend the same
# lock to destructive Advanced controls so every visible mutation path agrees
# with the engine-level SIERRA ORIGINAL read-only contract.
old = '''      'debug-fill-button', 'debug-outline-button', 'debug-undo-button', 'debug-redo-button',\n      'debug-view-solo', 'debug-view-all', 'debug-view-none'\n'''
new = '''      'debug-fill-button', 'debug-outline-button', 'debug-undo-button', 'debug-redo-button',\n      'debug-view-solo', 'debug-view-all', 'debug-view-none',\n      'debug-clear-layer', 'debug-reset-game', 'move-sprite-button', 'reset-sprite-button'\n'''
if text.count(old) != 1:
    raise RuntimeError(f'ORIGINAL UI lockIds anchor: expected 1, found {text.count(old)}')
text = text.replace(old, new, 1)

# Disabled controls should look intentionally locked rather than merely faded.
style_close = text.rfind('</style>')
if style_close < 0:
    raise RuntimeError('style close missing for ORIGINAL read-only UI lock')
css = '''    body.debug-source-original button:disabled,\n    body.debug-source-original input:disabled {\n      cursor: not-allowed !important;\n    }\n'''
text = text[:style_close] + css + text[style_close:]

path.write_text(text)
print('SIERRA ORIGINAL browser lock completed: destructive advanced controls disabled too')
