#!/usr/bin/env python3
from pathlib import Path
import sys
import runpy

if len(sys.argv) != 2:
    raise SystemExit('usage: run_debug_workspace_redesign.py /path/to/index.html')

script = Path(__file__).with_name('redesign_debug_workspace.py')
source = script.read_text()

# The legacy brush patches currently leave three readout assignments rather than
# the two earlier builds had. All of them should refresh the compact workspace
# status, so accept any positive count and patch every occurrence.
old = '''if text.count(brush_update) != 2:
    raise RuntimeError(f'brush readout anchors expected 2, found {text.count(brush_update)}')
text = text.replace(brush_update, brush_update + '    updateDebugWorkspaceStatus();\\n')
'''
new = '''if text.count(brush_update) < 1:
    raise RuntimeError('brush readout anchor not found')
text = text.replace(brush_update, brush_update + '    updateDebugWorkspaceStatus();\\n')
'''
if source.count(old) != 1:
    raise RuntimeError('debug redesign brush assertion anchor not found')
source = source.replace(old, new, 1)

# Preserve the original script's __file__ lookup behavior while supplying the
# requested index.html argument exactly as if it had been launched directly.
old_argv = sys.argv[:]
try:
    sys.argv = [str(script), old_argv[1]]
    scope = {'__name__': '__main__', '__file__': str(script)}
    exec(compile(source, str(script), 'exec'), scope, scope)
finally:
    sys.argv = old_argv

# Final guardrail pass: keep the editor vertical and unavailable on the title
# screen so the normal "press any key" input can always start the game.
fix = Path(__file__).with_name('fix_debug_workspace_launch.py')
runpy.run_path(str(fix), run_name='__main__')

# The dock reduces available browser width without changing libGDX's render
# dimensions. Scale the complete canvas into that remaining space rather than
# clipping the right side of the AGI screen.
fit = Path(__file__).with_name('fix_debug_canvas_fit.py')
runpy.run_path(str(fit), run_name='__main__')

# TEST must restore the exact inline canvas sizing that AGILE/libGDX owned before
# DEBUG opened. Removing those properties makes the canvas fall back to its large
# intrinsic render size and looks like a zoomed/cropped game.
restore = Path(__file__).with_name('fix_debug_canvas_restore.py')
runpy.run_path(str(restore), run_name='__main__')

# Add the room-wide safety reset only after the final workspace markup and JS are
# stable. It restores the built-in/Sierra baseline and promises one-step Undo.
reset = Path(__file__).with_name('add_reset_room_button.py')
runpy.run_path(str(reset), run_name='__main__')
