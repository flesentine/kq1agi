#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_mask_ui_sync.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

# The browser already owns the PAINT/TEST control and brush overlay. The old
# in-canvas PAINT button could toggle Java paint mode without the browser seeing
# that toggle, leaving the brush-size panel visible during test play. Remove that
# second entry point so Java and the browser UI cannot drift apart.
touch_old = '''    @Override
    public boolean touchDown(int screenX, int screenY, int pointer, int button) {
        int[] p = point(screenX, screenY);
        if (!paintMode) {
            // Always-visible top-right PAINT button. It deliberately lives inside
            // the 160x168 picture plane so hit testing stays correct on resized views.
            if (p != null && p[0] >= 132 && p[0] <= 159 && p[1] >= 0 && p[1] <= 13) {
                togglePaintMode();
                return true;
            }
            return false;
        }
'''
touch_new = '''    @Override
    public boolean touchDown(int screenX, int screenY, int pointer, int button) {
        int[] p = point(screenX, screenY);
        if (!paintMode) return false;
'''
if text.count(touch_old) != 1:
    raise RuntimeError('SceneMaskEditor in-canvas PAINT touch target not found')
text = text.replace(touch_old, touch_new)

render_old = '''        } else {
            // Visible mouse entry point so the Sierra parser never has to be used
            // to enter the editor. Hit area maps to mask x=132..159, y=0..13.
            batch.setColor(0f, 0f, 0f, 0.78f);
            batch.draw(white, 218, 178, 44, 13);
            batch.setColor(Color.WHITE);
            font.draw(batch, "PAINT", 224, 188);
        }
'''
render_new = '''        }

        // Browser PAINT/TEST control is authoritative. Keeping a second in-canvas
        // toggle here can desynchronise the fixed browser brush-size overlay.
'''
if text.count(render_old) != 1:
    raise RuntimeError('SceneMaskEditor in-canvas PAINT render block not found')
text = text.replace(render_old, render_new)

editor.write_text(text)
print('Scene mask UI sync fixed: browser PAINT/TEST is the single toggle; brush overlay cannot remain from canvas-only test toggles')
