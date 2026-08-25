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

# MOVE SPRITE should be impossible to confuse with moving the whole matte. Entering
# MOVE automatically selects ego (object 0) when it is visible, so the author can
# immediately drag anywhere or use arrows. Clicking another cyan box still switches
# selection. Arrow keys are always consumed by MOVE mode, even if no object exists.
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

select_anchor = '''    private boolean selectMoveObjectAt(int px, int py) {\n'''
if 'private boolean selectDefaultMoveObject()' not in text:
    default_helper = '''    private boolean selectDefaultMoveObject() {\n        int count = Math.max(0, Math.min(16, data.getSceneMoveObjectCount()));\n        if (count <= 0) {\n            moveSelectedObject = -1;\n            moveSelectedView = -1;\n            return false;\n        }\n\n        int selected = 0;\n        for (int i = 0; i < count; i++) {\n            if (data.getSceneMoveObjectField(i, 0) == 0) {\n                selected = i;\n                break;\n            }\n        }\n        moveSelectedObject = data.getSceneMoveObjectField(selected, 0);\n        moveSelectedView = data.getSceneMoveObjectField(selected, 1);\n        return true;\n    }\n\n'''
    if text.count(select_anchor) != 1:
        raise RuntimeError('SceneMaskEditor selectMoveObjectAt anchor not found')
    text = text.replace(select_anchor, default_helper + select_anchor, 1)

nudge_old = '''        if (moveMode && moveSelectedObject >= 0) {\n            if (keycode == Input.Keys.LEFT) { moveSelectedBy(-nudge, 0); return true; }\n            if (keycode == Input.Keys.RIGHT) { moveSelectedBy(nudge, 0); return true; }\n            if (keycode == Input.Keys.UP) { moveSelectedBy(0, -nudge); return true; }\n            if (keycode == Input.Keys.DOWN) { moveSelectedBy(0, nudge); return true; }\n            if (keycode == Input.Keys.BACKSPACE || keycode == Input.Keys.FORWARD_DEL) {\n                resetSelectedMove();\n                return true;\n            }\n        }\n'''
nudge_new = '''        if (moveMode) {\n            if (moveSelectedObject < 0 || moveSelectedView < 0) selectDefaultMoveObject();\n            if (keycode == Input.Keys.LEFT) {\n                if (moveSelectedObject >= 0) moveSelectedBy(-nudge, 0);\n                return true;\n            }\n            if (keycode == Input.Keys.RIGHT) {\n                if (moveSelectedObject >= 0) moveSelectedBy(nudge, 0);\n                return true;\n            }\n            if (keycode == Input.Keys.UP) {\n                if (moveSelectedObject >= 0) moveSelectedBy(0, -nudge);\n                return true;\n            }\n            if (keycode == Input.Keys.DOWN) {\n                if (moveSelectedObject >= 0) moveSelectedBy(0, nudge);\n                return true;\n            }\n            if (keycode == Input.Keys.BACKSPACE || keycode == Input.Keys.FORWARD_DEL) {\n                if (moveSelectedObject >= 0) resetSelectedMove();\n                return true;\n            }\n        }\n'''
if text.count(nudge_old) != 1:
    raise RuntimeError('SceneMaskEditor MOVE arrow block not found')
text = text.replace(nudge_old, nudge_new, 1)

mode_old = '''        else if (keycode == Input.Keys.NUM_5) {\n            moveMode = true;\n            eraser = false;\n            lineAnchorX = -1;\n            lineAnchorY = -1;\n            notice("MOVE: CLICK A BOX, THEN DRAG ANYWHERE");\n            return true;\n        }\n'''
mode_new = '''        else if (keycode == Input.Keys.NUM_5) {\n            moveMode = true;\n            eraser = false;\n            lineAnchorX = -1;\n            lineAnchorY = -1;\n            selectDefaultMoveObject();\n            notice = "";\n            noticeUntil = 0;\n            return true;\n        }\n'''
if text.count(mode_old) != 1:
    raise RuntimeError('SceneMaskEditor MOVE mode activation block not found')
text = text.replace(mode_old, mode_new, 1)

editor.write_text(text)

print('Debug capture ready; MOVE SPRITE now auto-selects ego and arrows can no longer move the matte')