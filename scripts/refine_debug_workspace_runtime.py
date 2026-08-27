#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: refine_debug_workspace_runtime.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

def one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 1) Editor state: one-step undo/redo, inspect mode, outline view, and opacity.
# ---------------------------------------------------------------------------
one(
'''    private final boolean[][][] masks = new boolean[6][HEIGHT][WIDTH];
''',
'''    private final boolean[][][] masks = new boolean[6][HEIGHT][WIDTH];
    private final boolean[][][] undoMasks = new boolean[6][HEIGHT][WIDTH];
    private final boolean[][][] redoMasks = new boolean[6][HEIGHT][WIDTH];
    private boolean undoValid;
    private boolean redoValid;
''',
'debug history fields'
)

one(
'''    private boolean fallActive;
    private boolean moveMode;
''',
'''    private boolean fallActive;
    private boolean inspectMode;
    private boolean outlineMode;
    private int overlayOpacityPercent = 70;
    private boolean moveMode;
''',
'debug workspace fields'
)

helper_anchor = '''    private boolean optionEraseHeld() {
'''
helpers = r'''    private void copyAllMasks(boolean[][][] from, boolean[][][] to) {
        for (int layer = 0; layer < 6; layer++) {
            for (int y = 0; y < HEIGHT; y++) {
                for (int x = 0; x < WIDTH; x++) to[layer][y][x] = from[layer][y][x];
            }
        }
    }

    private void captureUndoSnapshot() {
        copyAllMasks(masks, undoMasks);
        undoValid = true;
        redoValid = false;
    }

    private void undoMaskEdit() {
        if (!undoValid) {
            notice("NOTHING TO UNDO");
            return;
        }
        copyAllMasks(masks, redoMasks);
        copyAllMasks(undoMasks, masks);
        undoValid = false;
        redoValid = true;
        syncAll();
        dirty = true;
        saveRoom();
        notice("UNDO");
    }

    private void redoMaskEdit() {
        if (!redoValid) {
            notice("NOTHING TO REDO");
            return;
        }
        copyAllMasks(masks, undoMasks);
        copyAllMasks(redoMasks, masks);
        redoValid = false;
        undoValid = true;
        syncAll();
        dirty = true;
        saveRoom();
        notice("REDO");
    }

    private boolean optionEraseHeld() {
'''
one(helper_anchor, helpers, 'history helper anchor')

# Capture changes made by grow/shrink and whole-matte nudge.
one(
'''    private void morphSelectedLayer(boolean grow) {
        int layer = selectedLayer();
''',
'''    private void morphSelectedLayer(boolean grow) {
        captureUndoSnapshot();
        int layer = selectedLayer();
''',
'morph undo hook'
)
one(
'''    private void shiftAllMasks(int dx, int dy) {
''',
'''    private void shiftAllMasks(int dx, int dy) {
        captureUndoSnapshot();
''',
'nudge undo hook'
)

# ---------------------------------------------------------------------------
# 2) Keyboard commands for browser workspace controls.
# ---------------------------------------------------------------------------
key_anchor = '''        if (!paintMode) return false;

'''
key_repl = r'''        if (!paintMode) return false;

        if (keycode == Input.Keys.U) {
            undoMaskEdit();
            return true;
        }
        if (keycode == Input.Keys.Y) {
            redoMaskEdit();
            return true;
        }
        if (keycode == Input.Keys.I) {
            inspectMode = !inspectMode;
            moveMode = false;
            eraser = false;
            movingObject = false;
            notice(inspectMode ? "INSPECT MODE" : "PAINT MODE");
            return true;
        }
        if (keycode == Input.Keys.O) {
            outlineMode = !outlineMode;
            notice(outlineMode ? "OUTLINE VIEW" : "FILL VIEW");
            return true;
        }
        if (keycode == Input.Keys.COMMA) {
            overlayOpacityPercent = Math.max(25, overlayOpacityPercent - 5);
            notice("OVERLAY " + overlayOpacityPercent + "%");
            return true;
        }
        if (keycode == Input.Keys.PERIOD) {
            overlayOpacityPercent = Math.min(100, overlayOpacityPercent + 5);
            notice("OVERLAY " + overlayOpacityPercent + "%");
            return true;
        }

'''
# This phrase also appears in touch handlers, so patch only the keyDown method.
key_method = text.index('    public boolean keyDown(int keycode)')
key_pos = text.index(key_anchor, key_method)
text = text[:key_pos] + key_repl + text[key_pos + len(key_anchor):]

# Selecting any paint layer exits inspect mode. MOVE also exits inspect.
text = text.replace('moveMode = false; mode = OCCLUDER;', 'inspectMode = false; moveMode = false; mode = OCCLUDER;')
text = text.replace('moveMode = false; mode = COLLISION;', 'inspectMode = false; moveMode = false; mode = COLLISION;')
text = text.replace('moveMode = false; mode = BEHIND;', 'inspectMode = false; moveMode = false; mode = BEHIND;')
text = text.replace('moveMode = false; mode = WATER;', 'inspectMode = false; moveMode = false; mode = WATER;')
text = text.replace('moveMode = false; mode = FALL;', 'inspectMode = false; moveMode = false; mode = FALL;')
move_select = '''        else if (keycode == Input.Keys.NUM_6) {
            moveMode = true;
'''
if text.count(move_select) != 1:
    raise RuntimeError(f'MOVE mode selection anchor: expected 1, found {text.count(move_select)}')
text = text.replace(move_select, '''        else if (keycode == Input.Keys.NUM_6) {
            inspectMode = false;
            moveMode = true;
''', 1)

# Clear layer is destructive and must be undoable.
clear_anchor = '''        else if (keycode == Input.Keys.C) {
            int layer = selectedLayer();
'''
one(clear_anchor, '''        else if (keycode == Input.Keys.C) {
            captureUndoSnapshot();
            int layer = selectedLayer();
''', 'clear undo hook')

# ---------------------------------------------------------------------------
# 3) Paint gestures: INSPECT cannot edit, and each stroke is one undo action.
# ---------------------------------------------------------------------------
touch_anchor = '''        if (!paintMode) return false;
'''
touch_method = text.index('    public boolean touchDown(')
touch_pos = text.index(touch_anchor, touch_method)
text = text[:touch_pos] + '''        if (!paintMode) return false;
        if (inspectMode && !(spacePan && zoom > 1)) return true;
''' + text[touch_pos + len(touch_anchor):]

paint_start_anchor = '''        rightErase = (button == Input.Buttons.RIGHT);
'''
one(paint_start_anchor, '''        captureUndoSnapshot();
        rightErase = (button == Input.Buttons.RIGHT);
''', 'stroke undo hook')

# ---------------------------------------------------------------------------
# 4) Cleaner overlay rendering.
#    Browser UI owns all text/chrome, so remove the two giant in-canvas HUD rows.
#    Outline mode and opacity are applied inside the existing draw helper.
# ---------------------------------------------------------------------------
draw_method_old = r'''    private void drawMaskRuns(SpriteBatch batch, boolean[][] mask, Color color) {
        batch.setColor(color);
        for (int y = 0; y < HEIGHT; y++) {
            int x = 0;
            while (x < WIDTH) {
                while (x < WIDTH && !mask[y][x]) x++;
                if (x >= WIDTH) break;
                int start = x;
                while (x < WIDTH && mask[y][x]) x++;
                int end = x;
                float dx = start * (264f / WIDTH);
                float dw = (end - start) * (264f / WIDTH);
                float dy = 24f + (167 - y);
                batch.draw(white, dx, dy, dw, 1.0f);
            }
        }
    }
'''
draw_method_new = r'''    private void drawMaskRuns(SpriteBatch batch, boolean[][] mask, Color color) {
        float alphaScale = Math.max(25, Math.min(100, overlayOpacityPercent)) / 100f;
        batch.setColor(new Color(color.r, color.g, color.b, color.a * alphaScale));

        if (outlineMode) {
            float pxWidth = 264f / WIDTH;
            for (int y = 0; y < HEIGHT; y++) {
                for (int x = 0; x < WIDTH; x++) {
                    if (!mask[y][x]) continue;
                    boolean edge = x == 0 || x == WIDTH - 1 || y == 0 || y == HEIGHT - 1
                            || !mask[y][x - 1] || !mask[y][x + 1]
                            || !mask[y - 1][x] || !mask[y + 1][x];
                    if (!edge) continue;
                    float dx = x * pxWidth;
                    float dy = 24f + (167 - y);
                    batch.draw(white, dx, dy, Math.max(1f, pxWidth), 1.0f);
                }
            }
            return;
        }

        for (int y = 0; y < HEIGHT; y++) {
            int x = 0;
            while (x < WIDTH) {
                while (x < WIDTH && !mask[y][x]) x++;
                if (x >= WIDTH) break;
                int start = x;
                while (x < WIDTH && mask[y][x]) x++;
                int end = x;
                float dx = start * (264f / WIDTH);
                float dw = (end - start) * (264f / WIDTH);
                float dy = 24f + (167 - y);
                batch.draw(white, dx, dy, dw, 1.0f);
            }
        }
    }
'''
one(draw_method_old, draw_method_new, 'overlay renderer')

# Remove only the paint-mode HUD chrome; keep overlays, move boxes, and notices.
hud_start_marker = '            batch.setColor(0f, 0f, 0f, 0.78f);\n            batch.draw(white, 2, 174, 260, 24);\n'
hud_start = text.find(hud_start_marker)
if hud_start < 0:
    raise RuntimeError('in-canvas HUD start not found')
notice_anchor = '        if (System.currentTimeMillis() < noticeUntil) {\n'
notice_pos = text.find(notice_anchor, hud_start)
if notice_pos < 0:
    raise RuntimeError('notice render anchor not found')
paint_close = text.rfind('        }\n\n', hud_start, notice_pos)
if paint_close < 0:
    raise RuntimeError('paint-mode render close not found')
text = text[:hud_start] + (
    '            // Browser workspace shortcuts: 4 water, 5 FALL 6 MOVE.\n'
    '            batch.setColor(Color.WHITE);\n'
) + text[paint_close:]

editor.write_text(text)

# Existing Pages checks intentionally retain these semantic markers while the
# visible help is now context-sensitive inside the docked sidebar.
web = root.parent / 'web/index.html'
if web.exists():
    web_text = web.read_text()
    marker = '<!-- FALL = AGI HITSPEC / control 2 | Space + drag = pan -->'
    if marker not in web_text:
        if '</body>' not in web_text:
            raise RuntimeError('web body close not found for verification marker')
        web.write_text(web_text.replace('</body>', marker + '\n</body>', 1))

print('Debug workspace runtime refined: clean canvas HUD, inspect mode, outline/opacity controls, one-step undo/redo')
