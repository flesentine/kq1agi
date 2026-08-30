#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_debug_launcher_test_flow.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


# Keep the normal-game debug launcher in the same left-side zone where the dock
# appears. In DEBUG the three floating launch buttons are still hidden and the
# dock's own TEST / room tools remain authoritative.
style_anchor = '  </style>\n'
launcher_css = r'''    /* Normal-game debug launcher: left aligned with the editor dock. */
    #export-bg-button,
    #debug-snap-button,
    #paint-button {
      top: 14px !important;
      right: auto !important;
      z-index: 10001 !important;
      min-height: 36px;
      box-sizing: border-box;
    }
    #export-bg-button { left: 14px !important; width: 88px; }
    #debug-snap-button { left: 108px !important; width: 104px; }
    #paint-button { left: 218px !important; width: 68px; }

    @media (max-width: 520px) {
      #export-bg-button { left: 8px !important; width: 82px; }
      #debug-snap-button { left: 94px !important; width: 96px; }
      #paint-button { left: 194px !important; width: 64px; }
    }
  </style>
'''
if text.count(style_anchor) != 1:
    raise RuntimeError('final style close anchor not found')
text = text.replace(style_anchor, launcher_css, 1)

# Direct browser -> Java command. 101 = enter DEBUG paint mode, 100 = exit to
# TEST. Also mirror the worker-visible paint-mode slot immediately so Graham is
# never left frozen while the UI waits for the next render tick. Synthetic F2 is
# retained only as a fallback for an old/cached runtime without the new slot.
workspace_anchor = '''  function debugWorkspaceAllowed() {\n'''
workspace_helper = r'''  const DEBUG_WORKSPACE_BRIDGE_INDEX = 5829;
  const DEBUG_PAINT_MODE_INDEX = 522;

  function setDebugWorkspaceEngineActive(active) {
    try {
      const sab = window.__kq1agiVariableSAB;
      if (sab) {
        const shared = new Int32Array(sab);
        if (shared.length > DEBUG_WORKSPACE_BRIDGE_INDEX) {
          Atomics.store(shared, DEBUG_WORKSPACE_BRIDGE_INDEX, active ? 101 : 100);
          if (shared.length > DEBUG_PAINT_MODE_INDEX) {
            Atomics.store(shared, DEBUG_PAINT_MODE_INDEX, active ? 1 : 0);
          }
          if (typeof Atomics.notify === 'function') Atomics.notify(shared, DEBUG_WORKSPACE_BRIDGE_INDEX, 1);
          return true;
        }
      }
    } catch (error) {
      console.warn('DEBUG workspace direct bridge unavailable; falling back to F2', error);
    }
    sendF2();
    return false;
  }

  function restoreGameFocusAfterDebug() {
    const refocus = () => {
      focusGameCanvas();
      try {
        const canvas = document.querySelector('#embed-html canvas');
        if (canvas) {
          if (canvas.tabIndex < 0) canvas.tabIndex = 0;
          canvas.focus({ preventScroll: true });
        }
      } catch (error) {}
    };
    requestAnimationFrame(refocus);
    setTimeout(refocus, 60);
    setTimeout(refocus, 180);
  }

  function debugWorkspaceAllowed() {
'''
one(workspace_anchor, workspace_helper, 'workspace bridge helper anchor')

# TEST must turn the engine off directly before closing the dock. Multiple focus
# passes cover the canvas resize/restore that happens immediately after DEBUG.
test_old = '''  debugTestButton.addEventListener('click', event => {\n    event.preventDefault();\n    event.stopPropagation();\n    sendF2();\n    setPaintUiActive(false);\n    focusGameCanvas();\n  });\n'''
test_new = '''  debugTestButton.addEventListener('click', event => {\n    event.preventDefault();\n    event.stopPropagation();\n    setDebugWorkspaceEngineActive(false);\n    setPaintUiActive(false);\n    restoreGameFocusAfterDebug();\n  });\n'''
one(test_old, test_new, 'TEST direct-exit handler')

# Mouse DEBUG launcher: direct bridge instead of a synthetic F2.
click_old = '''  paintButton.addEventListener('click', event => {\n    event.preventDefault();\n    event.stopPropagation();\n    if (!paintUiActive && !debugWorkspaceAllowed()) {\n      focusGameCanvas();\n      return;\n    }\n    sendF2();\n    setPaintUiActive(!paintUiActive);\n    if (paintUiActive) applyBrushSize(brushSize);\n  });\n'''
click_new = '''  paintButton.addEventListener('click', event => {\n    event.preventDefault();\n    event.stopPropagation();\n    if (!paintUiActive && !debugWorkspaceAllowed()) {\n      focusGameCanvas();\n      return;\n    }\n    const nextActive = !paintUiActive;\n    setDebugWorkspaceEngineActive(nextActive);\n    setPaintUiActive(nextActive);\n    if (paintUiActive) applyBrushSize(brushSize);\n    else restoreGameFocusAfterDebug();\n  });\n'''
one(click_old, click_new, 'DEBUG button direct bridge')

# Tab gets the exact same reliable toggle path.
tab_old = '''  window.addEventListener('keydown', event => {\n    if (event.key !== 'Tab' || event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;\n    if (!paintUiActive && !debugWorkspaceAllowed()) return;\n    event.preventDefault();\n    event.stopPropagation();\n    sendF2();\n    setPaintUiActive(!paintUiActive);\n    if (paintUiActive) applyBrushSize(brushSize);\n  }, true);\n'''
tab_new = '''  window.addEventListener('keydown', event => {\n    if (event.key !== 'Tab' || event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;\n    if (!paintUiActive && !debugWorkspaceAllowed()) return;\n    event.preventDefault();\n    event.stopPropagation();\n    const nextActive = !paintUiActive;\n    setDebugWorkspaceEngineActive(nextActive);\n    setPaintUiActive(nextActive);\n    if (paintUiActive) applyBrushSize(brushSize);\n    else restoreGameFocusAfterDebug();\n  }, true);\n'''
one(tab_old, tab_new, 'Tab direct bridge')

# COPY DEBUG can enter the workspace automatically. Avoid the same synthetic-F2
# failure there too.
copy_old = '''    if (!paintUiActive) {\n      sendF2();\n      setPaintUiActive(true);\n      if (paintUiActive) applyBrushSize(brushSize);\n      setTimeout(openDebugCapture, 120);\n      return;\n    }\n'''
copy_new = '''    if (!paintUiActive) {\n      setDebugWorkspaceEngineActive(true);\n      setPaintUiActive(true);\n      if (paintUiActive) applyBrushSize(brushSize);\n      setTimeout(openDebugCapture, 120);\n      return;\n    }\n'''
if text.count(copy_old) == 1:
    text = text.replace(copy_old, copy_new, 1)

# If gameplay returns to the title/credits room while DEBUG is open, close both
# halves of the editor rather than leaving an invisible paint-mode trap.
poll_anchor = '''  setInterval(refreshDebugButtonAvailability, 200);\n'''
poll_new = '''  setInterval(() => {\n    refreshDebugButtonAvailability();\n    if (paintUiActive && !debugWorkspaceAllowed()) {\n      setDebugWorkspaceEngineActive(false);\n      setPaintUiActive(false);\n      restoreGameFocusAfterDebug();\n    }\n  }, 200);\n'''
one(poll_anchor, poll_new, 'workspace safety poll')

# Make the browser shell cache change obvious. This script runs after the final
# FALL/ERASE browser patches, so target their current build tag rather than the
# earlier workspace-fit tag.
old_tag = "const BUILD_TAG = '20260829-debug-eraser-bridge-v1';"
new_tag = "const BUILD_TAG = '20260830-debug-left-test-bridge-v1';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('debug workspace build tag not found')

path.write_text(text)
print('Debug launcher moved left; DEBUG/TEST now use direct bridge with repeated game-focus restore')
