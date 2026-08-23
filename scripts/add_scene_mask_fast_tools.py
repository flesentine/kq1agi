#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scene_mask_fast_tools.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

# Fast authoring helpers: Shift-click straight lines, Option/Alt temporary erase,
# one-pixel grow/shrink, and per-layer visibility toggles.
field = '''    private final boolean[][][] masks = new boolean[3][HEIGHT][WIDTH];
    private final Texture white;
'''
field_repl = '''    private final boolean[][][] masks = new boolean[3][HEIGHT][WIDTH];
    private final boolean[] layerVisible = new boolean[] { true, true, true };
    private final Texture white;
'''
if text.count(field) != 1:
    raise RuntimeError('SceneMaskEditor mask field anchor not found')
text = text.replace(field, field_repl)

pan_field = '''    private int panLastScreenX;
    private int panLastScreenY;
'''
pan_field_repl = '''    private int panLastScreenX;
    private int panLastScreenY;
    private int lineAnchorX = -1;
    private int lineAnchorY = -1;
'''
if text.count(pan_field) != 1:
    raise RuntimeError('SceneMaskEditor pan field anchor not found')
text = text.replace(pan_field, pan_field_repl)

# Reset straight-line state when rooms change so a Shift-click never connects
# to a point in the previous room.
room_anchor = '''        matteOffsetX = 0;
        matteOffsetY = 0;
'''
room_repl = '''        matteOffsetX = 0;
        matteOffsetY = 0;
        lineAnchorX = -1;
        lineAnchorY = -1;
'''
if text.count(room_anchor) != 1:
    raise RuntimeError('SceneMaskEditor room reset anchor not found')
text = text.replace(room_anchor, room_repl)

# Holding Option on macOS arrives as ALT_LEFT/ALT_RIGHT through libGDX. Treat it
# as a temporary eraser without changing the persistent E-key eraser state.
paint_anchor = '''        erase = erase || eraser;
        int layer = mode;
'''
paint_repl = '''        erase = erase || eraser || optionEraseHeld();
        int layer = mode;
'''
if text.count(paint_anchor) != 1:
    raise RuntimeError('SceneMaskEditor erase paint anchor not found')
text = text.replace(paint_anchor, paint_repl)

helper_anchor = '''    private void shiftAllMasks(int dx, int dy) {
'''
helpers = '''    private boolean optionEraseHeld() {
        return Gdx.input.isKeyPressed(Input.Keys.ALT_LEFT)
                || Gdx.input.isKeyPressed(Input.Keys.ALT_RIGHT);
    }

    private void paintLine(int x0, int y0, int x1, int y1, boolean erase) {
        int dx = Math.abs(x1 - x0);
        int sx = x0 < x1 ? 1 : -1;
        int dy = -Math.abs(y1 - y0);
        int sy = y0 < y1 ? 1 : -1;
        int err = dx + dy;
        while (true) {
            paint(x0, y0, erase);
            if (x0 == x1 && y0 == y1) break;
            int e2 = 2 * err;
            if (e2 >= dy) { err += dy; x0 += sx; }
            if (e2 <= dx) { err += dx; y0 += sy; }
        }
    }

    private void morphSelectedLayer(boolean grow) {
        int layer = selectedLayer();
        boolean[][] src = new boolean[HEIGHT][WIDTH];
        boolean[][] dst = new boolean[HEIGHT][WIDTH];
        for (int y = 0; y < HEIGHT; y++) {
            for (int x = 0; x < WIDTH; x++) src[y][x] = masks[layer][y][x];
        }

        if (grow) {
            for (int y = 0; y < HEIGHT; y++) {
                for (int x = 0; x < WIDTH; x++) {
                    if (!src[y][x]) continue;
                    for (int oy = -1; oy <= 1; oy++) {
                        for (int ox = -1; ox <= 1; ox++) {
                            int nx = x + ox;
                            int ny = y + oy;
                            if (nx >= 0 && nx < WIDTH && ny >= 0 && ny < HEIGHT) dst[ny][nx] = true;
                        }
                    }
                }
            }
        } else {
            for (int y = 0; y < HEIGHT; y++) {
                for (int x = 0; x < WIDTH; x++) {
                    if (!src[y][x]) continue;
                    boolean keep = true;
                    for (int oy = -1; oy <= 1 && keep; oy++) {
                        for (int ox = -1; ox <= 1; ox++) {
                            int nx = x + ox;
                            int ny = y + oy;
                            if (nx < 0 || nx >= WIDTH || ny < 0 || ny >= HEIGHT || !src[ny][nx]) {
                                keep = false;
                                break;
                            }
                        }
                    }
                    dst[y][x] = keep;
                }
            }
        }

        for (int y = 0; y < HEIGHT; y++) {
            for (int x = 0; x < WIDTH; x++) masks[layer][y][x] = dst[y][x];
        }
        syncAll();
        dirty = true;
        lineAnchorX = -1;
        lineAnchorY = -1;
        notice(grow ? "LAYER GROWN 1 PX" : "LAYER SHRUNK 1 PX");
    }

    private void toggleLayerVisible(int layer, String name) {
        layerVisible[layer] = !layerVisible[layer];
        notice(name + (layerVisible[layer] ? " VISIBLE" : " HIDDEN"));
    }

    private void shiftAllMasks(int dx, int dy) {
'''
if text.count(helper_anchor) != 1:
    raise RuntimeError('SceneMaskEditor shift helper anchor not found')
text = text.replace(helper_anchor, helpers)

# Add fast-tool shortcuts after Space hand-tool handling and before matte nudge.
key_anchor = '''        int nudge = (Gdx.input.isKeyPressed(Input.Keys.SHIFT_LEFT)
                || Gdx.input.isKeyPressed(Input.Keys.SHIFT_RIGHT)) ? 4 : 1;
'''
key_repl = '''        if (keycode == Input.Keys.EQUALS) { morphSelectedLayer(true); return true; }
        if (keycode == Input.Keys.MINUS) { morphSelectedLayer(false); return true; }
        if (keycode == Input.Keys.R) { toggleLayerVisible(OCCLUDER, "RED"); return true; }
        if (keycode == Input.Keys.B) { toggleLayerVisible(COLLISION, "BLUE"); return true; }
        if (keycode == Input.Keys.G) { toggleLayerVisible(BEHIND, "GREEN"); return true; }

        int nudge = (Gdx.input.isKeyPressed(Input.Keys.SHIFT_LEFT)
                || Gdx.input.isKeyPressed(Input.Keys.SHIFT_RIGHT)) ? 4 : 1;
'''
if text.count(key_anchor) != 1:
    raise RuntimeError('SceneMaskEditor nudge key anchor not found')
text = text.replace(key_anchor, key_repl)

# Switching layers also resets the line start, preventing accidental cross-layer lines.
mode_keys = '''        if (keycode == Input.Keys.NUM_1) { mode = OCCLUDER; eraser = false; }
        else if (keycode == Input.Keys.NUM_2) { mode = COLLISION; eraser = false; }
        else if (keycode == Input.Keys.NUM_3) { mode = BEHIND; eraser = false; }
'''
mode_keys_repl = '''        if (keycode == Input.Keys.NUM_1) { mode = OCCLUDER; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_2) { mode = COLLISION; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_3) { mode = BEHIND; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
'''
if text.count(mode_keys) != 1:
    raise RuntimeError('SceneMaskEditor layer selection keys not found')
text = text.replace(mode_keys, mode_keys_repl)

# Shift-click draws a straight line from the previous click. A regular click
# paints normally and establishes the next line start. Right-click or Option can
# erase the line just as they erase freehand painting.
touch_anchor = '''        if (p == null) return true;
        rightErase = (button == Input.Buttons.RIGHT);
        paint(p[0], p[1], rightErase);
        return true;
'''
touch_repl = '''        if (p == null) return true;
        rightErase = (button == Input.Buttons.RIGHT);
        boolean eraseNow = rightErase || optionEraseHeld();
        boolean shiftLine = Gdx.input.isKeyPressed(Input.Keys.SHIFT_LEFT)
                || Gdx.input.isKeyPressed(Input.Keys.SHIFT_RIGHT);
        if (shiftLine && lineAnchorX >= 0 && lineAnchorY >= 0) {
            paintLine(lineAnchorX, lineAnchorY, p[0], p[1], eraseNow);
        } else {
            paint(p[0], p[1], eraseNow);
        }
        lineAnchorX = p[0];
        lineAnchorY = p[1];
        return true;
'''
if text.count(touch_anchor) != 1:
    raise RuntimeError('SceneMaskEditor touchDown paint anchor not found')
text = text.replace(touch_anchor, touch_repl)

# Option can be pressed/released during a freehand drag, so query it on every event.
drag_anchor = '''        int[] p = point(screenX, screenY);
        if (p == null) return true;
        paint(p[0], p[1], rightErase);
        return true;
'''
drag_repl = '''        int[] p = point(screenX, screenY);
        if (p == null) return true;
        paint(p[0], p[1], rightErase || optionEraseHeld());
        return true;
'''
if text.count(drag_anchor) != 1:
    raise RuntimeError('SceneMaskEditor touchDragged paint anchor not found')
text = text.replace(drag_anchor, drag_repl)

# Visibility affects the authoring overlay only; the actual masks remain live and
# are unchanged, so hiding a color is safe while editing another layer.
render = '''            drawMaskRuns(batch, masks[OCCLUDER], new Color(1f, 0.12f, 0.08f, 0.45f));
            drawMaskRuns(batch, masks[COLLISION], new Color(0.08f, 0.35f, 1f, 0.50f));
            drawMaskRuns(batch, masks[BEHIND], new Color(0.10f, 1f, 0.25f, 0.35f));
'''
render_repl = '''            if (layerVisible[OCCLUDER]) drawMaskRuns(batch, masks[OCCLUDER], new Color(1f, 0.12f, 0.08f, 0.45f));
            if (layerVisible[COLLISION]) drawMaskRuns(batch, masks[COLLISION], new Color(0.08f, 0.35f, 1f, 0.50f));
            if (layerVisible[BEHIND]) drawMaskRuns(batch, masks[BEHIND], new Color(0.10f, 1f, 0.25f, 0.35f));
'''
if text.count(render) != 1:
    raise RuntimeError('SceneMaskEditor mask render block not found')
text = text.replace(render, render_repl)

hud = '''            font.draw(batch, "ARROWS move matte | SPACE+DRAG pan | Shift=4px | 1 front | 2 block | 3 behind",
                    6, 184);
'''
hud_repl = '''            font.draw(batch, "Shift-click line | Option erase | +/- grow/shrink | R/G/B hide | SPACE+DRAG pan",
                    6, 184);
'''
if text.count(hud) != 1:
    raise RuntimeError('SceneMaskEditor fast-tools HUD anchor not found')
text = text.replace(hud, hud_repl)

editor.write_text(text)
print('Fast mask tools installed: Shift-click line, Option erase, grow/shrink, layer visibility')
