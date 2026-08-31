#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: run_danger_view_ui.py /path/to/index.html')

script = Path(__file__).with_name('add_danger_view_ui.py')
source = script.read_text()

# fix_debug_workspace_launch.py inserts a title-screen guard at the start of
# setPaintUiActive before DANGER runs. Adapt only the cleanup anchor to the final
# function body; all other DANGER UI logic stays in the main patch.
old_source = """old = '''  function setPaintUiActive(active) {
    paintUiActive = !!active;
'''
new = '''  function setPaintUiActive(active) {
    paintUiActive = !!active;
    if (!paintUiActive && debugDangerActive) {
      setDebugDangerEngineActive(false);
      debugDangerActive = false;
      if (debugViewDanger) debugViewDanger.classList.remove('debug-selected');
    }
'''
one(old, new, 'setPaintUiActive DANGER cleanup')
"""
new_source = """old = '''    paintUiActive = !!active;
    document.body.classList.toggle('debug-workspace', paintUiActive);
'''
new = '''    paintUiActive = !!active;
    if (!paintUiActive && debugDangerActive) {
      setDebugDangerEngineActive(false);
      debugDangerActive = false;
      if (debugViewDanger) debugViewDanger.classList.remove('debug-selected');
    }
    document.body.classList.toggle('debug-workspace', paintUiActive);
'''
one(old, new, 'setPaintUiActive DANGER cleanup')
"""
if source.count(old_source) != 1:
    raise RuntimeError('DANGER UI state-cleanup source anchor not found')
source = source.replace(old_source, new_source, 1)

old_argv = sys.argv[:]
try:
    sys.argv = [str(script), old_argv[1]]
    scope = {'__name__': '__main__', '__file__': str(script)}
    exec(compile(source, str(script), 'exec'), scope, scope)
finally:
    sys.argv = old_argv
