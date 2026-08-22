#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scene_mask_nudge.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

# Track the cumulative nudge for the current room so the paint HUD tells the
# author exactly how far the complete depth matte has been moved.
field = '''    private int zoomFocusX = WIDTH / 2;
    private int zoomFocusY = HEIGHT / 2;
'''
field_repl = '''    private int zoomFocusX = WIDTH / 2;
    private int zoomFocusY = HEIGHT / 2;
    private int matteOffsetX = 0;
    private int matteOffsetY = 0;
'''
if text.count(field) != 1:
    raise RuntimeError('SceneMaskEditor zoom fields not found')
text = text.replace(field, field_repl)

# Reset the display counters when changing rooms. The actual shifted mask is
# already persisted by the normal room-save code.
room_anchor = '''        saveRoom();
        room = current;
'''
room_repl = '''        saveRoom();
        room = current;
        matteOffsetX = 0;
        matteOffsetY = 0;
'''
if text.count(room_anchor) != 1:
    raise RuntimeError('SceneMaskEditor room-change anchor not found')
text = text.replace(room_anchor, room_repl)

# Move all three planes together. This intentionally shifts the actual editable
# pixels, so FRONT, BEHIND, and BLOCK stay perfectly registered and the result
# can immediately be touched up with the existing paint tools.
helper_anchor = '''    @Override
    public boolean keyDown(int keycode) {
'''
helpers = '''    private void shiftAllMasks(int dx, int dy) {
        boolean[][][] moved = new boolean[3][HEIGHT][WIDTH];
        for (int layer = 0; layer < 3; layer++) {
            for (int y = 0; y < HEIGHT; y++) {
                for (int x = 0; x < WIDTH; x++) {
                    if (!masks[layer][y][x]) continue;
                    int nx = x + dx;
                    int ny = y + dy;
                    if (nx >= 0 && nx < WIDTH && ny >= 0 && ny < HEIGHT) {
                        moved[layer][ny][nx] = true;
                    }
                }
            }
        }

        for (int layer = 0; layer < 3; layer++) {
            for (int y = 0; y < HEIGHT; y++) {
                for (int x = 0; x < WIDTH; x++) {
                    masks[layer][y][x] = moved[layer][y][x];
                }
            }
        }

        matteOffsetX += dx;
        matteOffsetY += dy;
        syncAll();
        dirty = true;
        notice("MATTE X=" + matteOffsetX + " Y=" + matteOffsetY);
    }

    @Override
    public boolean keyDown(int keycode) {
'''
if text.count(helper_anchor) != 1:
    raise RuntimeError('SceneMaskEditor keyDown anchor not found')
text = text.replace(helper_anchor, helpers)

key_anchor = '''        if (!paintMode) return false;

        if (keycode == Input.Keys.NUM_1) { mode = OCCLUDER; eraser = false; }
'''
key_repl = '''        if (!paintMode) return false;

        int nudge = (Gdx.input.isKeyPressed(Input.Keys.SHIFT_LEFT)
                || Gdx.input.isKeyPressed(Input.Keys.SHIFT_RIGHT)) ? 4 : 1;
        if (keycode == Input.Keys.LEFT) { shiftAllMasks(-nudge, 0); return true; }
        else if (keycode == Input.Keys.RIGHT) { shiftAllMasks(nudge, 0); return true; }
        else if (keycode == Input.Keys.UP) { shiftAllMasks(0, -nudge); return true; }
        else if (keycode == Input.Keys.DOWN) { shiftAllMasks(0, nudge); return true; }

        if (keycode == Input.Keys.NUM_1) { mode = OCCLUDER; eraser = false; }
'''
if text.count(key_anchor) != 1:
    raise RuntimeError('SceneMaskEditor paint-key anchor not found')
text = text.replace(key_anchor, key_repl)

# Put the offset on the first HUD line and make the arrow controls prominent.
hud1 = '''            font.draw(batch, "MASK PAINT  room " + room + "  mode=" + modeName + "  brush=" + brush + "  zoom=" + zoom + "x",
                    6, 195);
'''
hud1_repl = '''            font.draw(batch, "MASK PAINT room " + room + " mode=" + modeName + " brush=" + brush + " zoom=" + zoom + "x  xy=" + matteOffsetX + "," + matteOffsetY,
                    6, 195);
'''
if text.count(hud1) != 1:
    raise RuntimeError('SceneMaskEditor HUD status line not found')
text = text.replace(hud1, hud1_repl)

hud2 = '''            font.draw(batch, "F2 test | 1 front | 2 block | 3 behind | E erase | Z zoom | Shift-Z out | 0 reset",
                    6, 184);
'''
hud2_repl = '''            font.draw(batch, "ARROWS move matte | Shift=4px | 1 front | 2 block | 3 behind | E erase | Z zoom",
                    6, 184);
'''
if text.count(hud2) != 1:
    raise RuntimeError('SceneMaskEditor HUD controls line not found')
text = text.replace(hud2, hud2_repl)

# The in-game button is clickable, so don't advertise the awkward Mac F-key.
button = '''            font.draw(batch, "F2 PAINT", 222, 188);
'''
button_repl = '''            font.draw(batch, "PAINT", 224, 188);
'''
if text.count(button) != 1:
    raise RuntimeError('SceneMaskEditor PAINT label not found')
text = text.replace(button, button_repl)

editor.write_text(text)
print('Scene mask nudge installed: arrows move complete matte, Shift moves 4 pixels')
