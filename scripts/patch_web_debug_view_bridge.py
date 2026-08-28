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


# Keep the debug DISPLAY controls authoritative through the SharedArrayBuffer.
# Synthetic KeyboardEvents can update the sidebar while never reaching libGDX,
# which is exactly what made VIEW, OUTLINE, and OVERLAY appear to do nothing.
helper_anchor = '''  function setAllOverlayVisibility(visible) {\n'''
helpers = '''  function writeDebugBridgeValue(index, value) {\n    const sab = window.__kq1agiVariableSAB;\n    if (!sab) return false;\n    try {\n      const values = new Int32Array(sab);\n      if (values.length <= index) return false;\n      Atomics.store(values, index, Number(value) | 0);\n      return true;\n    } catch (error) {\n      console.warn('DEBUG display bridge unavailable', error);\n      return false;\n    }\n  }\n\n  function writeDebugVisibilityBridge(mask) {\n    // 0 releases browser control. 100..131 encode NONE through ALL.\n    return writeDebugBridgeValue(5825, mask == null ? 0 : (100 + (Number(mask) & 31)));\n  }\n\n  function writeDebugOutlineBridge(outline) {\n    // 100 = fill, 101 = outline. Zero remains available as unmanaged.\n    return writeDebugBridgeValue(5826, outline ? 101 : 100);\n  }\n\n  function writeDebugOpacityBridge(value) {\n    const opacity = Math.max(25, Math.min(100, Number(value) || 70));\n    return writeDebugBridgeValue(5827, opacity);\n  }\n\n  function applyDebugVisibilityBridgeMask(mask, fallbackKey) {\n    if (!writeDebugVisibilityBridge(mask)) sendEditorShortcut(fallbackKey);\n  }\n\n  function setAllOverlayVisibility(visible) {\n'''
replace_one(helper_anchor, helpers, 'debug display bridge helper anchor')

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

# Manual layer visibility intentionally leaves absolute preset mode, so release
# the visibility bridge before sending the existing R/B/G/W/V toggle.
replace_one(
'''    const key = visibilityKeys[layer];\n    if (!key) return;\n    sendEditorShortcut(key);\n''',
'''    const key = visibilityKeys[layer];\n    if (!key) return;\n    writeDebugVisibilityBridge(null);\n    sendEditorShortcut(key);\n''',
'manual visibility bridge release'
)

# FILL / OUTLINE now write absolute state directly. Keyboard O remains only as a
# fallback for environments where SharedArrayBuffer is not available.
replace_one(
'''  function setOutlineView(outline) {\n    debugOutline = !!outline;\n    if (paintUiActive && runtimeOutline !== debugOutline) {\n      sendEditorShortcut('o');\n      runtimeOutline = debugOutline;\n    }\n    debugFillButton.classList.toggle('debug-selected', !debugOutline);\n    debugOutlineButton.classList.toggle('debug-selected', debugOutline);\n    saveDebugWorkspacePrefs();\n  }\n''',
'''  function setOutlineView(outline) {\n    debugOutline = !!outline;\n    if (paintUiActive) {\n      if (!writeDebugOutlineBridge(debugOutline) && runtimeOutline !== debugOutline) {\n        sendEditorShortcut('o');\n      }\n      runtimeOutline = debugOutline;\n    }\n    debugFillButton.classList.toggle('debug-selected', !debugOutline);\n    debugOutlineButton.classList.toggle('debug-selected', debugOutline);\n    saveDebugWorkspacePrefs();\n  }\n''',
'outline direct bridge'
)

# OVERLAY opacity is also absolute now. The old fallback walked to 25% with comma
# keystrokes and back up with periods; keep that only if the direct bridge fails.
replace_one(
'''  function applyOverlayOpacity(value) {\n    overlayOpacity = Math.max(25, Math.min(100, Math.round((Number(value) || 70) / 5) * 5));\n    debugOpacity.value = String(overlayOpacity);\n    debugOpacityValue.textContent = overlayOpacity + '%';\n    if (paintUiActive) {\n      // Make the Java value absolute: clamp to 25%, then step upward.\n      for (let i = 0; i < 20; i++) tapGameKey(',', 'Comma', 188);\n      for (let value = 25; value < overlayOpacity; value += 5) tapGameKey('.', 'Period', 190);\n      runtimeOpacity = overlayOpacity;\n    }\n    saveDebugWorkspacePrefs();\n  }\n''',
'''  function applyOverlayOpacity(value) {\n    overlayOpacity = Math.max(25, Math.min(100, Math.round((Number(value) || 70) / 5) * 5));\n    debugOpacity.value = String(overlayOpacity);\n    debugOpacityValue.textContent = overlayOpacity + '%';\n    if (paintUiActive) {\n      if (!writeDebugOpacityBridge(overlayOpacity)) {\n        // Fallback for non-SAB environments: clamp to 25%, then step upward.\n        for (let i = 0; i < 20; i++) tapGameKey(',', 'Comma', 188);\n        for (let value = 25; value < overlayOpacity; value += 5) tapGameKey('.', 'Period', 190);\n      }\n      runtimeOpacity = overlayOpacity;\n    }\n    saveDebugWorkspacePrefs();\n  }\n''',
'opacity direct bridge'
)

# Apply opacity while the slider is moving instead of only after mouse-up.
replace_one(
'''  debugOpacity.addEventListener('input', event => {\n    overlayOpacity = Number(event.target.value);\n    debugOpacityValue.textContent = overlayOpacity + '%';\n  });\n''',
'''  debugOpacity.addEventListener('input', event => applyOverlayOpacity(event.target.value));\n''',
'live opacity slider'
)

# A real R/B/G/W/V keystroke bypasses setOverlayVisible. Release only the view
# bridge in capture phase so SceneMaskEditor's normal manual toggle can stick.
keyboard_anchor = '''  // Native-feeling undo/redo on desktop.\n'''
keyboard_bridge = '''  window.addEventListener('keydown', event => {\n    if (!paintUiActive || !event.isTrusted || event.repeat || event.metaKey || event.ctrlKey || event.altKey) return;\n    if (!['r', 'b', 'g', 'w', 'v'].includes(event.key.toLowerCase())) return;\n    writeDebugVisibilityBridge(null);\n  }, true);\n\n  // Native-feeling undo/redo on desktop.\n'''
replace_one(keyboard_anchor, keyboard_bridge, 'trusted manual visibility bridge release')

old_tag = "const BUILD_TAG = '20260827-debug-workspace-v3-views1';"
new_tag = "const BUILD_TAG = '20260827-debug-workspace-v3-display1';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('debug display bridge build tag not found')

path.write_text(text)
print('Debug display browser bridge installed: VIEW, FILL/OUTLINE, and live opacity use shared state')
