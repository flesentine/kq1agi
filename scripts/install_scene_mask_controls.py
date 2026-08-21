#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: install_scene_mask_controls.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

# ---------------------------------------------------------------------------
# Paint controls: use F2 rather than a printable character, swallow typed
# characters while painting, expose a visible mouse-click PAINT button, and add
# 1x/2x/4x/8x cursor-centred zoom.
# ---------------------------------------------------------------------------
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
    raise RuntimeError('SceneMaskEditor field block not found')
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
    }

    private void togglePaintMode() {
        ensureRoom();
        paintMode = !paintMode;
        if (paintMode) {
            data.setSceneMaskRoom(room);
            data.setSceneMaskEnabled(true);
            prefs.putBoolean(key("active"), true);
            notice("PAINT MODE ON");
        } else {
            saveRoom();
            resetZoom();
            notice("TEST MODE - MASKS LIVE");
        }
        data.setSceneMaskPaintMode(paintMode);
    }

    @Override
    public boolean keyDown(int keycode) {
'''
if text.count(anchor) != 1:
    raise RuntimeError('SceneMaskEditor selectedLayer/keyDown anchor not found')
text = text.replace(anchor, helpers)

old_toggle = '''        if (keycode == Input.Keys.GRAVE) {
            paintMode = !paintMode;
            if (paintMode) {
                data.setSceneMaskRoom(room);
                data.setSceneMaskEnabled(true);
                prefs.putBoolean(key("active"), true);
                notice("PAINT MODE ON");
            } else {
                saveRoom();
                notice("TEST MODE - MASKS LIVE");
            }
            data.setSceneMaskPaintMode(paintMode);
            return true;
        }
        if (!paintMode) return false;
'''
new_toggle = '''        if (keycode == Input.Keys.F2) {
            togglePaintMode();
            return true;
        }
        if (!paintMode) return false;
'''
if text.count(old_toggle) != 1:
    raise RuntimeError('SceneMaskEditor backtick toggle block not found')
text = text.replace(old_toggle, new_toggle)

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
        else if (keycode == Input.Keys.NUM_0) { resetZoom(); notice("ZOOM 1X"); }
        else if (keycode == Input.Keys.LEFT_BRACKET) brush = Math.max(1, brush - 1);
'''
if text.count(keys) != 1:
    raise RuntimeError('SceneMaskEditor editor-key block not found')
text = text.replace(keys, keys_repl)

# keyTyped is a separate libGDX event from keyDown. Consuming it while paint mode
# is active prevents 1/2/3/E/Z/etc from appearing in the Sierra parser.
keyup = '''    @Override
    public boolean keyUp(int keycode) {
        return paintMode;
    }

    @Override
    public boolean touchDown(int screenX, int screenY, int pointer, int button) {
        if (!paintMode) return false;
        int[] p = point(screenX, screenY);
'''
keyup_repl = '''    @Override
    public boolean keyUp(int keycode) {
        return paintMode || keycode == Input.Keys.F2;
    }

    @Override
    public boolean keyTyped(char character) {
        return paintMode;
    }

    @Override
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
if text.count(keyup) != 1:
    raise RuntimeError('SceneMaskEditor keyUp/touchDown block not found')
text = text.replace(keyup, keyup_repl)

# The old touchDown block declared p after the paint-mode early return; after the
# replacement above p already exists.
text = text.replace('''        int[] p = point(screenX, screenY);
        if (p == null) return true;
        rightErase = (button == Input.Buttons.RIGHT);
''', '''        if (p == null) return true;
        rightErase = (button == Input.Buttons.RIGHT);
''', 1)

# Always render a small entry button in test/play mode. Runtime overlay and paint
# HUD continue to use the same game-camera coordinate system.
render_start = '''    public void render(SpriteBatch batch) {
        ensureRoom();
        if (!data.getSceneMaskEnabled() && !paintMode) return;

        Texture background = RoomBackgrounds.getTexture(room);
        batch.enableBlending();
        batch.begin();
'''
render_repl = '''    public void render(SpriteBatch batch) {
        ensureRoom();

        Texture background = RoomBackgrounds.getTexture(room);
        batch.enableBlending();
        batch.begin();
'''
if text.count(render_start) != 1:
    raise RuntimeError('SceneMaskEditor render start not found')
text = text.replace(render_start, render_repl)

hud = '''            font.draw(batch, "MASK PAINT  room " + room + "  mode=" + modeName + "  brush=" + brush,
                    6, 195);
            font.draw(batch, "` test | 1 front | 2 block | 3 behind | E erase | [ ] size | C clear | X copy",
                    6, 184);
        }

        if (System.currentTimeMillis() < noticeUntil) {
'''
hud_repl = '''            font.draw(batch, "MASK PAINT  room " + room + "  mode=" + modeName + "  brush=" + brush + "  zoom=" + zoom + "x",
                    6, 195);
            font.draw(batch, "F2 test | 1 front | 2 block | 3 behind | E erase | Z zoom | Shift-Z out | 0 reset",
                    6, 184);
        } else {
            // Visible mouse entry point so the Sierra parser never has to be used
            // to enter the editor. Hit area maps to mask x=132..159, y=0..13.
            batch.setColor(0f, 0f, 0f, 0.78f);
            batch.draw(white, 218, 178, 44, 13);
            batch.setColor(Color.WHITE);
            font.draw(batch, "F2 PAINT", 222, 188);
        }

        if (System.currentTimeMillis() < noticeUntil) {
'''
if text.count(hud) != 1:
    raise RuntimeError('SceneMaskEditor HUD block not found')
text = text.replace(hud, hud_repl)

# Keep source comments accurate.
text = text.replace('` toggles paint mode.', 'F2 toggles paint mode.')
editor.write_text(text)

# ---------------------------------------------------------------------------
# Camera zoom: magnifies only the paint view; viewport.unproject then maps mouse
# input back onto the same exact 160x168 mask coordinates.
# ---------------------------------------------------------------------------
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

print('Scene mask controls installed: visible PAINT button, F2 toggle, parser-safe input, Z zoom')
