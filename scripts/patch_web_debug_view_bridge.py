#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_debug_view_bridge.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def replace_one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


# PR #19 still routed VIEW through synthetic 7/8/9 KeyboardEvents. Those events
# can be swallowed by the browser/GWT input path even though the sidebar button
# itself updates. Write the requested visibility mask straight into the same
# SharedArrayBuffer used by SceneMaskEditor instead.
helper_anchor = '''  function setAllOverlayVisibility(visible) {\n'''
helpers = '''  function writeDebugVisibilityBridge(mask) {\n    const sab = window.__kq1agiVariableSAB;\n    if (!sab) return false;\n    try {\n      const values = new Int32Array(sab);\n      const index = 5825;\n      if (values.length <= index) return false;\n      // 0 releases browser control. 100..131 encode NONE through ALL.\n      Atomics.store(values, index, mask == null ? 0 : (100 + (Number(mask) & 31)));\n      return true;\n    } catch (error) {\n      console.warn('DEBUG view bridge unavailable', error);\n      return false;\n    }\n  }\n\n  function applyDebugVisibilityBridgeMask(mask, fallbackKey) {\n    if (!writeDebugVisibilityBridge(mask)) sendEditorShortcut(fallbackKey);\n  }\n\n  function setAllOverlayVisibility(visible) {\n'''
replace_one(helper_anchor, helpers, 'view bridge helper anchor')

replace_one(
'''    if (paintUiActive && debugMode !== 'sprites') sendEditorShortcut(visible ? '8' : '9');\n''',
'''    if (paintUiActive && debugMode !== 'sprites')\n      applyDebugVisibilityBridgeMask(visible ? 31 : 0, visible ? '8' : '9');\n''',
'ALL/NONE bridge dispatch'
)

replace_one(
'''    if (mode === 'all') {\n      sendEditorShortcut('8');\n      for (let layer = 1; layer <= 5; layer++) overlayVisibility[layer] = true;\n    } else if (mode === 'none') {\n      sendEditorShortcut('9');\n      for (let layer = 1; layer <= 5; layer++) overlayVisibility[layer] = false;\n    } else {\n      sendEditorShortcut('7');\n      for (let layer = 1; layer <= 5; layer++) overlayVisibility[layer] = layer === selectedDebugLayer;\n    }\n''',
'''    if (mode === 'all') {\n      applyDebugVisibilityBridgeMask(31, '8');\n      for (let layer = 1; layer <= 5; layer++) overlayVisibility[layer] = true;\n    } else if (mode === 'none') {\n      applyDebugVisibilityBridgeMask(0, '9');\n      for (let layer = 1; layer <= 5; layer++) overlayVisibility[layer] = false;\n    } else {\n      const soloMask = 1 << (selectedDebugLayer - 1);\n      applyDebugVisibilityBridgeMask(soloMask, '7');\n      for (let layer = 1; layer <= 5; layer++) overlayVisibility[layer] = layer === selectedDebugLayer;\n    }\n''',
'view mode bridge dispatch'
)

# Manual layer visibility should intentionally leave absolute preset mode, so
# release the bridge before sending the existing R/B/G/W/V toggle.
replace_one(
'''    const key = visibilityKeys[layer];\n    if (!key) return;\n    sendEditorShortcut(key);\n''',
'''    const key = visibilityKeys[layer];\n    if (!key) return;\n    writeDebugVisibilityBridge(null);\n    sendEditorShortcut(key);\n''',
'manual visibility bridge release'
)

# A real R/B/G/W/V keystroke bypasses setOverlayVisible. Release the bridge in
# capture phase so SceneMaskEditor's normal toggle is not overwritten next frame.
keyboard_anchor = '''  // Native-feeling undo/redo on desktop.\n'''
keyboard_bridge = '''  window.addEventListener('keydown', event => {\n    if (!paintUiActive || !event.isTrusted || event.repeat || event.metaKey || event.ctrlKey || event.altKey) return;\n    if (!['r', 'b', 'g', 'w', 'v'].includes(event.key.toLowerCase())) return;\n    writeDebugVisibilityBridge(null);\n  }, true);\n\n  // Native-feeling undo/redo on desktop.\n'''
replace_one(keyboard_anchor, keyboard_bridge, 'trusted manual visibility bridge release')

old_tag = "const BUILD_TAG = '20260827-debug-workspace-v3-views1';"
new_tag = "const BUILD_TAG = '20260827-debug-workspace-v3-views2';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('direct view bridge build tag not found')

path.write_text(text)
print('Debug view browser bridge installed: SOLO/ALL/NONE write exact visibility bits to shared slot 5825')
