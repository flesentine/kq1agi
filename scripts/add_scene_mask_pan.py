#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scene_mask_pan.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

# Spacebar hand-tool panning while zoomed. Keep the zoom focus as floats so
# dragging feels smooth even at 4x/8x rather than jumping one AGI pixel at a time.
field = '''    private int zoomFocusX = WIDTH / 2;
    private int zoomFocusY = HEIGHT / 2;
    private boolean draggingBrushSlider;
'''
field_repl = '''    private float zoomFocusX = WIDTH / 2f;
    private float zoomFocusY = HEIGHT / 2f;
    private boolean draggingBrushSlider;
    private boolean spacePan;
    private boolean panning;
    private int panLastScreenX;
    private int panLastScreenY;
'''
if text.count(field) != 1:
    raise RuntimeError('SceneMaskEditor zoom/brush fields not found')
text = text.replace(field, field_repl)

# Clamp the movable focus to the editable 160x168 scene plane.
helper_anchor = '''    private void resetZoom() {
        zoom = 1;
        zoomFocusX = WIDTH / 2;
        zoomFocusY = HEIGHT / 2;
    }
'''
helper_repl = '''    private void clampPanFocus() {
        zoomFocusX = Math.max(0f, Math.min(WIDTH - 1f, zoomFocusX));
        zoomFocusY = Math.max(0f, Math.min(HEIGHT - 1f, zoomFocusY));
    }

    private void resetZoom() {
        zoom = 1;
        zoomFocusX = WIDTH / 2f;
        zoomFocusY = HEIGHT / 2f;
        spacePan = false;
        panning = false;
    }
'''
if text.count(helper_anchor) != 1:
    raise RuntimeError('SceneMaskEditor resetZoom block not found')
text = text.replace(helper_anchor, helper_repl)

# Space is consumed in paint mode and becomes a temporary hand tool.
key_anchor = '''        if (!paintMode) return false;

        int nudge = (Gdx.input.isKeyPressed(Input.Keys.SHIFT_LEFT)
'''
key_repl = '''        if (!paintMode) return false;

        if (keycode == Input.Keys.SPACE) {
            spacePan = true;
            if (zoom > 1) notice("PAN - DRAG THE SCENE");
            else notice("ZOOM IN, THEN SPACE + DRAG");
            return true;
        }

        int nudge = (Gdx.input.isKeyPressed(Input.Keys.SHIFT_LEFT)
'''
if text.count(key_anchor) != 1:
    raise RuntimeError('SceneMaskEditor paint-key nudge anchor not found')
text = text.replace(key_anchor, key_repl)

keyup_anchor = '''    @Override
    public boolean keyUp(int keycode) {
        return paintMode || keycode == Input.Keys.F2;
    }
'''
keyup_repl = '''    @Override
    public boolean keyUp(int keycode) {
        if (keycode == Input.Keys.SPACE) {
            spacePan = false;
            panning = false;
            return paintMode;
        }
        return paintMode || keycode == Input.Keys.F2;
    }
'''
if text.count(keyup_anchor) != 1:
    raise RuntimeError('SceneMaskEditor keyUp block not found')
text = text.replace(keyup_anchor, keyup_repl)

# When Space is held, mouse-down starts a pan instead of painting. The old
# in-canvas brush slider is disabled here because the fixed HTML control is now
# the authoritative brush UI and remains visible at every zoom level.
touch_anchor = '''        if (p == null) return true;
        if (isBrushSliderPoint(p[0], p[1])) {
            draggingBrushSlider = true;
            setBrushFromSlider(p[0]);
            return true;
        }
        rightErase = (button == Input.Buttons.RIGHT);
        paint(p[0], p[1], rightErase);
        return true;
'''
touch_repl = '''        if (spacePan && zoom > 1) {
            panning = true;
            panLastScreenX = screenX;
            panLastScreenY = screenY;
            return true;
        }
        if (p == null) return true;
        rightErase = (button == Input.Buttons.RIGHT);
        paint(p[0], p[1], rightErase);
        return true;
'''
if text.count(touch_anchor) != 1:
    raise RuntimeError('SceneMaskEditor brush-slider touchDown block not found')
text = text.replace(touch_anchor, touch_repl)

drag_anchor = '''    public boolean touchDragged(int screenX, int screenY, int pointer) {
        if (!paintMode) return false;
        int[] p = point(screenX, screenY);
        if (p == null) return true;
        if (draggingBrushSlider) {
            setBrushFromSlider(p[0]);
            return true;
        }
        paint(p[0], p[1], rightErase);
        return true;
    }
'''
drag_repl = '''    public boolean touchDragged(int screenX, int screenY, int pointer) {
        if (!paintMode) return false;
        if (panning && spacePan && zoom > 1) {
            int dx = screenX - panLastScreenX;
            int dy = screenY - panLastScreenY;
            float screenW = Math.max(1f, Gdx.graphics.getWidth());
            float screenH = Math.max(1f, Gdx.graphics.getHeight());
            // Hand-tool semantics: dragging right/down moves the artwork right/down,
            // so the camera focus moves in the opposite direction.
            zoomFocusX -= dx * (WIDTH / (screenW * zoom));
            zoomFocusY -= dy * (200f / (screenH * zoom));
            clampPanFocus();
            panLastScreenX = screenX;
            panLastScreenY = screenY;
            return true;
        }
        int[] p = point(screenX, screenY);
        if (p == null) return true;
        paint(p[0], p[1], rightErase);
        return true;
    }
'''
if text.count(drag_anchor) != 1:
    raise RuntimeError('SceneMaskEditor brush-slider touchDragged block not found')
text = text.replace(drag_anchor, drag_repl)

# Stop panning cleanly when the mouse is released.
up_anchor = '''        rightErase = false;
        draggingBrushSlider = false;
        saveRoom();
'''
up_repl = '''        rightErase = false;
        draggingBrushSlider = false;
        panning = false;
        saveRoom();
'''
if text.count(up_anchor) != 1:
    raise RuntimeError('SceneMaskEditor touchUp state block not found')
text = text.replace(up_anchor, up_repl)

# The fixed browser overlay replaces the in-world slider, which used to zoom and
# pan away with the scene camera.
slider_draw = '            drawBrushSlider(batch);\n'
if text.count(slider_draw) != 1:
    raise RuntimeError('SceneMaskEditor drawBrushSlider call not found')
text = text.replace(slider_draw, '')

hud = '''            font.draw(batch, "ARROWS move matte | Shift=4px | 1 front | 2 block | 3 behind | E erase | Z zoom",
                    6, 184);
'''
hud_repl = '''            font.draw(batch, "ARROWS move matte | SPACE+DRAG pan | Shift=4px | 1 front | 2 block | 3 behind",
                    6, 184);
'''
if text.count(hud) != 1:
    raise RuntimeError('SceneMaskEditor HUD controls line not found')
text = text.replace(hud, hud_repl)

editor.write_text(text)
print('Scene mask pan installed: Space+drag pans smoothly while zoomed; in-canvas brush UI disabled')
