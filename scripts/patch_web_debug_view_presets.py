#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_debug_view_presets.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def replace_one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)

# Let sendEditorShortcut address the new absolute 7/8/9 Java presets.
replace_one("    const digit = /^[1-6]$/.test(lower);\n",
            "    const digit = /^[1-9]$/.test(lower);\n",
            'debug shortcut digit range')

old_views = '''  function setAllOverlayVisibility(visible) {\n    for (let layer = 1; layer <= 5; layer++) setOverlayVisible(layer, visible);\n  }\n\n  function applyDebugViewMode(mode) {\n    debugViewMode = mode;\n    debugViewSolo.classList.toggle('debug-selected', mode === 'solo');\n    debugViewAll.classList.toggle('debug-selected', mode === 'all');\n    debugViewNone.classList.toggle('debug-selected', mode === 'none');\n\n    if (!paintUiActive || debugMode === 'sprites') return;\n    if (mode === 'all') {\n      setAllOverlayVisibility(true);\n    } else if (mode === 'none') {\n      setAllOverlayVisibility(false);\n    } else {\n      for (let layer = 1; layer <= 5; layer++) setOverlayVisible(layer, layer === selectedDebugLayer);\n    }\n    saveDebugWorkspacePrefs();\n  }\n'''
new_views = '''  function setAllOverlayVisibility(visible) {\n    visible = !!visible;\n    if (paintUiActive && debugMode !== 'sprites') sendEditorShortcut(visible ? '8' : '9');\n    for (let layer = 1; layer <= 5; layer++) overlayVisibility[layer] = visible;\n    syncVisibilityButtons();\n  }\n\n  function applyDebugViewMode(mode) {\n    debugViewMode = mode;\n    debugViewSolo.classList.toggle('debug-selected', mode === 'solo');\n    debugViewAll.classList.toggle('debug-selected', mode === 'all');\n    debugViewNone.classList.toggle('debug-selected', mode === 'none');\n\n    if (!paintUiActive || debugMode === 'sprites') {\n      saveDebugWorkspacePrefs();\n      return;\n    }\n\n    // These are absolute Java-side presets, not a series of guessed toggles.\n    // That keeps the button state and the rendered overlays synchronized.\n    if (mode === 'all') {\n      sendEditorShortcut('8');\n      for (let layer = 1; layer <= 5; layer++) overlayVisibility[layer] = true;\n    } else if (mode === 'none') {\n      sendEditorShortcut('9');\n      for (let layer = 1; layer <= 5; layer++) overlayVisibility[layer] = false;\n    } else {\n      sendEditorShortcut('7');\n      for (let layer = 1; layer <= 5; layer++) overlayVisibility[layer] = layer === selectedDebugLayer;\n    }\n    syncVisibilityButtons();\n    saveDebugWorkspacePrefs();\n  }\n'''
replace_one(old_views, new_views, 'absolute SOLO/ALL/NONE browser views')

# If power users use R/B/G/W/V directly, mirror those trusted keyboard toggles
# back into the sidebar so the next preset starts from truthful browser state.
undo_anchor = '''  // Native-feeling undo/redo on desktop.\n'''
keyboard_sync = '''  window.addEventListener('keydown', event => {\n    if (!paintUiActive || !event.isTrusted || event.repeat || event.metaKey || event.ctrlKey || event.altKey) return;\n    const layer = ({ r: 1, b: 2, g: 3, w: 4, v: 5 })[event.key.toLowerCase()];\n    if (!layer) return;\n    overlayVisibility[layer] = !overlayVisibility[layer];\n    debugViewMode = 'manual';\n    debugViewSolo.classList.remove('debug-selected');\n    debugViewAll.classList.remove('debug-selected');\n    debugViewNone.classList.remove('debug-selected');\n    syncVisibilityButtons();\n  }, true);\n\n  // Native-feeling undo/redo on desktop.\n'''
replace_one(undo_anchor, keyboard_sync, 'trusted visibility keyboard sync')

old_tag = "const BUILD_TAG = '20260827-debug-workspace-v3-fit2';"
new_tag = "const BUILD_TAG = '20260827-debug-workspace-v3-views1';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('debug view preset build tag not found')

path.write_text(text)
print('Debug view controls fixed: SOLO/ALL/NONE now send absolute editor visibility presets')
