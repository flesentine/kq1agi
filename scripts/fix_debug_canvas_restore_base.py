#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_debug_canvas_restore.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def replace_one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)

# PR #18 visually scales the game canvas while DEBUG is open. Its first restore
# pass removed width/height from the canvas on TEST, but those properties belong
# to AGILE/libGDX. Removing them makes the canvas fall back to its large intrinsic
# render size, which looks like a zoomed/cropped game. Preserve AGILE's exact
# inline sizing before DEBUG and put it back on exit instead.
old_decl = '''  let debugCanvasBaseSize = null;\n\n  function captureDebugCanvasBaseSize() {\n'''
new_decl = '''  let debugCanvasBaseSize = null;\n  let debugCanvasBaseStyle = null;\n\n  function captureDebugCanvasBaseSize() {\n'''
replace_one(old_decl, new_decl, 'debug canvas style snapshot declaration')

old_capture = '''    const rect = canvas.getBoundingClientRect();\n    if (rect.width > 0 && rect.height > 0) {\n      debugCanvasBaseSize = { width: rect.width, height: rect.height };\n    }\n  }\n\n  function clearDebugCanvasFit() {\n    const canvas = gameCanvas();\n    if (!canvas) return;\n    canvas.style.removeProperty('width');\n    canvas.style.removeProperty('height');\n    canvas.style.removeProperty('max-width');\n    canvas.style.removeProperty('max-height');\n  }\n'''
new_capture = '''    const rect = canvas.getBoundingClientRect();\n    if (rect.width > 0 && rect.height > 0) {\n      debugCanvasBaseSize = { width: rect.width, height: rect.height };\n      debugCanvasBaseStyle = {\n        width: canvas.style.getPropertyValue('width'),\n        widthPriority: canvas.style.getPropertyPriority('width'),\n        height: canvas.style.getPropertyValue('height'),\n        heightPriority: canvas.style.getPropertyPriority('height'),\n        maxWidth: canvas.style.getPropertyValue('max-width'),\n        maxWidthPriority: canvas.style.getPropertyPriority('max-width'),\n        maxHeight: canvas.style.getPropertyValue('max-height'),\n        maxHeightPriority: canvas.style.getPropertyPriority('max-height')\n      };\n    }\n  }\n\n  function restoreDebugCanvasStyleProperty(canvas, name, value, priority) {\n    if (value) canvas.style.setProperty(name, value, priority || '');\n    else canvas.style.removeProperty(name);\n  }\n\n  function clearDebugCanvasFit() {\n    const canvas = gameCanvas();\n    if (!canvas) return;\n\n    const saved = debugCanvasBaseStyle;\n    if (saved) {\n      restoreDebugCanvasStyleProperty(canvas, 'width', saved.width, saved.widthPriority);\n      restoreDebugCanvasStyleProperty(canvas, 'height', saved.height, saved.heightPriority);\n      restoreDebugCanvasStyleProperty(canvas, 'max-width', saved.maxWidth, saved.maxWidthPriority);\n      restoreDebugCanvasStyleProperty(canvas, 'max-height', saved.maxHeight, saved.maxHeightPriority);\n    } else {\n      canvas.style.removeProperty('width');\n      canvas.style.removeProperty('height');\n      canvas.style.removeProperty('max-width');\n      canvas.style.removeProperty('max-height');\n    }\n\n    debugCanvasBaseStyle = null;\n\n    // Give AGILE/libGDX one normal browser resize pass after the dock disappears.\n    // This also handles a browser resize that happened while DEBUG was open.\n    requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));\n  }\n'''
replace_one(old_capture, new_capture, 'debug canvas exact style restore')

old_tag = "const BUILD_TAG = '20260827-debug-workspace-v3-fit1';"
new_tag = "const BUILD_TAG = '20260827-debug-workspace-v3-fit2';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('debug canvas restore build tag not found')

path.write_text(text)
print('Debug TEST restore fixed: AGILE canvas sizing is preserved and restored instead of removed')
