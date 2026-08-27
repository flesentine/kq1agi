#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_debug_workspace_launch.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def replace_one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)

# The dock is a vertical editor. v3 enabled display:flex but forgot to set the
# flex direction, which laid the header/tabs/tools out horizontally and clipped
# almost everything inside the narrow sidebar.
replace_one(
'''    #brush-control {\n      left: 0;\n''',
'''    #brush-control {\n      flex-direction: column;\n      align-items: stretch;\n      gap: 0;\n      left: 0;\n''',
'debug dock flex direction'
)

# Title/credits room 83 must remain normal gameplay. Opening the editor there
# consumes the "press any key" input, so DEBUG should not be enterable until the
# game has actually moved into a playable room.
set_active_anchor = '''  function setPaintUiActive(active) {\n    paintUiActive = !!active;\n'''
set_active_repl = '''  function debugWorkspaceAllowed() {\n    try {\n      const sab = window.__kq1agiVariableSAB;\n      if (!sab) return false;\n      const room = (new Int32Array(sab)[0] || 0) & 255;\n      return room > 0 && room !== 83;\n    } catch (error) {\n      return false;\n    }\n  }\n\n  function refreshDebugButtonAvailability() {\n    if (paintUiActive) return;\n    paintButton.style.display = debugWorkspaceAllowed() ? 'block' : 'none';\n  }\n\n  function setPaintUiActive(active) {\n    if (active && !debugWorkspaceAllowed()) {\n      paintUiActive = false;\n      document.body.classList.remove('debug-workspace');\n      brushControl.style.display = 'none';\n      paintButton.classList.remove('debug-active');\n      focusGameCanvas();\n      return;\n    }\n    paintUiActive = !!active;\n'''
replace_one(set_active_anchor, set_active_repl, 'debug workspace availability helper')

# Mouse DEBUG entry: do not send F2 at all on the title/credits screen.
click_old = '''  paintButton.addEventListener('click', event => {\n    event.preventDefault();\n    event.stopPropagation();\n    sendF2();\n    setPaintUiActive(!paintUiActive);\n    if (paintUiActive) applyBrushSize(brushSize);\n  });\n'''
click_new = '''  paintButton.addEventListener('click', event => {\n    event.preventDefault();\n    event.stopPropagation();\n    if (!paintUiActive && !debugWorkspaceAllowed()) {\n      focusGameCanvas();\n      return;\n    }\n    sendF2();\n    setPaintUiActive(!paintUiActive);\n    if (paintUiActive) applyBrushSize(brushSize);\n  });\n'''
replace_one(click_old, click_new, 'DEBUG button title-room guard')

# Tab entry gets the same guard so it remains harmless while the title screen is
# waiting for its normal key press.
tab_old = '''  window.addEventListener('keydown', event => {\n    if (event.key !== 'Tab' || event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;\n    event.preventDefault();\n    event.stopPropagation();\n    sendF2();\n    setPaintUiActive(!paintUiActive);\n    if (paintUiActive) applyBrushSize(brushSize);\n  }, true);\n'''
tab_new = '''  window.addEventListener('keydown', event => {\n    if (event.key !== 'Tab' || event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;\n    if (!paintUiActive && !debugWorkspaceAllowed()) return;\n    event.preventDefault();\n    event.stopPropagation();\n    sendF2();\n    setPaintUiActive(!paintUiActive);\n    if (paintUiActive) applyBrushSize(brushSize);\n  }, true);\n'''
replace_one(tab_old, tab_new, 'Tab title-room guard')

# A physical F2 is captured at window level before libGDX sees it. Block it on
# room 83 so browser state and engine paint state cannot become desynchronised.
f2_old = '''  window.addEventListener('keydown', event => {\n    if (!event.isTrusted || event.key !== 'F2' || event.repeat) return;\n    setPaintUiActive(!paintUiActive);\n    if (paintUiActive) applyBrushSize(brushSize);\n  }, true);\n'''
f2_new = '''  window.addEventListener('keydown', event => {\n    if (!event.isTrusted || event.key !== 'F2' || event.repeat) return;\n    if (!paintUiActive && !debugWorkspaceAllowed()) {\n      event.preventDefault();\n      event.stopImmediatePropagation();\n      focusGameCanvas();\n      return;\n    }\n    setPaintUiActive(!paintUiActive);\n    if (paintUiActive) applyBrushSize(brushSize);\n  }, true);\n'''
replace_one(f2_old, f2_new, 'F2 title-room guard')

# The base loader shows DEBUG as soon as a canvas exists. Correct that state on
# a short poll: hidden during room 83, then automatically available once the
# actual game room loads. This does not touch EXPORT BG.
insert_anchor = '''  brushControl.addEventListener('mousedown', event => {\n'''
insert_repl = '''  setInterval(refreshDebugButtonAvailability, 200);\n  setTimeout(refreshDebugButtonAvailability, 0);\n\n  brushControl.addEventListener('mousedown', event => {\n'''
replace_one(insert_anchor, insert_repl, 'DEBUG availability poll')

# Make this fix unmistakable in cached browser shells.
old_tag = "const BUILD_TAG = '20260827-debug-workspace-v3';"
new_tag = "const BUILD_TAG = '20260827-debug-workspace-v3-fix1';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('debug workspace build tag not found')

path.write_text(text)
print('Debug workspace launch fixed: vertical dock, title-screen input preserved, DEBUG hidden until playable room')
