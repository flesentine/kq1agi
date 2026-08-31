#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: run_danger_composite_runtime.py /path/to/agile-gdx')

script = Path(__file__).with_name('add_danger_composite_runtime.py')
source = script.read_text()

# improve_fall_accessibility_runtime.py leaves FALL one indentation level deeper
# than the older raw overlay block. Keep the DANGER patch itself readable, but
# adapt its final render anchor to the exact post-accessibility Java source before
# executing it.
old_source = """old = '''            if (layerVisible[FALL]) {
                rebuildScriptFallDisplay();
                drawAccessibleEditableFall(batch);
                // Script markers render last so editable FALL can never bury them.
                drawAccessibleScriptFall(batch);
            }
'''
new = '''            if (!dangerView && layerVisible[FALL]) {
                rebuildScriptFallDisplay();
                drawAccessibleEditableFall(batch);
                // Script markers render last so editable FALL can never bury them.
                drawAccessibleScriptFall(batch);
            }
            if (dangerView) {
                // WATER is one source. Scripted marks expose bridge/death positions
                // that do not coincide with WATER pixels.
                drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.50f));
                rebuildScriptFallDisplay();
                drawAccessibleEditableFall(batch);
                drawAccessibleScriptFall(batch);
            }
'''
"""
new_source = """old = '''                if (layerVisible[FALL]) {
                    rebuildScriptFallDisplay();
                    drawAccessibleEditableFall(batch);
                    // Script markers render last so editable FALL can never bury them.
                    drawAccessibleScriptFall(batch);
                }
'''
new = '''                if (!dangerView && layerVisible[FALL]) {
                    rebuildScriptFallDisplay();
                    drawAccessibleEditableFall(batch);
                    // Script markers render last so editable FALL can never bury them.
                    drawAccessibleScriptFall(batch);
                }
                if (dangerView) {
                    // WATER is one source. Scripted marks expose bridge/death positions
                    // that do not coincide with WATER pixels.
                    drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.50f));
                    rebuildScriptFallDisplay();
                    drawAccessibleEditableFall(batch);
                    drawAccessibleScriptFall(batch);
                }
'''
"""
if source.count(old_source) != 1:
    raise RuntimeError('DANGER runtime FALL source anchor not found')
source = source.replace(old_source, new_source, 1)

old_argv = sys.argv[:]
try:
    sys.argv = [str(script), old_argv[1]]
    scope = {'__name__': '__main__', '__file__': str(script)}
    exec(compile(source, str(script), 'exec'), scope, scope)
finally:
    sys.argv = old_argv

# Detector v3 runs after the composite patch so it can replace v2's flattened
# per-condition painting with nested-IF-aware geometry and invalidate old caches.
geometry = Path(__file__).with_name('fix_danger_condition_geometry.py')
__import__('runpy').run_path(str(geometry), run_name='__main__')
