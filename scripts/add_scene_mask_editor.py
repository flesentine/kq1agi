#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scene_mask_editor.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# ---------------------------------------------------------------------------
# 1) Shared UI <-> worker mask transport.
# ---------------------------------------------------------------------------
variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
text = variable_data.read_text()
needle = '''    default void setModernRoomOverlay(boolean value) {
        // Optional platform hook.
    }
    
}'''
replacement = '''    default void setModernRoomOverlay(boolean value) {
        // Optional platform hook.
    }

    // Live scene-mask editor. Browser/GWT overrides these with SharedArrayBuffer
    // storage so the UI painter and interpreter worker see changes immediately.
    default boolean getSceneMaskEnabled() { return false; }
    default void setSceneMaskEnabled(boolean value) { }
    default int getSceneMaskRoom() { return -1; }
    default void setSceneMaskRoom(int room) { }
    default boolean getSceneMaskOccluderActive() { return false; }
    default void setSceneMaskOccluderActive(boolean value) { }
    default boolean getSceneMaskPaintMode() { return false; }
    default void setSceneMaskPaintMode(boolean value) { }
    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }
    default void setSceneMaskBit(int layer, int x, int y, boolean value) { }
    default void clearSceneMaskLayer(int layer) { }
    
}'''
if text.count(needle) != 1:
    raise RuntimeError('VariableData modern overlay tail not found')
variable_data.write_text(text.replace(needle, replacement))

# GWT stores three 160x168 bit planes (occluder, collision, behind-zone) in the
# same SharedArrayBuffer already used by the interpreter worker and UI thread.
gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()
const = '    private static final int MODERN_ROOM_OVERLAY = 518;\n'
extra = '''    private static final int MODERN_ROOM_OVERLAY = 518;
    private static final int SCENE_MASK_ENABLED = 519;
    private static final int SCENE_MASK_ROOM = 520;
    private static final int SCENE_MASK_OCCLUDER_ACTIVE = 521;
    private static final int SCENE_MASK_PAINT_MODE = 522;
    private static final int SCENE_MASK_BITS = 523;
    private static final int SCENE_MASK_WIDTH = 160;
    private static final int SCENE_MASK_HEIGHT = 168;
    private static final int SCENE_MASK_WORDS = ((SCENE_MASK_WIDTH * SCENE_MASK_HEIGHT) + 31) / 32;
    private static final int SCENE_MASK_LAYERS = 3;
'''
if text.count(const) != 1:
    raise RuntimeError('GwtVariableData modern overlay constant not found')
text = text.replace(const, extra)

# 512 standard slots + 7 old extras + 4 editor metadata + 3*840 bit words.
if text.count('Defines.NUMVARS + Defines.NUMFLAGS + 7') != 2:
    raise RuntimeError('GwtVariableData post-overlay capacity markers not found')
text = text.replace('Defines.NUMVARS + Defines.NUMFLAGS + 7',
                    'Defines.NUMVARS + Defines.NUMFLAGS + 2531')

method_needle = '''    @Override
    public void setModernRoomOverlay(boolean value) {
        variableArray.set(MODERN_ROOM_OVERLAY, value ? TRUE : FALSE);
    }

    /**
     * Gets the SharedArrayBuffer used internally by the variable array.
'''
method_replacement = '''    @Override
    public void setModernRoomOverlay(boolean value) {
        variableArray.set(MODERN_ROOM_OVERLAY, value ? TRUE : FALSE);
    }

    @Override
    public boolean getSceneMaskEnabled() {
        return variableArray.get(SCENE_MASK_ENABLED) == TRUE;
    }

    @Override
    public void setSceneMaskEnabled(boolean value) {
        variableArray.set(SCENE_MASK_ENABLED, value ? TRUE : FALSE);
    }

    @Override
    public int getSceneMaskRoom() {
        return variableArray.get(SCENE_MASK_ROOM);
    }

    @Override
    public void setSceneMaskRoom(int room) {
        variableArray.set(SCENE_MASK_ROOM, room);
    }

    @Override
    public boolean getSceneMaskOccluderActive() {
        return variableArray.get(SCENE_MASK_OCCLUDER_ACTIVE) == TRUE;
    }

    @Override
    public void setSceneMaskOccluderActive(boolean value) {
        variableArray.set(SCENE_MASK_OCCLUDER_ACTIVE, value ? TRUE : FALSE);
    }

    @Override
    public boolean getSceneMaskPaintMode() {
        return variableArray.get(SCENE_MASK_PAINT_MODE) == TRUE;
    }

    @Override
    public void setSceneMaskPaintMode(boolean value) {
        variableArray.set(SCENE_MASK_PAINT_MODE, value ? TRUE : FALSE);
    }

    private int sceneMaskIndex(int layer, int x, int y) {
        if (layer < 0 || layer >= SCENE_MASK_LAYERS ||
                x < 0 || x >= SCENE_MASK_WIDTH || y < 0 || y >= SCENE_MASK_HEIGHT) {
            return -1;
        }
        int bitIndex = (y * SCENE_MASK_WIDTH) + x;
        return SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS) + (bitIndex >>> 5);
    }

    @Override
    public boolean getSceneMaskBit(int layer, int x, int y) {
        int index = sceneMaskIndex(layer, x, y);
        if (index < 0) return false;
        int bitIndex = (y * SCENE_MASK_WIDTH) + x;
        return (variableArray.get(index) & (1 << (bitIndex & 31))) != 0;
    }

    @Override
    public void setSceneMaskBit(int layer, int x, int y, boolean value) {
        int index = sceneMaskIndex(layer, x, y);
        if (index < 0) return;
        int bitIndex = (y * SCENE_MASK_WIDTH) + x;
        int bit = 1 << (bitIndex & 31);
        int word = variableArray.get(index);
        variableArray.set(index, value ? (word | bit) : (word & ~bit));
    }

    @Override
    public void clearSceneMaskLayer(int layer) {
        if (layer < 0 || layer >= SCENE_MASK_LAYERS) return;
        int start = SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);
        for (int i = 0; i < SCENE_MASK_WORDS; i++) {
            variableArray.set(start + i, 0);
        }
    }

    /**
     * Gets the SharedArrayBuffer used internally by the variable array.
'''
if text.count(method_needle) != 1:
    raise RuntimeError('GwtVariableData modern overlay methods not found')
gwt.write_text(text.replace(method_needle, method_replacement))

# ---------------------------------------------------------------------------
# 2) Worker-side runtime semantics.
# ---------------------------------------------------------------------------
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
runtime.write_text(r'''package com.agifans.agile;

/** Worker-side semantics for the live scene mask editor. */
public final class SceneMaskRuntime {
    public static final int OCCLUDER = 0;
    public static final int COLLISION = 1;
    public static final int BEHIND = 2;

    private SceneMaskRuntime() {
    }

    public static boolean editorOwnsRoom(GameState state) {
        VariableData data = state.getVariableData();
        return data.getSceneMaskEnabled()
                && data.getSceneMaskRoom() == state.getVar(Defines.CURROOM);
    }

    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
        if (editorOwnsRoom(state)) {
            VariableData data = state.getVariableData();
            // Paint mode freezes Graham in place so mouse painting never moves him.
            if (data.getSceneMaskPaintMode()) {
                return true;
            }
            if (y < 0 || y >= 168) {
                return false;
            }
            int left = Math.max(0, Math.min(leftX, rightX));
            int right = Math.min(159, Math.max(leftX, rightX));
            for (int x = left; x <= right; x++) {
                if (data.getSceneMaskBit(COLLISION, x, y)) {
                    return true;
                }
            }
            return false;
        }

        // Existing hand-tuned fallback remains available until the editor takes
        // ownership of a room.
        return ModernRoomDepth.blocksEgoBaseline(
                state.gameId,
                state.getVar(Defines.CURROOM),
                leftX,
                rightX,
                y);
    }

    public static void updateOccluderFlag(GameState state) {
        VariableData data = state.getVariableData();
        boolean active = false;
        if (editorOwnsRoom(state) && state.ego != null && state.ego.drawn) {
            int center = state.ego.x + (state.ego.xSize() / 2);
            int y = state.ego.y;
            if (y >= 0 && y < 168) {
                // A small foot probe makes the green behind-zone easy to paint.
                for (int x = center - 1; x <= center + 1 && !active; x++) {
                    active = data.getSceneMaskBit(BEHIND, x, y);
                }
            }
        }
        data.setSceneMaskOccluderActive(active);
    }
}
''')

# Expose VariableData to the runtime helper and publish behind-zone state each
# animation redraw.
game_state = root / 'core/src/main/java/com/agifans/agile/GameState.java'
text = game_state.read_text()
field = '    private VariableData variableData;\n'
field_repl = '''    private VariableData variableData;

    public VariableData getVariableData() {
        return variableData;
    }
'''
if text.count(field) != 1:
    raise RuntimeError('GameState VariableData field not found')
text = text.replace(field, field_repl)

draw_marker = '        // Draw the AnimatedObjects to screen in priority order.\n'
if text.count(draw_marker) != 1:
    raise RuntimeError('GameState drawObjects(List) draw marker not found')
text = text.replace(draw_marker,
                    '        SceneMaskRuntime.updateOccluderFlag(this);\n\n' + draw_marker)
game_state.write_text(text)

# Make the live mask editor authoritative for collision, priority and old control
# lines whenever it owns the current room.
animated = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
text = animated.read_text()

hard_collision = '''                if (ModernRoomDepth.blocksEgoBaseline(
                        state.gameId,
                        state.getVar(Defines.CURROOM),
                        footLeft,
                        footRight,
                        oy)) {'''
if text.count(hard_collision) != 1:
    raise RuntimeError('AnimatedObject direct hard-collision call not found')
text = text.replace(hard_collision,
                    '''                if (SceneMaskRuntime.blocksEgoMovement(
                        state,
                        footLeft,
                        footRight,
                        oy)) {''')

# The older canBeHere fallback must not add a second tree collision while the
# editor owns the room.
canbe = '''            if ((this.objectNumber == 0) && canBeHere && ModernRoomDepth.blocksEgoBaseline(
'''
if text.count(canbe) != 1:
    raise RuntimeError('AnimatedObject canBeHere modern collision block not found')
text = text.replace(canbe,
                    '''            if ((this.objectNumber == 0) && canBeHere
                    && !SceneMaskRuntime.editorOwnsRoom(state)
                    && ModernRoomDepth.blocksEgoBaseline(
''')

# While editing a room, old invisible EGA picture priority must not crop sprites.
priority_hook = '''                    if (modernPriority >= 0) {
                        priorityIndex = modernPriority;
                    }
'''
if text.count(priority_hook) != 1:
    raise RuntimeError('AnimatedObject modern priority hook not found')
text = text.replace(priority_hook, '''                    if (SceneMaskRuntime.editorOwnsRoom(state)) {
                        priorityIndex = 4;
                    } else if (modernPriority >= 0) {
                        priorityIndex = modernPriority;
                    }
''')

# And legacy blocking colours 0/1 are replaced by the editor's blue collision
# layer. Water/special controls remain unchanged.
control_hook = '''                // For ego only, neutralise the OLD tree's blocking controls in its old
                // corridor. Preserve special=2 and water=3 exactly as-is.
                if ((this.objectNumber == 0)
                        && (priority == 0 || priority == 1)
                        && ModernRoomDepth.insideOldTreeControlCorridor(
                                state.gameId,
                                state.getVar(Defines.CURROOM),
                                baselineX,
                                this.y)) {
                    priority = 4;
                }
'''
if text.count(control_hook) != 1:
    raise RuntimeError('AnimatedObject old-control neutralisation hook not found')
text = text.replace(control_hook, '''                // If the live editor owns this room, its blue collision plane is
                // authoritative. Otherwise retain the older Room 1 compatibility fix.
                if ((this.objectNumber == 0)
                        && (priority == 0 || priority == 1)
                        && SceneMaskRuntime.editorOwnsRoom(state)) {
                    priority = 4;
                } else if ((this.objectNumber == 0)
                        && (priority == 0 || priority == 1)
                        && ModernRoomDepth.insideOldTreeControlCorridor(
                                state.gameId,
                                state.getVar(Defines.CURROOM),
                                baselineX,
                                this.y)) {
                    priority = 4;
                }
''')
animated.write_text(text)

# ---------------------------------------------------------------------------
# 3) UI-thread paint editor with per-room browser persistence.
# ---------------------------------------------------------------------------
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
editor.write_text(r'''package com.agifans.agile;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.Input;
import com.badlogic.gdx.InputAdapter;
import com.badlogic.gdx.Preferences;
import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.Pixmap;
import com.badlogic.gdx.graphics.Texture;
import com.badlogic.gdx.graphics.g2d.BitmapFont;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;

/**
 * Live in-game authoring tool for replacement-room depth and collision.
 *
 * M toggles paint mode. 1=foreground/occluder, 2=collision, 3=behind-zone,
 * E=eraser, [ ] brush size, C=clear current layer, S=save, X=copy JSON.
 * Masks apply immediately when paint mode is exited and are saved per room in
 * browser Preferences/localStorage.
 */
public class SceneMaskEditor extends InputAdapter {
    public static final int WIDTH = 160;
    public static final int HEIGHT = 168;
    private static final int OCCLUDER = 0;
    private static final int COLLISION = 1;
    private static final int BEHIND = 2;
    private static final int ERASER = 3;

    private final GameScreen gameScreen;
    private final VariableData data;
    private final Preferences prefs;
    private final boolean[][][] masks = new boolean[3][HEIGHT][WIDTH];
    private final Texture white;
    private final BitmapFont font;

    private int room = -1;
    private int mode = OCCLUDER;
    private int brush = 2;
    private boolean paintMode;
    private boolean dirty;
    private boolean rightErase;
    private String notice = "";
    private long noticeUntil;

    public SceneMaskEditor(GameScreen gameScreen) {
        this.gameScreen = gameScreen;
        this.data = gameScreen.getAgileRunner().getVariableData();
        this.prefs = Gdx.app.getPreferences("agi-scene-mask-editor-v1");

        Pixmap pixel = new Pixmap(1, 1, Pixmap.Format.RGBA8888);
        pixel.setColor(Color.WHITE);
        pixel.fill();
        white = new Texture(pixel);
        pixel.dispose();

        font = new BitmapFont();
        font.getData().setScale(0.55f);
    }

    public void dispose() {
        saveRoom();
        white.dispose();
        font.dispose();
    }

    private String key(String suffix) {
        return "room_" + room + "_" + suffix;
    }

    private void ensureRoom() {
        int current = data.getVar(Defines.CURROOM);
        if (current == room) return;
        saveRoom();
        room = current;
        for (int layer = 0; layer < 3; layer++) {
            for (int y = 0; y < HEIGHT; y++) {
                for (int x = 0; x < WIDTH; x++) masks[layer][y][x] = false;
            }
        }
        decode(prefs.getString(key("occluder"), ""), masks[OCCLUDER]);
        decode(prefs.getString(key("collision"), ""), masks[COLLISION]);
        decode(prefs.getString(key("behind"), ""), masks[BEHIND]);
        boolean active = prefs.getBoolean(key("active"), false);
        data.setSceneMaskRoom(room);
        data.setSceneMaskEnabled(active);
        data.setSceneMaskPaintMode(false);
        syncAll();
        dirty = false;
    }

    private void syncAll() {
        for (int layer = 0; layer < 3; layer++) {
            data.clearSceneMaskLayer(layer);
            for (int y = 0; y < HEIGHT; y++) {
                for (int x = 0; x < WIDTH; x++) {
                    if (masks[layer][y][x]) data.setSceneMaskBit(layer, x, y, true);
                }
            }
        }
    }

    private String encode(boolean[][] mask) {
        StringBuilder out = new StringBuilder(HEIGHT * 40);
        for (int y = 0; y < HEIGHT; y++) {
            for (int x = 0; x < WIDTH; x += 4) {
                int value = 0;
                for (int bit = 0; bit < 4; bit++) {
                    if (mask[y][x + bit]) value |= 1 << bit;
                }
                out.append(Character.forDigit(value, 16));
            }
        }
        return out.toString();
    }

    private void decode(String text, boolean[][] mask) {
        if (text == null || text.length() != HEIGHT * 40) return;
        int p = 0;
        for (int y = 0; y < HEIGHT; y++) {
            for (int x = 0; x < WIDTH; x += 4) {
                int value = Character.digit(text.charAt(p++), 16);
                if (value < 0) value = 0;
                for (int bit = 0; bit < 4; bit++) {
                    mask[y][x + bit] = (value & (1 << bit)) != 0;
                }
            }
        }
    }

    private void saveRoom() {
        if (room < 0 || (!dirty && !paintMode)) return;
        prefs.putString(key("occluder"), encode(masks[OCCLUDER]));
        prefs.putString(key("collision"), encode(masks[COLLISION]));
        prefs.putString(key("behind"), encode(masks[BEHIND]));
        prefs.putBoolean(key("active"), data.getSceneMaskEnabled());
        prefs.flush();
        dirty = false;
    }

    private void notice(String value) {
        notice = value;
        noticeUntil = System.currentTimeMillis() + 2200;
    }

    private int[] point(int screenX, int screenY) {
        return gameScreen.sceneMaskPoint(screenX, screenY);
    }

    private void paint(int cx, int cy, boolean erase) {
        ensureRoom();
        if (mode == ERASER) erase = true;
        int layer = (mode == ERASER ? OCCLUDER : mode);
        // Eraser removes the selected last non-eraser layer; E toggles back to
        // occluder by default, while right-click erases the currently selected layer.
        if (mode == ERASER) layer = OCCLUDER;
        int radius = Math.max(1, brush);
        for (int y = cy - radius; y <= cy + radius; y++) {
            for (int x = cx - radius; x <= cx + radius; x++) {
                if (x < 0 || x >= WIDTH || y < 0 || y >= HEIGHT) continue;
                int dx = x - cx;
                int dy = y - cy;
                if ((dx * dx) + (dy * dy) > radius * radius) continue;
                masks[layer][y][x] = !erase;
                data.setSceneMaskBit(layer, x, y, !erase);
            }
        }
        dirty = true;
    }

    private int selectedLayer() {
        return mode == ERASER ? OCCLUDER : mode;
    }

    @Override
    public boolean keyDown(int keycode) {
        ensureRoom();
        if (keycode == Input.Keys.M) {
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

        if (keycode == Input.Keys.NUM_1) mode = OCCLUDER;
        else if (keycode == Input.Keys.NUM_2) mode = COLLISION;
        else if (keycode == Input.Keys.NUM_3) mode = BEHIND;
        else if (keycode == Input.Keys.E) mode = (mode == ERASER ? OCCLUDER : ERASER);
        else if (keycode == Input.Keys.LEFT_BRACKET) brush = Math.max(1, brush - 1);
        else if (keycode == Input.Keys.RIGHT_BRACKET) brush = Math.min(12, brush + 1);
        else if (keycode == Input.Keys.C) {
            int layer = selectedLayer();
            for (int y = 0; y < HEIGHT; y++) {
                for (int x = 0; x < WIDTH; x++) masks[layer][y][x] = false;
            }
            data.clearSceneMaskLayer(layer);
            dirty = true;
            notice("LAYER CLEARED");
        }
        else if (keycode == Input.Keys.S) {
            saveRoom();
            notice("ROOM MASK SAVED");
        }
        else if (keycode == Input.Keys.X) {
            String json = exportJson();
            Gdx.app.getClipboard().setContents(json);
            Gdx.app.log("SceneMaskEditor", json);
            notice("MASK JSON COPIED");
        }
        return true;
    }

    @Override
    public boolean keyUp(int keycode) {
        return paintMode;
    }

    @Override
    public boolean touchDown(int screenX, int screenY, int pointer, int button) {
        if (!paintMode) return false;
        int[] p = point(screenX, screenY);
        if (p == null) return true;
        rightErase = (button == Input.Buttons.RIGHT);
        paint(p[0], p[1], rightErase);
        return true;
    }

    @Override
    public boolean touchDragged(int screenX, int screenY, int pointer) {
        if (!paintMode) return false;
        int[] p = point(screenX, screenY);
        if (p != null) paint(p[0], p[1], rightErase);
        return true;
    }

    @Override
    public boolean touchUp(int screenX, int screenY, int pointer, int button) {
        if (!paintMode) return false;
        rightErase = false;
        saveRoom();
        return true;
    }

    public String exportJson() {
        ensureRoom();
        return "{\"room\":" + room
                + ",\"width\":160,\"height\":168"
                + ",\"occluder\":\"" + encode(masks[OCCLUDER]) + "\""
                + ",\"collision\":\"" + encode(masks[COLLISION]) + "\""
                + ",\"behind\":\"" + encode(masks[BEHIND]) + "\"}";
    }

    private void drawMaskRuns(SpriteBatch batch, boolean[][] mask, Color color) {
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

    private void drawForegroundRuns(SpriteBatch batch, Texture background) {
        if (!data.getSceneMaskOccluderActive()) return;
        int sw = background.getWidth();
        int sh = background.getHeight();
        batch.setColor(Color.WHITE);
        boolean[][] mask = masks[OCCLUDER];
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
                int sx = Math.max(0, Math.min(sw - 1, (int)Math.floor(start * (sw / 160.0))));
                int sx2 = Math.max(sx + 1, Math.min(sw, (int)Math.ceil(end * (sw / 160.0))));
                int sy = Math.max(0, Math.min(sh - 1, (int)Math.floor(y * (sh / 168.0))));
                int sy2 = Math.max(sy + 1, Math.min(sh, (int)Math.ceil((y + 1) * (sh / 168.0))));
                batch.draw(background, dx, dy, dw, 1.0f,
                        sx, sy, sx2 - sx, sy2 - sy, false, false);
            }
        }
    }

    public void render(SpriteBatch batch) {
        ensureRoom();
        if (!data.getSceneMaskEnabled() && !paintMode) return;

        Texture background = RoomBackgrounds.getTexture(room);
        batch.enableBlending();
        batch.begin();

        // Runtime result first: actual room pixels are redrawn over Graham wherever
        // the red occluder mask is active and his feet are in the green behind-zone.
        if (background != null && data.getSceneMaskEnabled()) {
            drawForegroundRuns(batch, background);
        }

        if (paintMode) {
            drawMaskRuns(batch, masks[OCCLUDER], new Color(1f, 0.12f, 0.08f, 0.45f));
            drawMaskRuns(batch, masks[COLLISION], new Color(0.08f, 0.35f, 1f, 0.50f));
            drawMaskRuns(batch, masks[BEHIND], new Color(0.10f, 1f, 0.25f, 0.35f));

            batch.setColor(0f, 0f, 0f, 0.78f);
            batch.draw(white, 2, 174, 260, 24);
            batch.setColor(Color.WHITE);
            String modeName = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : mode == BEHIND ? "BEHIND" : "ERASE";
            font.draw(batch, "MASK PAINT  room " + room + "  mode=" + modeName + "  brush=" + brush,
                    6, 195);
            font.draw(batch, "M test | 1 front | 2 block | 3 behind | E erase | [ ] size | C clear | X copy",
                    6, 184);
        }

        if (System.currentTimeMillis() < noticeUntil) {
            batch.setColor(0f, 0f, 0f, 0.75f);
            batch.draw(white, 72, 101, 120, 18);
            batch.setColor(Color.WHITE);
            font.draw(batch, notice, 78, 114);
        }
        batch.setColor(Color.WHITE);
        batch.end();
    }
}
''')

# ---------------------------------------------------------------------------
# 4) Hook editor into GameScreen input, coordinates and render order.
# ---------------------------------------------------------------------------
game_screen = root / 'core/src/main/java/com/agifans/agile/GameScreen.java'
text = game_screen.read_text()

# Import Vector2 for screen -> picture coordinates.
if 'import com.badlogic.gdx.math.Vector2;\n' not in text:
    import_anchor = 'import com.badlogic.gdx.graphics.g2d.SpriteBatch;\n'
    if text.count(import_anchor) != 1:
        raise RuntimeError('GameScreen SpriteBatch import marker not found')
    text = text.replace(import_anchor, import_anchor + 'import com.badlogic.gdx.math.Vector2;\n')

field_anchor = '    private GameScreenInputProcessor gameScreenInputProcessor;\n'
if text.count(field_anchor) != 1:
    raise RuntimeError('GameScreen input processor field marker not found')
text = text.replace(field_anchor,
                    field_anchor + '    private SceneMaskEditor sceneMaskEditor;\n')

input_block = '''        gameScreenInputProcessor = new GameScreenInputProcessor(this, dialogHandler);
        portraitInputProcessor = new InputMultiplexer();
        portraitInputProcessor.addProcessor(agileRunner.userInput);
'''
input_repl = '''        gameScreenInputProcessor = new GameScreenInputProcessor(this, dialogHandler);
        sceneMaskEditor = new SceneMaskEditor(this);
        portraitInputProcessor = new InputMultiplexer();
        portraitInputProcessor.addProcessor(sceneMaskEditor);
        portraitInputProcessor.addProcessor(agileRunner.userInput);
'''
if text.count(input_block) != 1:
    raise RuntimeError('GameScreen portrait input setup marker not found')
text = text.replace(input_block, input_repl)

landscape = '''        landscapeInputProcessor = new InputMultiplexer();
        landscapeInputProcessor.addProcessor(agileRunner.userInput);
'''
landscape_repl = '''        landscapeInputProcessor = new InputMultiplexer();
        landscapeInputProcessor.addProcessor(sceneMaskEditor);
        landscapeInputProcessor.addProcessor(agileRunner.userInput);
'''
if text.count(landscape) != 1:
    raise RuntimeError('GameScreen landscape input setup marker not found')
text = text.replace(landscape, landscape_repl)

# Exact mapping from browser screen coordinates into the 160x168 AGI picture plane.
method_anchor = '''    public Texture getDrawScreen() {
        return screens[drawScreen];
    }
'''
method_repl = '''    public Texture getDrawScreen() {
        return screens[drawScreen];
    }

    /** Returns {x,y} in the 160x168 AGI picture plane, or null outside it. */
    public int[] sceneMaskPoint(int screenX, int screenY) {
        Vector2 point = new Vector2(screenX, screenY);
        viewport.unproject(point);
        if (point.x < 0 || point.x >= ADJUSTED_WIDTH || point.y < 24 || point.y >= 192) {
            return null;
        }
        int x = Math.max(0, Math.min(159, (int)(point.x * 160f / ADJUSTED_WIDTH)));
        int y = Math.max(0, Math.min(167, 167 - (int)(point.y - 24f)));
        return new int[] { x, y };
    }
'''
if text.count(method_anchor) != 1:
    raise RuntimeError('GameScreen getDrawScreen method marker not found')
text = text.replace(method_anchor, method_repl)

# Dispose editor resources.
dispose_anchor = '        fullScreenIcon.dispose();\n        batch.dispose();\n'
if text.count(dispose_anchor) != 1:
    raise RuntimeError('GameScreen dispose marker not found')
text = text.replace(dispose_anchor,
                    '        fullScreenIcon.dispose();\n        sceneMaskEditor.dispose();\n        batch.dispose();\n')

# Suppress the old hard-coded Room 1 tree overlay while live editor masks own room.
old_overlay_cond = 'if ((roomOverlay != null) && agileRunner.getVariableData().getModernRoomOverlay()) {'
if text.count(old_overlay_cond) != 1:
    raise RuntimeError('GameScreen static Room 1 overlay condition not found')
text = text.replace(old_overlay_cond,
                    'if ((roomOverlay != null) && agileRunner.getVariableData().getModernRoomOverlay()\n                && !agileRunner.getVariableData().getSceneMaskEnabled()) {')

ui_marker = '        // Now render the UI elements, e.g. the keyboard, full screen, and joystick icons.\n'
if text.count(ui_marker) != 1:
    raise RuntimeError('GameScreen UI render marker not found')
text = text.replace(ui_marker,
                    '        // Live scene-mask authoring/runtime overlay.\n        sceneMaskEditor.render(batch);\n\n' + ui_marker)
game_screen.write_text(text)

print('Live Scene Mask Editor installed: M paint/test, 1 front, 2 block, 3 behind, X export JSON')
