#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: improve_scene_object_move.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

# Make sprite movement forgiving and obvious: once an object is selected, the
# user can drag from anywhere in the picture. Initial selection also gets a
# generous hit box so tiny AGI sprites are easy to grab.
select_old = '''    private boolean selectMoveObjectAt(int px, int py) {
        int count = Math.max(0, Math.min(16, data.getSceneMoveObjectCount()));
        int best = -1;
        int bestBaseline = -9999;
        for (int i = 0; i < count; i++) {
            int x = data.getSceneMoveObjectField(i, 2);
            int baselineY = data.getSceneMoveObjectField(i, 3);
            int width = Math.max(1, data.getSceneMoveObjectField(i, 4));
            int height = Math.max(1, data.getSceneMoveObjectField(i, 5));
            int top = baselineY - height + 1;
            if (px >= x && px < x + width && py >= top && py <= baselineY && baselineY >= bestBaseline) {
                best = i;
                bestBaseline = baselineY;
            }
        }
        if (best < 0) {
            moveSelectedObject = -1;
            moveSelectedView = -1;
            notice("NO SPRITE HERE");
            return false;
        }
        moveSelectedObject = data.getSceneMoveObjectField(best, 0);
        moveSelectedView = data.getSceneMoveObjectField(best, 1);
        notice("MOVE OBJ " + moveSelectedObject + " VIEW " + moveSelectedView);
        return true;
    }
'''
select_new = '''    private boolean selectMoveObjectAt(int px, int py) {
        int count = Math.max(0, Math.min(16, data.getSceneMoveObjectCount()));
        int best = -1;
        int bestBaseline = -9999;
        int bestDistance = 999999;
        final int grabPad = 6;
        for (int i = 0; i < count; i++) {
            int x = data.getSceneMoveObjectField(i, 2);
            int baselineY = data.getSceneMoveObjectField(i, 3);
            int width = Math.max(1, data.getSceneMoveObjectField(i, 4));
            int height = Math.max(1, data.getSceneMoveObjectField(i, 5));
            int top = baselineY - height + 1;
            boolean hit = px >= x - grabPad && px < x + width + grabPad
                    && py >= top - grabPad && py <= baselineY + grabPad;
            if (!hit) continue;
            int cx = x + (width / 2);
            int cy = top + (height / 2);
            int distance = Math.abs(px - cx) + Math.abs(py - cy);
            if (best < 0 || baselineY > bestBaseline
                    || (baselineY == bestBaseline && distance < bestDistance)) {
                best = i;
                bestBaseline = baselineY;
                bestDistance = distance;
            }
        }
        if (best < 0) {
            // After the first selection, dragging can begin anywhere in the game
            // image. This removes the need to keep grabbing a tiny sprite box.
            if (moveSelectedObject >= 0 && moveSelectedView >= 0) return true;
            notice("CLICK A SPRITE FIRST");
            return false;
        }
        moveSelectedObject = data.getSceneMoveObjectField(best, 0);
        moveSelectedView = data.getSceneMoveObjectField(best, 1);
        return true;
    }
'''
if text.count(select_old) != 1:
    raise RuntimeError('SceneMaskEditor original move selection method not found')
text = text.replace(select_old, select_new)

# Do not throw a notice popup on every mouse movement; the persistent HUD already
# shows object/view and exact offsets and is much easier to read while dragging.
move_old = '''    private void moveSelectedBy(int dx, int dy) {
        if (moveSelectedObject < 0 || moveSelectedView < 0) return;
        int r = ensureVisualOffsetRecord(room, moveSelectedObject, moveSelectedView);
        if (r < 0) return;
        int nx = Math.max(-80, Math.min(80, data.getSceneVisualOffsetField(r, 3) + dx));
        int ny = Math.max(-80, Math.min(80, data.getSceneVisualOffsetField(r, 4) + dy));
        data.setSceneVisualOffsetField(r, 3, nx);
        data.setSceneVisualOffsetField(r, 4, ny);
        saveVisualOffsets();
        notice("OBJ " + moveSelectedObject + " VIEW " + moveSelectedView + " X=" + nx + " Y=" + ny);
    }
'''
move_new = '''    private void moveSelectedBy(int dx, int dy) {
        if (moveSelectedObject < 0 || moveSelectedView < 0) return;
        int r = ensureVisualOffsetRecord(room, moveSelectedObject, moveSelectedView);
        if (r < 0) return;
        int nx = Math.max(-80, Math.min(80, data.getSceneVisualOffsetField(r, 3) + dx));
        int ny = Math.max(-80, Math.min(80, data.getSceneVisualOffsetField(r, 4) + dy));
        data.setSceneVisualOffsetField(r, 3, nx);
        data.setSceneVisualOffsetField(r, 4, ny);
        saveVisualOffsets();
    }
'''
if text.count(move_old) != 1:
    raise RuntimeError('SceneMaskEditor original moveSelectedBy method not found')
text = text.replace(move_old, move_new)

# Draw a grab box around every visible sprite in MOVE mode, with the currently
# selected sprite in bright yellow and the others in cyan.
draw_old = '''    private void drawMoveSelection(SpriteBatch batch) {
        if (!moveMode || moveSelectedObject < 0) return;
        int count = Math.max(0, Math.min(16, data.getSceneMoveObjectCount()));
        for (int i = 0; i < count; i++) {
            if (data.getSceneMoveObjectField(i, 0) != moveSelectedObject
                    || data.getSceneMoveObjectField(i, 1) != moveSelectedView) continue;
            int x = data.getSceneMoveObjectField(i, 2);
            int baselineY = data.getSceneMoveObjectField(i, 3);
            int width = Math.max(1, data.getSceneMoveObjectField(i, 4));
            int height = Math.max(1, data.getSceneMoveObjectField(i, 5));
            float sx = x * (264f / WIDTH);
            float sw = width * (264f / WIDTH);
            float bottom = 24f + (167 - baselineY);
            float sh = height;
            batch.setColor(1f, 0.95f, 0.1f, 0.95f);
            batch.draw(white, sx, bottom, sw, 1f);
            batch.draw(white, sx, bottom + sh - 1f, sw, 1f);
            batch.draw(white, sx, bottom, 1f, sh);
            batch.draw(white, sx + sw - 1f, bottom, 1f, sh);
            batch.setColor(Color.WHITE);
            return;
        }
    }
'''
draw_new = '''    private void drawMoveSelection(SpriteBatch batch) {
        if (!moveMode) return;
        int count = Math.max(0, Math.min(16, data.getSceneMoveObjectCount()));
        for (int i = 0; i < count; i++) {
            int objectNumber = data.getSceneMoveObjectField(i, 0);
            int viewNumber = data.getSceneMoveObjectField(i, 1);
            int x = data.getSceneMoveObjectField(i, 2);
            int baselineY = data.getSceneMoveObjectField(i, 3);
            int width = Math.max(1, data.getSceneMoveObjectField(i, 4));
            int height = Math.max(1, data.getSceneMoveObjectField(i, 5));
            float sx = x * (264f / WIDTH);
            float sw = Math.max(2f, width * (264f / WIDTH));
            float bottom = 24f + (167 - baselineY);
            float sh = Math.max(2f, height);
            boolean selected = objectNumber == moveSelectedObject && viewNumber == moveSelectedView;
            batch.setColor(selected ? new Color(1f, 0.95f, 0.1f, 0.98f)
                    : new Color(0.15f, 0.95f, 1f, 0.65f));
            float thick = selected ? 2f : 1f;
            batch.draw(white, sx, bottom, sw, thick);
            batch.draw(white, sx, bottom + sh - thick, sw, thick);
            batch.draw(white, sx, bottom, thick, sh);
            batch.draw(white, sx + sw - thick, bottom, thick, sh);
            if (selected) {
                float cx = sx + (sw / 2f);
                float cy = bottom + (sh / 2f);
                batch.draw(white, cx - 3f, cy, 6f, 1f);
                batch.draw(white, cx, cy - 3f, 1f, 6f);
            }
        }
        batch.setColor(Color.WHITE);
    }
'''
if text.count(draw_old) != 1:
    raise RuntimeError('SceneMaskEditor original drawMoveSelection method not found')
text = text.replace(draw_old, draw_new)

text = text.replace('notice("MOVE MODE - CLICK A SPRITE");',
                    'notice("MOVE: CLICK A BOX, THEN DRAG ANYWHERE");')
text = text.replace('"MOVE: click+drag sprite | arrows nudge | Shift=4px | Backspace reset | 1-4 paint"',
                    '"MOVE SPRITE: click a box once, then drag anywhere | arrows nudge | Backspace reset"')

editor.write_text(text)

# Debug screenshots copy the WebGL canvas. LibGDX normally discards the WebGL
# back buffer after each frame, which makes drawImage()/toDataURL() produce a
# black rectangle. Preserve it so COPY DEBUG gets the actual visible frame.
launcher = root / 'html/src/main/java/com/agifans/agile/gwt/GwtLauncher.java'
text = launcher.read_text()
anchor = '''        cfg.padVertical = 0;
        cfg.padHorizontal = 0;
        return cfg;
'''
repl = '''        cfg.padVertical = 0;
        cfg.padHorizontal = 0;
        cfg.preserveDrawingBuffer = true;
        return cfg;
'''
if text.count(anchor) != 1:
    raise RuntimeError('GwtLauncher config anchor not found')
launcher.write_text(text.replace(anchor, repl))

# Expose the SharedArrayBuffer to the page so the pasted image can include live
# AGI state such as room, ONWATER and Graham's current published view/bounds.
gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()
ctor_anchor = '''        this.variableArray = new SharedArray(variableArraySAB);
    }
'''
ctor_repl = '''        this.variableArray = new SharedArray(variableArraySAB);
        exposeVariableSharedArrayBuffer(variableArraySAB);
    }

    private static native void exposeVariableSharedArrayBuffer(JavaScriptObject sab) /*-{
        $wnd.__kq1agiVariableSAB = sab;
    }-*/;
'''
if text.count(ctor_anchor) != 1:
    raise RuntimeError('GwtVariableData constructor anchor not found')
gwt.write_text(text.replace(ctor_anchor, ctor_repl))

print('Sprite move UX improved; debug framebuffer preserved and live AGI state exposed to browser')