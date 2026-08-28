#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_debug_view_presets_runtime.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()


def replace_one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)

# Browser SOLO/ALL/NONE used to be implemented by guessing the Java editor's
# current per-layer visibility and then sending toggle keys. Once the browser
# and Java state drifted, the buttons could look selected while changing
# nothing. Give the editor absolute visibility presets instead.
helper_anchor = '''    private boolean optionEraseHeld() {\n'''
helpers = '''    private void applyOverlayVisibilityPreset(int preset) {\n        if (preset == 8) {\n            for (int layer = 0; layer < layerVisible.length; layer++) layerVisible[layer] = true;\n            notice("VIEW ALL");\n            return;\n        }\n\n        for (int layer = 0; layer < layerVisible.length; layer++) layerVisible[layer] = false;\n        if (preset == 7) {\n            int layer = selectedLayer();\n            if (layer >= 0 && layer < layerVisible.length) layerVisible[layer] = true;\n            // Scripted FALL orange is rendered under layerVisible[FALL], so SOLO\n            // FALL still shows both editable magenta and original scripted danger.\n            notice("VIEW SOLO");\n        } else {\n            notice("VIEW NONE");\n        }\n    }\n\n    private boolean optionEraseHeld() {\n'''
replace_one(helper_anchor, helpers, 'overlay visibility preset helper')

key_anchor = '''        if (keycode == Input.Keys.U) {\n'''
key_repl = '''        if (keycode == Input.Keys.NUM_7) {\n            applyOverlayVisibilityPreset(7);\n            return true;\n        }\n        if (keycode == Input.Keys.NUM_8) {\n            applyOverlayVisibilityPreset(8);\n            return true;\n        }\n        if (keycode == Input.Keys.NUM_9) {\n            applyOverlayVisibilityPreset(9);\n            return true;\n        }\n        if (keycode == Input.Keys.U) {\n'''
replace_one(key_anchor, key_repl, 'overlay visibility preset keys')

editor.write_text(text)
print('Debug view presets installed: 7=SOLO, 8=ALL, 9=NONE are absolute editor states')
