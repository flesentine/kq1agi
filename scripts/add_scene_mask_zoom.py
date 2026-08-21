#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scene_mask_zoom.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# Add cursor-centred paint zoom to SceneMaskEditor. The mask remains 160x168;
# only the GameScreen camera magnifies it, so painting still lands on exact AGI
# coordinates.
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

field = '''    private int mode = OCCLUDER;
    private int brush = 2;
    private boolean eraser;
'''
field_repl = '''    private int mode = OCCLUDER;
    private int brush = 2;
    private boolean eraser;
    private int zoom = 1;
    private int zoomFocusX = WIDTH / 2;
    private int zoomFocusY = HEIGHT / 2;
'''
if text.count(field) != 1:
    raise RuntimeError('SceneMaskEditor mode/brush field block not found')
text = text.replace(field, field_repl)

anchor = '''    private int selectedLayer() {
        return mode;
    }

    @Override
    public boolean keyDown(int keycode) {
'''
helpers = '''    private int selectedLayer() {
        return mode;
    }

    public boolean isPaintMode() {
        return paintMode;
    }

    /** Magnification used only while painting: 1x, 2x, 4x, or 8x. */
    public float getViewMagnification() {
        return paintMode ? zoom : 1f;
    }

    /** Camera focus expressed in GameScreen's 264x200 AGI world coordinates. */
    public float getViewCenterX() {
        return (zoomFocusX + 0.5f) * (264f / WIDTH);
    }

    public float getViewCenterY() {
        return 24f + (167 - zoomFocusY) + 0.5f;
    }

    private void focusZoomAtMouse() {
        int[] p = point(Gdx.input.getX(), Gdx.input.getY());
        if (p != null) {
            zoomFocusX = p[0];
            zoomFocusY = p[1];
        }
    }

    private void zoomIn() {
        focusZoomAtMouse();
        if (zoom < 2) zoom = 2;
        else if (zoom < 4) zoom = 4;
        else zoom = 8;
        notice("ZOOM " + zoom + "X");
    }

    private void zoomOut() {
        focusZoomAtMouse();
        if (zoom > 4) zoom = 4;
        else if (zoom > 2) zoom = 2;
        else zoom = 1;
        notice("ZOOM " + zoom + "X");
    }

    private void resetZoom() {
        zoom = 1;
        zoomFocusX = WIDTH / 2;
        zoomFocusY = HEIGHT / 2;
        notice("ZOOM 1X");
    }

    @Override
    public boolean keyDown(int keycode) {
'''
if text.count(anchor) != 1:
    raise RuntimeError('SceneMaskEditor selectedLayer/keyDown anchor not found')
text = text.replace(anchor, helpers)

keys = '''        if (keycode == Input.Keys.NUM_1) { mode = OCCLUDER; eraser = false; }
        else if (keycode == Input.Keys.NUM_2) { mode = COLLISION; eraser = false; }
        else if (keycode == Input.Keys.NUM_3) { mode = BEHIND; eraser = false; }
        else if (keycode == Input.Keys.E) eraser = !eraser;
        else if (keycode == Input.Keys.LEFT_BRACKET) brush = Math.max(1, brush - 1);
'''
keys_repl = '''        if (keycode == Input.Keys.NUM_1) { mode = OCCLUDER; eraser = false; }
        else if (keycode == Input.Keys.NUM_2) { mode = COLLISION; eraser = false; }
        else if (keycode == Input.Keys.NUM_3) { mode = BEHIND; eraser = false; }
        else if (keycode == Input.Keys.E) eraser = !eraser;
        else if (keycode == Input.Keys.Z) {
            if (Gdx.input.isKeyPressed(Input.Keys.SHIFT_LEFT)
                    || Gdx.input.isKeyPressed(Input.Keys.SHIFT_RIGHT)) zoomOut();
            else zoomIn();
        }
        else if (keycode == Input.Keys.NUM_0) resetZoom();
        else if (keycode == Input.Keys.LEFT_BRACKET) brush = Math.max(1, brush - 1);
'''
if text.count(keys) != 1:
    raise RuntimeError('SceneMaskEditor control-key block not found')
text = text.replace(keys, keys_repl)

hud = '''            font.draw(batch, "MASK PAINT  room " + room + "  mode=" + modeName + "  brush=" + brush,
                    6, 195);
            font.draw(batch, "M test | 1 front | 2 block | 3 behind | E erase | [ ] size | C clear | X copy",
                    6, 184);
'''
hud_repl = '''            font.draw(batch, "MASK PAINT  room " + room + "  mode=" + modeName + "  brush=" + brush + "  zoom=" + zoom + "x",
                    6, 195);
            font.draw(batch, "M test | 1 front | 2 block | 3 behind | E erase | Z zoom | Shift-Z out | 0 reset",
                    6, 184);
'''
if text.count(hud) != 1:
    raise RuntimeError('SceneMaskEditor HUD help block not found')
text = text.replace(hud, hud_repl)
editor.write_text(text)

# Make GameScreen's AGI camera zoom around the cursor-selected mask point while
# paint mode is active. viewport.unproject() then automatically maps clicks back
# to the correct 160x168 mask coordinate at every zoom level.
game = root / 'core/src/main/java/com/agifans/agile/GameScreen.java'
text = game.read_text()
old_camera = '''        gameScreenInputProcessor.setCameraXOffset(cameraXOffset);
        camera.position.set((ADJUSTED_WIDTH / 2) + cameraXOffset, (ADJUSTED_HEIGHT / 2) - cameraYOffset, 0.0f);
        camera.update();
'''
new_camera = '''        gameScreenInputProcessor.setCameraXOffset(cameraXOffset);

        float editorMagnification = sceneMaskEditor.getViewMagnification();
        if (camera instanceof OrthographicCamera) {
            ((OrthographicCamera)camera).zoom = 1f / editorMagnification;
        }

        if (sceneMaskEditor.isPaintMode() && editorMagnification > 1f) {
            float halfWidth = ADJUSTED_WIDTH / (2f * editorMagnification);
            float halfHeight = ADJUSTED_HEIGHT / (2f * editorMagnification);
            float centerX = Math.max(halfWidth,
                    Math.min(ADJUSTED_WIDTH - halfWidth, sceneMaskEditor.getViewCenterX()));
            float centerY = Math.max(halfHeight,
                    Math.min(ADJUSTED_HEIGHT - halfHeight, sceneMaskEditor.getViewCenterY()));
            camera.position.set(centerX, centerY, 0.0f);
        } else {
            camera.position.set((ADJUSTED_WIDTH / 2) + cameraXOffset,
                    (ADJUSTED_HEIGHT / 2) - cameraYOffset, 0.0f);
        }
        camera.update();
'''
if text.count(old_camera) != 1:
    raise RuntimeError('GameScreen camera-position block not found')
text = text.replace(old_camera, new_camera)
game.write_text(text)

print('Scene mask zoom installed: Z zoom in at cursor, Shift-Z out, 0 reset (1x/2x/4x/8x)')
