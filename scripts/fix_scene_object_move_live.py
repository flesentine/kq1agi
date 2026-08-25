#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_object_move_live.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# ---------------------------------------------------------------------------
# 1) Make initial sprite selection forgiving. Direct box hits still win, but if
# the click lands slightly outside a tiny AGI sprite box, select the nearest
# published sprite within 24 AGI pixels. Once selected, drag-anywhere remains.
# ---------------------------------------------------------------------------
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

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
editor.write_text(text.replace(old, new, 1))

# ---------------------------------------------------------------------------
# 2) AGI print windows block the interpreter inside waitAcceptAbort(). The UI
# thread can still edit SharedArrayBuffer offsets, but without this hook the
# worker does not redraw the sprite until the message is dismissed. Poll the
# visual offset table while a print window is waiting and redraw only the visual
# object layer whenever an authoring offset changes.
# ---------------------------------------------------------------------------
text_graphics = root / 'core/src/main/java/com/agifans/agile/TextGraphics.java'
text = text_graphics.read_text()

helper_anchor = '''    public boolean windowPrint(String str) {
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

    /**
     * Refresh only the rendered object layer for DEBUG/MOVE authoring. Logical AGI
     * x/y values are untouched. This is safe to call while windowPrint is waiting,
     * which is important because that wait keeps the web-worker inside one tick.
     */
    private void redrawSceneMoveVisuals() {
        if (!state.graphicsMode || !state.pictureVisible) return;

        // Restore the last object save areas, redraw at the newly authored visual
        // offsets, then blit the changed object rectangles into shared PixelData.
        state.restoreBackgrounds();
        state.drawObjects();
        for (AnimatedObject aniObj : state.stoppedObjectList) {
            if (aniObj.drawn) aniObj.show(pixelData);
        }
        for (AnimatedObject aniObj : state.updateObjectList) {
            if (aniObj.drawn) aniObj.show(pixelData);
        }

        // The AGI message window lives directly in PixelData, so redraw it last.
        // Re-capture its backing pixels first so closing the message restores the
        // newly moved scene rather than the old sprite placement.
        if (openWindow != null) {
            openWindow.backPixels = null;
            drawWindow();
        }
    }

    public boolean windowPrint(String str) {
        return windowPrint(str, null);
    }
'''

if text.count(helper_anchor) != 1:
    raise RuntimeError('TextGraphics windowPrint helper anchor not found')
text = text.replace(helper_anchor, helpers, 1)

wait_old = '''        // Get the response.
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

wait_new = '''        // Get the response. Unlike the stock waitAcceptAbort() call, this loop
        // also watches DEBUG/MOVE visual offsets in shared memory so a sprite can
        // visibly follow the mouse even while this AGI message blocks the tick.
        int moveVisualSignature = sceneMoveVisualSignature();
        if (state.getVar(Defines.PRINT_TIMEOUT) == 0) {
            // Match waitAcceptAbort(): ignore anything that was already queued when
            // the message opened, then wait for a fresh ENTER or ESC.
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

if text.count(wait_old) != 1:
    raise RuntimeError('TextGraphics print-window wait anchor not found')
text_graphics.write_text(text.replace(wait_old, wait_new, 1))

print('MOVE SPRITE live fix installed: nearest-box selection and visual redraws continue while AGI messages are open')
