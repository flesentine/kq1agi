#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_debug_canvas_fit.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def replace_one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)

# DEBUG takes 296 px away from the browser width, but libGDX keeps rendering its
# landscape viewport at the pre-dock full-window size. CSS clipping the canvas
# therefore hides the right side of the AGI screen. Keep libGDX's render surface
# untouched and scale the *whole* canvas visually to fit the remaining editor
# viewport instead. That preserves the complete game picture and its controls.
helper_anchor = '''  function debugWorkspaceAllowed() {\n'''
helpers = r'''  let debugCanvasBaseSize = null;

  function captureDebugCanvasBaseSize() {
    const canvas = gameCanvas();
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      debugCanvasBaseSize = { width: rect.width, height: rect.height };
    }
  }

  function clearDebugCanvasFit() {
    const canvas = gameCanvas();
    if (!canvas) return;
    canvas.style.removeProperty('width');
    canvas.style.removeProperty('height');
    canvas.style.removeProperty('max-width');
    canvas.style.removeProperty('max-height');
  }

  function fitDebugCanvasToWorkspace() {
    const canvas = gameCanvas();
    if (!canvas) return;

    if (!paintUiActive) {
      clearDebugCanvasFit();
      debugCanvasBaseSize = null;
      return;
    }

    if (!debugCanvasBaseSize) captureDebugCanvasBaseSize();
    if (!debugCanvasBaseSize) return;

    const sidebarValue = getComputedStyle(document.documentElement)
      .getPropertyValue('--debug-sidebar-width').trim();
    const sidebarWidth = Number.parseFloat(sidebarValue) || 296;
    const availableWidth = Math.max(320, window.innerWidth - sidebarWidth);
    const availableHeight = Math.max(200, window.innerHeight);
    const scale = Math.min(
      1,
      availableWidth / debugCanvasBaseSize.width,
      availableHeight / debugCanvasBaseSize.height
    );

    const fittedWidth = Math.max(1, Math.floor(debugCanvasBaseSize.width * scale));
    const fittedHeight = Math.max(1, Math.floor(debugCanvasBaseSize.height * scale));

    // Inline !important wins over the generated workspace's width:auto rules.
    // We only change CSS display size, not canvas.width/canvas.height, so AGILE's
    // WebGL viewport and game-state coordinates stay exactly as they were.
    canvas.style.setProperty('width', fittedWidth + 'px', 'important');
    canvas.style.setProperty('height', fittedHeight + 'px', 'important');
    canvas.style.setProperty('max-width', 'none', 'important');
    canvas.style.setProperty('max-height', 'none', 'important');
  }

  function debugWorkspaceAllowed() {
'''
replace_one(helper_anchor, helpers, 'debug canvas fit helpers')

# Capture the normal full-window canvas before the dock changes layout. Then fit
# it on the next frame after the debug-workspace class has been applied. On exit,
# the same function clears the temporary CSS dimensions.
set_active_anchor = '''    paintUiActive = !!active;\n    document.body.classList.toggle('debug-workspace', paintUiActive);\n'''
set_active_repl = '''    if (active && !paintUiActive) captureDebugCanvasBaseSize();\n    paintUiActive = !!active;\n    document.body.classList.toggle('debug-workspace', paintUiActive);\n    requestAnimationFrame(fitDebugCanvasToWorkspace);\n'''
replace_one(set_active_anchor, set_active_repl, 'debug canvas fit activation')

# Keep the visual fit correct if the browser window or Chrome side panel changes
# size while DEBUG is open.
resize_anchor = '''  setInterval(refreshDebugButtonAvailability, 200);\n  setTimeout(refreshDebugButtonAvailability, 0);\n'''
resize_repl = '''  window.addEventListener('resize', () => {\n    if (paintUiActive) requestAnimationFrame(fitDebugCanvasToWorkspace);\n  });\n\n  setInterval(refreshDebugButtonAvailability, 200);\n  setTimeout(refreshDebugButtonAvailability, 0);\n'''
replace_one(resize_anchor, resize_repl, 'debug canvas fit resize hook')

old_tag = "const BUILD_TAG = '20260827-debug-workspace-v3-fix1';"
new_tag = "const BUILD_TAG = '20260827-debug-workspace-v3-fit1';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('debug canvas fit build tag not found')

path.write_text(text)
print('Debug canvas fit installed: full AGI render surface scales beside sidebar instead of clipping')
