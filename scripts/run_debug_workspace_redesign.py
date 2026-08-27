#!/usr/bin/env python3
from pathlib import Path
import sys

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
