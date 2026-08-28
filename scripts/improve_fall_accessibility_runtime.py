#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: improve_fall_accessibility_runtime.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()


def one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


# FALL needs its own visual language. Colour remains useful, but the mask must be
# understandable without hue: editable HITSPEC gets diagonal black/white stripes,
# exact detected script triggers get split black/white marks, and only the
# expanded display halo gets a dotted boundary. None of this changes mask bits.
render_anchor = '''    public void render(SpriteBatch batch) {\n'''
helpers = r'''    private boolean fallMaskEdge(boolean[][] mask, int x, int y) {
        return x == 0 || x == WIDTH - 1 || y == 0 || y == HEIGHT - 1
                || !mask[y][x - 1] || !mask[y][x + 1]
                || !mask[y - 1][x] || !mask[y + 1][x];
    }

    private void drawFallPixel(SpriteBatch batch, int x, int y) {
        float pxWidth = 264f / WIDTH;
        float dx = x * pxWidth;
        float dy = 24f + (167 - y);
        batch.draw(white, dx, dy, Math.max(1f, pxWidth), 1.0f);
    }

    private void drawFallHalfPixel(SpriteBatch batch, int x, int y) {
        float pxWidth = 264f / WIDTH;
        float dx = x * pxWidth;
        float dy = 24f + (167 - y);
        float half = Math.max(0.5f, pxWidth * 0.5f);
        batch.draw(white, dx + (pxWidth - half), dy, half, 1.0f);
    }

    private void drawAccessibleEditableFall(SpriteBatch batch) {
        // Preserve the existing overlay-opacity behaviour for the coloured body.
        // The identifying black/white marks below intentionally stay strong so
        // FALL remains readable even at the 25% slider setting.
        drawMaskRuns(batch, masks[FALL], new Color(1f, 0.86f, 0.08f, 0.52f));

        if (outlineMode) {
            batch.setColor(new Color(0f, 0f, 0f, 0.96f));
            for (int y = 0; y < HEIGHT; y++) for (int x = 0; x < WIDTH; x++) {
                if (masks[FALL][y][x] && fallMaskEdge(masks[FALL], x, y)
                        && ((x + y) & 1) == 0) drawFallPixel(batch, x, y);
            }
            batch.setColor(new Color(1f, 1f, 1f, 0.98f));
            for (int y = 0; y < HEIGHT; y++) for (int x = 0; x < WIDTH; x++) {
                if (masks[FALL][y][x] && fallMaskEdge(masks[FALL], x, y)
                        && ((x + y) & 1) == 1) drawFallPixel(batch, x, y);
            }
        } else {
            // Two adjacent diagonal bands make a high-contrast //// pattern.
            batch.setColor(new Color(0f, 0f, 0f, 0.92f));
            for (int y = 0; y < HEIGHT; y++) for (int x = 0; x < WIDTH; x++) {
                if (masks[FALL][y][x] && ((x + y) % 6) == 0) drawFallPixel(batch, x, y);
            }
            batch.setColor(new Color(1f, 1f, 1f, 0.95f));
            for (int y = 0; y < HEIGHT; y++) for (int x = 0; x < WIDTH; x++) {
                if (masks[FALL][y][x] && ((x + y) % 6) == 1) drawFallPixel(batch, x, y);
            }
        }
        batch.setColor(Color.WHITE);
    }

    private void drawAccessibleScriptFall(SpriteBatch batch) {
        // The 2-pixel-expanded mask is DISPLAY ONLY. Draw only its boundary and
        // keep it dotted so it cannot be mistaken for the exact gameplay trigger.
        batch.setColor(new Color(0f, 0f, 0f, 0.98f));
        for (int y = 0; y < HEIGHT; y++) for (int x = 0; x < WIDTH; x++) {
            if (scriptFallDisplay[y][x] && fallMaskEdge(scriptFallDisplay, x, y)
                    && ((x + y) % 4) == 0) drawFallPixel(batch, x, y);
        }
        batch.setColor(new Color(1f, 1f, 1f, 1f));
        for (int y = 0; y < HEIGHT; y++) for (int x = 0; x < WIDTH; x++) {
            if (scriptFallDisplay[y][x] && fallMaskEdge(scriptFallDisplay, x, y)
                    && ((x + y) % 4) == 2) drawFallPixel(batch, x, y);
        }

        // Exact SCRIPT_FALL bits are rendered on top as two-tone marks. Even a
        // one-pixel Sierra position test therefore remains visible on any art.
        batch.setColor(new Color(0f, 0f, 0f, 1f));
        for (int y = 0; y < HEIGHT; y++) for (int x = 0; x < WIDTH; x++) {
            if (masks[SCRIPT_FALL][y][x]) drawFallPixel(batch, x, y);
        }
        batch.setColor(new Color(1f, 1f, 1f, 1f));
        for (int y = 0; y < HEIGHT; y++) for (int x = 0; x < WIDTH; x++) {
            if (masks[SCRIPT_FALL][y][x]) drawFallHalfPixel(batch, x, y);
        }
        batch.setColor(Color.WHITE);
    }

    public void render(SpriteBatch batch) {
'''
one(render_anchor, helpers, 'SceneMaskEditor render anchor')

old_draw = '''                if (layerVisible[FALL]) {\n                    rebuildScriptFallDisplay();\n                    drawMaskRuns(batch, scriptFallDisplay, new Color(1f, 0.48f, 0.05f, 0.55f));\n                    drawMaskRuns(batch, masks[FALL], new Color(1f, 0.08f, 0.62f, 0.52f));\n                }\n'''
new_draw = '''                if (layerVisible[FALL]) {\n                    rebuildScriptFallDisplay();\n                    drawAccessibleEditableFall(batch);\n                    // Script markers render last so editable FALL can never bury them.\n                    drawAccessibleScriptFall(batch);\n                }\n'''
one(old_draw, new_draw, 'FALL render block')

editor.write_text(text)
print('FALL accessibility renderer installed: striped HITSPEC, exact two-tone script marks, dotted display halo')
