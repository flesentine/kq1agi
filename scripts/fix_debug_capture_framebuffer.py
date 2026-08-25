#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_debug_capture_framebuffer.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# Preserve the WebGL back buffer so canvas.toDataURL()/drawImage captures the
# actual rendered game instead of a black frame. This script may run after
# improve_scene_object_move.py, so treat an already-applied patch as success.
launcher = root / 'html/src/main/java/com/agifans/agile/gwt/GwtLauncher.java'
text = launcher.read_text()
if 'cfg.preserveDrawingBuffer = true;' not in text:
    anchor = '''        cfg.padVertical = 0;\n        cfg.padHorizontal = 0;\n        return cfg;\n'''
    repl = '''        cfg.padVertical = 0;\n        cfg.padHorizontal = 0;\n        cfg.preserveDrawingBuffer = true;\n        return cfg;\n'''
    if text.count(anchor) != 1:
        raise RuntimeError('GwtLauncher config anchor not found')
    launcher.write_text(text.replace(anchor, repl))

# Expose the already-shared AGI variable buffer to the browser page. This gives
# the debug capture useful live state without creating a second data channel.
gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()
if 'exposeVariableSharedArrayBuffer' not in text:
    ctor_anchor = '''        this.variableArray = new SharedArray(variableArraySAB);\n    }\n'''
    ctor_repl = '''        this.variableArray = new SharedArray(variableArraySAB);\n        exposeVariableSharedArrayBuffer(variableArraySAB);\n    }\n\n    private static native void exposeVariableSharedArrayBuffer(JavaScriptObject sab) /*-{\n        $wnd.__kq1agiVariableSAB = sab;\n    }-*/;\n'''
    if text.count(ctor_anchor) != 1:
        raise RuntimeError('GwtVariableData constructor anchor not found')
    gwt.write_text(text.replace(ctor_anchor, ctor_repl))

print('Debug capture framebuffer ready: preserveDrawingBuffer=true and shared AGI state exposed to page')