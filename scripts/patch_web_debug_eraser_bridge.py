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


# The ERASE button currently updates browser-local state and then synthesizes an
# E key. That key can be swallowed before libGDX sees it. Use a one-shot absolute
# state command in the same SharedArrayBuffer used by the other debug controls.
old_helper = '''  function writeDebugOpacityBridge(value) {\n    const opacity = Math.max(25, Math.min(100, Number(value) || 70));\n    return writeDebugBridgeValue(5827, opacity);\n  }\n\n'''
new_helper = '''  function writeDebugOpacityBridge(value) {\n    const opacity = Math.max(25, Math.min(100, Number(value) || 70));\n    return writeDebugBridgeValue(5827, opacity);\n  }\n\n  function writeDebugEraserBridge(erase) {\n    // 100 = paint, 101 = erase. Java consumes this as a one-shot command.\n    return writeDebugBridgeValue(5828, erase ? 101 : 100);\n  }\n\n'''
one(old_helper, new_helper, 'debug eraser bridge helper')

# Every workspace state change already comes through this renderer. Reconcile the
# Java eraser state here so layer changes, mode changes, and the ERASE button all
# become authoritative even when their synthetic keyboard fallbacks are ignored.
old_buttons = '''  function debugModeButtons() {\n    debugModePaint.classList.toggle('debug-selected', debugMode === 'paint');\n    debugModeSprites.classList.toggle('debug-selected', debugMode === 'sprites');\n    debugModeInspect.classList.toggle('debug-selected', debugMode === 'inspect');\n    debugEraserButton.classList.toggle('debug-selected', debugEraserActive && debugMode === 'paint');\n  }\n'''
new_buttons = '''  function debugModeButtons() {\n    debugModePaint.classList.toggle('debug-selected', debugMode === 'paint');\n    debugModeSprites.classList.toggle('debug-selected', debugMode === 'sprites');\n    debugModeInspect.classList.toggle('debug-selected', debugMode === 'inspect');\n    debugEraserButton.classList.toggle('debug-selected', debugEraserActive && debugMode === 'paint');\n    if (paintUiActive) writeDebugEraserBridge(debugMode === 'paint' && debugEraserActive);\n  }\n'''
one(old_buttons, new_buttons, 'debug eraser state reconciliation')

old_tag = "const BUILD_TAG = '20260829-fall-accessible-v9-zero-counts';"
new_tag = "const BUILD_TAG = '20260829-debug-eraser-bridge-v1';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('debug eraser bridge build tag not found')

path.write_text(text)
print('Debug ERASE browser bridge installed: sidebar state now drives Java eraser directly')
