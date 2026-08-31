#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: enforce_original_readonly_runtime.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

# SIERRA is a comparison source, never an editable state. Browser buttons are
# disabled too, but enforce this at the engine boundary so physical shortcuts or
# delayed synthetic input cannot mutate authored masks while ORIGINAL is shown.
key_method = text.find('    public boolean keyDown(int keycode)')
if key_method < 0:
    raise RuntimeError('SceneMaskEditor keyDown not found for ORIGINAL read-only lock')
anchor = '        if (!paintMode) return false;\n\n'
pos = text.find(anchor, key_method)
if pos < 0:
    raise RuntimeError('SceneMaskEditor keyDown paint-mode anchor not found for ORIGINAL read-only lock')
insert = '''        if (!paintMode) return false;\n\n        if (sourceOriginalView && keycode != Input.Keys.SPACE) {\n            // F2/browser PLAY is handled before this point. SPACE remains available\n            // for read-only panning; every edit/move/undo/reset shortcut is consumed.\n            notice("SIERRA ORIGINAL - READ ONLY");\n            return true;\n        }\n\n'''
text = text[:pos] + insert + text[pos + len(anchor):]

# Belt-and-suspenders canvas guard. inspectMode normally consumes paint gestures,
# but this prevents a future mode transition from ever painting hidden edited
# pixels while the source selector still says SIERRA.
touch_method = text.find('    public boolean touchDown(')
if touch_method < 0:
    raise RuntimeError('SceneMaskEditor touchDown not found for ORIGINAL read-only lock')
touch_anchor = '        if (!paintMode) return false;\n'
touch_pos = text.find(touch_anchor, touch_method)
if touch_pos < 0:
    raise RuntimeError('SceneMaskEditor touchDown paint-mode anchor not found for ORIGINAL read-only lock')
touch_insert = '''        if (!paintMode) return false;\n        if (sourceOriginalView && !(spacePan && zoom > 1)) {\n            notice("SIERRA ORIGINAL - READ ONLY");\n            return true;\n        }\n'''
text = text[:touch_pos] + touch_insert + text[touch_pos + len(touch_anchor):]

editor.write_text(text)
print('SIERRA ORIGINAL runtime lock installed: physical shortcuts and canvas edits cannot mutate authored masks')
