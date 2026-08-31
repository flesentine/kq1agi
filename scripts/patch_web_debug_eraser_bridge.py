#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_debug_eraser_bridge.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


# The ERASE button used to rely on a synthetic E KeyboardEvent. Chrome/GWT can
# delay or swallow that event, and when it races the direct bridge it can toggle
# Java back out of erase mode after the sidebar already says ERASE. Keep the
# SharedArrayBuffer command as the single source of truth for browser controls.
old_helper = '''  function writeDebugOpacityBridge(value) {\n    const opacity = Math.max(25, Math.min(100, Number(value) || 70));\n    return writeDebugBridgeValue(5827, opacity);\n  }\n\n'''
new_helper = '''  function writeDebugOpacityBridge(value) {\n    const opacity = Math.max(25, Math.min(100, Number(value) || 70));\n    return writeDebugBridgeValue(5827, opacity);\n  }\n\n  function writeDebugEraserBridge(erase) {\n    // 100 = paint, 101 = erase. Java consumes this as a one-shot command.\n    return writeDebugBridgeValue(5828, erase ? 101 : 100);\n  }\n\n'''
one(old_helper, new_helper, 'debug eraser bridge helper')

# Every workspace state change already comes through this renderer. Reconcile the
# Java eraser state here so layer changes, mode changes, and the ERASE button all
# become authoritative.
old_buttons = '''  function debugModeButtons() {\n    debugModePaint.classList.toggle('debug-selected', debugMode === 'paint');\n    debugModeSprites.classList.toggle('debug-selected', debugMode === 'sprites');\n    debugModeInspect.classList.toggle('debug-selected', debugMode === 'inspect');\n    debugEraserButton.classList.toggle('debug-selected', debugEraserActive && debugMode === 'paint');\n  }\n'''
new_buttons = '''  function debugModeButtons() {\n    debugModePaint.classList.toggle('debug-selected', debugMode === 'paint');\n    debugModeSprites.classList.toggle('debug-selected', debugMode === 'sprites');\n    debugModeInspect.classList.toggle('debug-selected', debugMode === 'inspect');\n    debugEraserButton.classList.toggle('debug-selected', debugEraserActive && debugMode === 'paint');\n    if (paintUiActive) writeDebugEraserBridge(debugMode === 'paint' && debugEraserActive);\n  }\n'''
one(old_buttons, new_buttons, 'debug eraser state reconciliation')

# Do not also synthesize E from the browser button. The synthetic key and the
# direct absolute bridge can arrive in opposite orders in Chrome, which makes the
# engine toggle back to paint while the UI still shows ERASE selected.
old_click = '''  debugEraserButton.addEventListener('click', event => {\n    event.preventDefault();\n    event.stopPropagation();\n    ensureDebugEditorActive();\n    if (debugMode !== 'paint') setDebugMode('paint');\n    sendEditorShortcut('e');\n    debugEraserActive = !debugEraserActive;\n    debugModeButtons();\n    updateDebugWorkspaceStatus();\n  });\n'''
new_click = '''  debugEraserButton.addEventListener('click', event => {\n    event.preventDefault();\n    event.stopPropagation();\n    ensureDebugEditorActive();\n    if (debugMode !== 'paint') setDebugMode('paint');\n    debugEraserActive = !debugEraserActive;\n    debugModeButtons();\n    updateDebugWorkspaceStatus();\n    focusGameCanvas();\n  });\n'''
one(old_click, new_click, 'debug eraser click direct-only path')

old_tag = "const BUILD_TAG = '20260829-fall-accessible-v9-zero-counts';"
new_tag = "const BUILD_TAG = '20260829-debug-eraser-bridge-v2';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('debug eraser bridge build tag not found')

path.write_text(text)
print('Debug ERASE browser bridge installed: direct absolute state only; synthetic E race removed')
