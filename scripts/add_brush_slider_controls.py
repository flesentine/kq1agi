#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_brush_slider_controls.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

# Add a draggable brush-size control to paint mode. The slider lives at the
# bottom-left of the 160x168 picture plane, just above the parser area, so it is
# easy to reach without covering the Room 1 tree being edited on the right.
field = '''    private int zoom = 1;
    private int zoomFocusX = WIDTH / 2;
    private int zoomFocusY = HEIGHT / 2;
'''
field_repl = '''    private int zoom = 1;
    private int zoomFocusX = WIDTH / 2;
    private int zoomFocusY = HEIGHT / 2;
    private boolean draggingBrushSlider;
'''
if text.count(field) != 1:
    raise RuntimeError('SceneMaskEditor zoom field block not found')
text = text.replace(field, field_repl)

# Brush value 1 must really paint exactly one AGI mask pixel. Larger values keep
# the existing circular-brush behaviour so old keyboard brush sizes remain useful.
paint_anchor = '''        int radius = Math.max(1, brush);
        for (int y = cy - radius; y <= cy + radius; y++) {
'''
paint_repl = '''        if (brush <= 1) {
            if (cx >= 0 && cx < WIDTH && cy >= 0 && cy < HEIGHT) {
                masks[layer][cy][cx] = !erase;
                data.setSceneMaskBit(layer, cx, cy, !erase);
                dirty = true;
            }
            return;
        }
        int radius = brush;
        for (int y = cy - radius; y <= cy + radius; y++) {
'''
if text.count(paint_anchor) != 1:
    raise RuntimeError('SceneMaskEditor brush radius block not found')
text = text.replace(paint_anchor, paint_repl)

helper_anchor = '''    private int selectedLayer() {
        return mode;
    }
'''
helpers = '''    private boolean isBrushSliderPoint(int x, int y) {
        return x >= 4 && x <= 54 && y >= 151 && y <= 166;
    }

    private void setBrushFromSlider(int x) {
        final int minX = 11;
        final int maxX = 47;
        float t = (x - minX) / (float)(maxX - minX);
        if (t < 0f) t = 0f;
        if (t > 1f) t = 1f;
        brush = Math.max(1, Math.min(12, 1 + Math.round(t * 11f)));
    }

    private void drawBrushSlider(SpriteBatch batch) {
        float unit = 264f / WIDTH;
        float panelX = 4f * unit;
        float panelY = 24f + (167 - 166);
        float panelW = (54 - 4) * unit;
        float panelH = 15f;
        float trackX = 11f * unit;
        float trackW = (47 - 11) * unit;
        float trackY = panelY + 4f;
        float knobX = trackX + ((brush - 1) / 11f) * trackW;

        batch.setColor(0f, 0f, 0f, 0.78f);
        batch.draw(white, panelX, panelY, panelW, panelH);
        batch.setColor(1f, 1f, 1f, 0.35f);
        batch.draw(white, trackX, trackY, trackW, 2f);
        batch.setColor(1f, 1f, 0.2f, 1f);
        batch.draw(white, knobX - 1.5f, panelY + 2f, 3f, 6f);
        batch.setColor(Color.WHITE);
        font.draw(batch, "1", panelX + 2f, panelY + 12f);
        font.draw(batch, "12", panelX + panelW - 10f, panelY + 12f);
        font.draw(batch, "BRUSH " + brush + " PX", panelX + 20f, panelY + 12f);
    }

    private int selectedLayer() {
        return mode;
    }
'''
if text.count(helper_anchor) != 1:
    raise RuntimeError('SceneMaskEditor selectedLayer anchor not found')
text = text.replace(helper_anchor, helpers)

# Clicking/dragging the slider changes size without painting underneath it.
touch_anchor = '''        if (p == null) return true;
        rightErase = (button == Input.Buttons.RIGHT);
        paint(p[0], p[1], rightErase);
        return true;
'''
touch_repl = '''        if (p == null) return true;
        if (isBrushSliderPoint(p[0], p[1])) {
            draggingBrushSlider = true;
            setBrushFromSlider(p[0]);
            return true;
        }
        rightErase = (button == Input.Buttons.RIGHT);
        paint(p[0], p[1], rightErase);
        return true;
'''
if text.count(touch_anchor) != 1:
    raise RuntimeError('SceneMaskEditor touchDown paint block not found')
text = text.replace(touch_anchor, touch_repl)

drag_anchor = '''    public boolean touchDragged(int screenX, int screenY, int pointer) {
        if (!paintMode) return false;
        int[] p = point(screenX, screenY);
        if (p != null) paint(p[0], p[1], rightErase);
        return true;
    }
'''
drag_repl = '''    public boolean touchDragged(int screenX, int screenY, int pointer) {
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
if text.count(drag_anchor) != 1:
    raise RuntimeError('SceneMaskEditor touchDragged block not found')
text = text.replace(drag_anchor, drag_repl)

up_anchor = '''    public boolean touchUp(int screenX, int screenY, int pointer, int button) {
        if (!paintMode) return false;
        rightErase = false;
        saveRoom();
        return true;
    }
'''
up_repl = '''    public boolean touchUp(int screenX, int screenY, int pointer, int button) {
        if (!paintMode) return false;
        rightErase = false;
        draggingBrushSlider = false;
        saveRoom();
        return true;
    }
'''
if text.count(up_anchor) != 1:
    raise RuntimeError('SceneMaskEditor touchUp block not found')
text = text.replace(up_anchor, up_repl)

render_anchor = '''        } else {
            // Visible mouse entry point so the Sierra parser never has to be used
'''
render_repl = '''            drawBrushSlider(batch);
        } else {
            // Visible mouse entry point so the Sierra parser never has to be used
'''
if text.count(render_anchor) != 1:
    raise RuntimeError('SceneMaskEditor paint HUD end not found')
text = text.replace(render_anchor, render_repl)

editor.write_text(text)
print('Brush slider installed: 1-12 with true single-pixel minimum and numeric readout')
