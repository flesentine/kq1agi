#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_object_move_bounds.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# 1) Keep MOVE-SPRITE authoring offsets in a sane range and ignore old accidental
# giant offsets. This specifically self-heals previously saved values such as
# +53,+80 that can move a 160x168 AGI sprite completely off screen.
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

old = '''                for (int f = 0; f < 5; f++) data.setSceneVisualOffsetField(out, f, Integer.parseInt(p[f]));
                out++;
'''
new = '''                for (int f = 0; f < 5; f++) data.setSceneVisualOffsetField(out, f, Integer.parseInt(p[f]));
                int savedDx = data.getSceneVisualOffsetField(out, 3);
                int savedDy = data.getSceneVisualOffsetField(out, 4);
                if (Math.abs(savedDx) > 40 || Math.abs(savedDy) > 40) {
                    // Legacy/debug accident: do not reactivate an off-screen sprite offset.
                    data.setSceneVisualOffsetField(out, 3, 0);
                    data.setSceneVisualOffsetField(out, 4, 0);
                }
                out++;
'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor visual-offset load anchor not found')
text = text.replace(old, new, 1)

old = '''        int nx = Math.max(-80, Math.min(80, data.getSceneVisualOffsetField(r, 3) + dx));
        int ny = Math.max(-80, Math.min(80, data.getSceneVisualOffsetField(r, 4) + dy));
'''
new = '''        int nx = Math.max(-40, Math.min(40, data.getSceneVisualOffsetField(r, 3) + dx));
        int ny = Math.max(-40, Math.min(40, data.getSceneVisualOffsetField(r, 4) + dy));
'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor move offset clamp anchor not found')
text = text.replace(old, new, 1)

# Initial sprite selection should be forgiving. Direct box hits still win, but
# clicks slightly outside tiny AGI sprite boxes select the nearest sprite within
# 24 AGI pixels. Once selected, drag-anywhere still works.
old = '''    private boolean selectMoveObjectAt(int px, int py) {
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
new = '''    private boolean selectMoveObjectAt(int px, int py) {
        int count = Math.max(0, Math.min(16, data.getSceneMoveObjectCount()));
        int best = -1;
        int bestBaseline = -9999;
        int bestDistance = 999999;
        int nearest = -1;
        int nearestDistanceSq = 999999;
        final int grabPad = 6;
        final int nearestRadius = 24;
        for (int i = 0; i < count; i++) {
            int x = data.getSceneMoveObjectField(i, 2);
            int baselineY = data.getSceneMoveObjectField(i, 3);
            int width = Math.max(1, data.getSceneMoveObjectField(i, 4));
            int height = Math.max(1, data.getSceneMoveObjectField(i, 5));
            int top = baselineY - height + 1;
            int cx = x + (width / 2);
            int cy = top + (height / 2);
            int ddx = px - cx;
            int ddy = py - cy;
            int distanceSq = (ddx * ddx) + (ddy * ddy);
            if (distanceSq < nearestDistanceSq) {
                nearest = i;
                nearestDistanceSq = distanceSq;
            }

            boolean hit = px >= x - grabPad && px < x + width + grabPad
                    && py >= top - grabPad && py <= baselineY + grabPad;
            if (!hit) continue;
            int distance = Math.abs(ddx) + Math.abs(ddy);
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
            if (nearest >= 0 && nearestDistanceSq <= nearestRadius * nearestRadius) {
                best = nearest;
            } else {
                notice("CLICK NEAR A CYAN SPRITE BOX");
                return false;
            }
        }
        moveSelectedObject = data.getSceneMoveObjectField(best, 0);
        moveSelectedView = data.getSceneMoveObjectField(best, 1);
        return true;
    }
'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor forgiving selection anchor not found')
text = text.replace(old, new, 1)
editor.write_text(text)

# 2) Final render safety: even a valid saved offset may combine with a changing
# cel/water sink. Clamp the VISUAL draw location only; logical AGI x/y remain
# untouched, so game scripts/collision are unaffected.
animated = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
text = animated.read_text()
old = '''        int drawX = this.x + editorVisualOffsetX;
        int drawY = this.y + waterVisualSink + editorVisualOffsetY;
'''
new = '''        int drawX = Math.max(0, Math.min(160 - cellWidth, this.x + editorVisualOffsetX));
        int drawY = Math.max(cellHeight - 1, Math.min(167, this.y + waterVisualSink + editorVisualOffsetY));
'''
if text.count(old) != 1:
    raise RuntimeError('AnimatedObject visual draw position anchor not found')
animated.write_text(text.replace(old, new, 1))

# 3) Publish the same on-screen coordinates to MOVE mode/debug metadata so its
# yellow/cyan grab box and copied diagnostics match what is actually rendered.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
old = '''            int visualX = obj.x + objectVisualOffsetX(state, obj);
            int visualY = obj.y + objectVisualOffsetY(state, obj) + waterVisualSink(state, obj);
'''
new = '''            int visualX = Math.max(0, Math.min(160 - width, obj.x + objectVisualOffsetX(state, obj)));
            int visualY = Math.max(height - 1, Math.min(167,
                    obj.y + objectVisualOffsetY(state, obj) + waterVisualSink(state, obj)));
'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskRuntime published visual position anchor not found')
runtime.write_text(text.replace(old, new, 1))

# 4) A normal AGI print window blocks the interpreter worker inside
# waitAcceptAbort(). The browser UI can still edit SharedArrayBuffer offsets, but
# the worker won't run another animation cycle until the message closes. Poll the
# offset table inside windowPrint and visually redraw sprites immediately when a
# MOVE-SPRITE offset changes.
text_graphics = root / 'core/src/main/java/com/agifans/agile/TextGraphics.java'
text = text_graphics.read_text()

anchor = '''    public boolean windowPrint(String str) {
        return windowPrint(str, null);
    }
'''
helpers = '''    private int sceneMoveVisualSignature() {
        VariableData data = state.getVariableData();
        if (!data.getSceneMaskPaintMode()) return 0;
        int room = state.getVar(Defines.CURROOM);
        int count = Math.max(0, Math.min(32, data.getSceneVisualOffsetCount()));
        int hash = 17 + room;
        for (int i = 0; i < count; i++) {
            if (data.getSceneVisualOffsetField(i, 0) != room) continue;
            for (int field = 0; field < 5; field++) {
                hash = (hash * 31) + data.getSceneVisualOffsetField(i, field);
            }
        }
        return hash;
    }

    /** Redraws only the visible object layer for DEBUG/MOVE authoring. */
    private void redrawSceneMoveVisuals() {
        if (!state.graphicsMode || !state.pictureVisible) return;

        state.restoreBackgrounds();
        state.drawObjects();
        for (AnimatedObject aniObj : state.stoppedObjectList) {
            if (aniObj.drawn) aniObj.show(pixelData);
        }
        for (AnimatedObject aniObj : state.updateObjectList) {
            if (aniObj.drawn) aniObj.show(pixelData);
        }

        // Message windows are drawn directly into PixelData. Re-capture the
        // backing pixels after the move so closing the window restores the new
        // sprite placement, then redraw the message over the scene.
        if (openWindow != null) {
            openWindow.backPixels = null;
            drawWindow();
        }
    }

    public boolean windowPrint(String str) {
        return windowPrint(str, null);
    }
'''
if text.count(anchor) != 1:
    raise RuntimeError('TextGraphics windowPrint helper anchor not found')
text = text.replace(anchor, helpers, 1)

old = '''        // Get the response.
        if (state.getVar(Defines.PRINT_TIMEOUT) == 0) {
            retVal = (userInput.waitAcceptAbort() == UserInput.ACCEPT);
        }
        else {
            // The timeout value is given in half seconds and the TotalTicks in 1/60ths of a second.
            timeOut = state.getTotalTicks() + state.getVar(Defines.PRINT_TIMEOUT) * 30;

            while ((state.getTotalTicks() < timeOut) && (userInput.checkAcceptAbort() == -1))  {
                try {
                    Thread.sleep(1);
                } catch (InterruptedException e) {
                    // Interrupt indicates AGILE is stopping, so throw QuitAction.
                    QuitAction.exit();
                }
            }

            retVal = true;

            state.setVar(Defines.PRINT_TIMEOUT, 0);
        }
'''
new = '''        // Get the response. Also watch DEBUG/MOVE offsets in shared memory so
        // sprites visibly follow the mouse even while this AGI message blocks the tick.
        int moveVisualSignature = sceneMoveVisualSignature();
        if (state.getVar(Defines.PRINT_TIMEOUT) == 0) {
            // Match waitAcceptAbort(): ignore anything already queued when the
            // message opens, then wait for a fresh ENTER or ESC.
            while (userInput.getKey() != 0) ;
            int action;
            while ((action = userInput.checkAcceptAbort()) == -1) {
                int nextSignature = sceneMoveVisualSignature();
                if (nextSignature != moveVisualSignature) {
                    moveVisualSignature = nextSignature;
                    redrawSceneMoveVisuals();
                }
                try {
                    Thread.sleep(1);
                } catch (InterruptedException e) {
                    QuitAction.exit();
                }
            }
            retVal = (action == UserInput.ACCEPT);
        }
        else {
            // The timeout value is given in half seconds and the TotalTicks in 1/60ths of a second.
            timeOut = state.getTotalTicks() + state.getVar(Defines.PRINT_TIMEOUT) * 30;

            while ((state.getTotalTicks() < timeOut) && (userInput.checkAcceptAbort() == -1))  {
                int nextSignature = sceneMoveVisualSignature();
                if (nextSignature != moveVisualSignature) {
                    moveVisualSignature = nextSignature;
                    redrawSceneMoveVisuals();
                }
                try {
                    Thread.sleep(1);
                } catch (InterruptedException e) {
                    // Interrupt indicates AGILE is stopping, so throw QuitAction.
                    QuitAction.exit();
                }
            }

            retVal = true;

            state.setVar(Defines.PRINT_TIMEOUT, 0);
        }
'''
if text.count(old) != 1:
    raise RuntimeError('TextGraphics print-window wait anchor not found')
text_graphics.write_text(text.replace(old, new, 1))

print('Sprite move fixed: safe bounds, forgiving selection, and live visual redraw while AGI messages are open')
