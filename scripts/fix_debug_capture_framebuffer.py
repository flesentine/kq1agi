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

# A relative offset can snap visually when KQ1 rewrites the logical x/y of an
# object during a scripted sequence. MOVE is an authoring tool, so store an
# absolute rendered target position instead. Once dropped, the sprite remains
# pinned to that screen coordinate for this room/object/view.
start = text.index('    private void loadVisualOffsets() {')
end = text.index('    private void saveVisualOffsets() {', start)
text = text[:start] + '''    private void loadVisualOffsets() {\n        data.setSceneVisualOffsetCount(0);\n        String saved = prefs.getString("visualPinsV1", "");\n        if (saved == null || saved.length() == 0) return;\n        String[] records = saved.split(";");\n        int out = 0;\n        for (String record : records) {\n            if (out >= 32 || record == null || record.length() == 0) continue;\n            String[] p = record.split(",");\n            if (p.length != 5) continue;\n            try {\n                int targetX = Integer.parseInt(p[3]);\n                int targetY = Integer.parseInt(p[4]);\n                if (targetX < 0 || targetX >= WIDTH || targetY < 0 || targetY >= HEIGHT) continue;\n                // Legacy/debug accident offsets are intentionally ignored by visualPinsV1.\n                for (int f = 0; f < 5; f++) data.setSceneVisualOffsetField(out, f, Integer.parseInt(p[f]));\n                out++;\n            } catch (Exception ignored) {\n            }\n        }\n        data.setSceneVisualOffsetCount(out);\n    }\n\n''' + text[end:]

start = text.index('    private void saveVisualOffsets() {')
end = text.index('    private int findVisualOffsetRecord(', start)
text = text[:start] + '''    private void saveVisualOffsets() {\n        StringBuilder out = new StringBuilder();\n        int count = Math.max(0, Math.min(32, data.getSceneVisualOffsetCount()));\n        for (int i = 0; i < count; i++) {\n            if (i > 0) out.append(';');\n            for (int f = 0; f < 5; f++) {\n                if (f > 0) out.append(',');\n                out.append(data.getSceneVisualOffsetField(i, f));\n            }\n        }\n        prefs.putString("visualPinsV1", out.toString());\n        prefs.flush();\n    }\n\n''' + text[end:]

ensure_anchor = '    private int ensureVisualOffsetRecord(int targetRoom, int objectNumber, int viewNumber) {'
idx = text.index(ensure_anchor)
text = text[:idx] + '''    private int publishedMoveField(int objectNumber, int viewNumber, int field, int fallback) {\n        int count = Math.max(0, Math.min(16, data.getSceneMoveObjectCount()));\n        for (int i = 0; i < count; i++) {\n            if (data.getSceneMoveObjectField(i, 0) == objectNumber\n                    && data.getSceneMoveObjectField(i, 1) == viewNumber) {\n                return data.getSceneMoveObjectField(i, field);\n            }\n        }\n        return fallback;\n    }\n\n''' + text[idx:]

start = text.index('    private int ensureVisualOffsetRecord(')
end = text.index('    private int selectedMoveDx()', start)
text = text[:start] + '''    private int ensureVisualOffsetRecord(int targetRoom, int objectNumber, int viewNumber) {\n        int existing = findVisualOffsetRecord(targetRoom, objectNumber, viewNumber);\n        if (existing >= 0) return existing;\n        int count = Math.max(0, Math.min(32, data.getSceneVisualOffsetCount()));\n        if (count >= 32) {\n            notice("MOVE TABLE FULL");\n            return -1;\n        }\n        int currentX = publishedMoveField(objectNumber, viewNumber, 2, 0);\n        int currentY = publishedMoveField(objectNumber, viewNumber, 3, HEIGHT - 1);\n        data.setSceneVisualOffsetField(count, 0, targetRoom);\n        data.setSceneVisualOffsetField(count, 1, objectNumber);\n        data.setSceneVisualOffsetField(count, 2, viewNumber);\n        data.setSceneVisualOffsetField(count, 3, currentX);\n        data.setSceneVisualOffsetField(count, 4, currentY);\n        data.setSceneVisualOffsetCount(count + 1);\n        return count;\n    }\n\n''' + text[end:]

start = text.index('    private void moveSelectedBy(')
end = text.index('    private void resetSelectedMove()', start)
text = text[:start] + '''    private void moveSelectedBy(int dx, int dy) {\n        if (moveSelectedObject < 0 || moveSelectedView < 0) return;\n        int r = ensureVisualOffsetRecord(room, moveSelectedObject, moveSelectedView);\n        if (r < 0) return;\n        int width = Math.max(1, publishedMoveField(moveSelectedObject, moveSelectedView, 4, 1));\n        int height = Math.max(1, publishedMoveField(moveSelectedObject, moveSelectedView, 5, 1));\n        // Old relative mode used Math.max(-40, Math.min(40; absolute pinning replaces it.\n        int nx = Math.max(0, Math.min(WIDTH - width, data.getSceneVisualOffsetField(r, 3) + dx));\n        int ny = Math.max(height - 1, Math.min(HEIGHT - 1, data.getSceneVisualOffsetField(r, 4) + dy));\n        data.setSceneVisualOffsetField(r, 3, nx);\n        data.setSceneVisualOffsetField(r, 4, ny);\n        saveVisualOffsets();\n    }\n\n''' + text[end:]

start = text.index('    private void resetSelectedMove() {')
end = text.index('    private boolean select', start)
text = text[:start] + '''    private void resetSelectedMove() {\n        int r = findVisualOffsetRecord(room, moveSelectedObject, moveSelectedView);\n        if (r < 0) return;\n        int count = Math.max(0, Math.min(32, data.getSceneVisualOffsetCount()));\n        for (int i = r; i < count - 1; i++) {\n            for (int f = 0; f < 5; f++) {\n                data.setSceneVisualOffsetField(i, f, data.getSceneVisualOffsetField(i + 1, f));\n            }\n        }\n        if (count > 0) {\n            for (int f = 0; f < 5; f++) data.setSceneVisualOffsetField(count - 1, f, 0);\n            data.setSceneVisualOffsetCount(count - 1);\n        }\n        saveVisualOffsets();\n        notice("SPRITE UNPINNED");\n    }\n\n''' + text[end:]

editor.write_text(text)

# Convert runtime interpretation from relative offsets to absolute visual pins.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
start = text.index('    private static int visualOffset(')
end = text.index('    public static void publishMoveObjects(', start)
text = text[:start] + '''    private static int visualPin(GameState state, AnimatedObject obj, int field) {\n        if (state == null || obj == null) return Integer.MIN_VALUE;\n        VariableData data = state.getVariableData();\n        int room = state.getVar(Defines.CURROOM);\n        int count = Math.max(0, Math.min(VISUAL_OFFSET_MAX, data.getSceneVisualOffsetCount()));\n        for (int i = 0; i < count; i++) {\n            if (data.getSceneVisualOffsetField(i, 0) == room\n                    && data.getSceneVisualOffsetField(i, 1) == obj.objectNumber\n                    && data.getSceneVisualOffsetField(i, 2) == obj.currentView) {\n                return data.getSceneVisualOffsetField(i, field);\n            }\n        }\n        return Integer.MIN_VALUE;\n    }\n\n    public static int objectVisualOffsetX(GameState state, AnimatedObject obj) {\n        int targetX = visualPin(state, obj, 3);\n        return targetX == Integer.MIN_VALUE ? 0 : targetX - obj.x;\n    }\n\n    public static int objectVisualOffsetY(GameState state, AnimatedObject obj) {\n        int targetY = visualPin(state, obj, 4);\n        if (targetY == Integer.MIN_VALUE) return 0;\n        int naturalVisualY = obj.y + waterVisualSink(state, obj);\n        return targetY - naturalVisualY;\n    }\n\n    public static int objectVisualPadding(GameState state, AnimatedObject obj) {\n        if (state == null || obj == null) return 0;\n        int targetX = visualPin(state, obj, 3);\n        int targetY = visualPin(state, obj, 4);\n        if (targetX == Integer.MIN_VALUE || targetY == Integer.MIN_VALUE) return 0;\n        int naturalY = obj.y + waterVisualSink(state, obj);\n        int padding = Math.max(Math.abs(targetX - obj.x), Math.abs(targetY - naturalY));\n        return Math.min(160, padding + 2);\n    }\n\n''' + text[end:]
runtime.write_text(text)

print('Debug capture ready; MOVE SPRITE auto-selects ego and dropped sprites are absolute visual pins')