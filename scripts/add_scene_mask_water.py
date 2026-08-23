#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scene_mask_water.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# ---------------------------------------------------------------------------
# Shared transport: add a fourth 160x168 plane for WATER, plus two metadata
# booleans. WATER_ACTIVE means the painted mask overrides Sierra control color 3.
# WATER_SEEDED means the worker has copied the room's original water controls into
# the shared plane so the editor can start from the existing shoreline.
# ---------------------------------------------------------------------------
variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
text = variable_data.read_text()
anchor = '''    default boolean getSceneMaskPaintMode() { return false; }
    default void setSceneMaskPaintMode(boolean value) { }
    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }
'''
repl = '''    default boolean getSceneMaskPaintMode() { return false; }
    default void setSceneMaskPaintMode(boolean value) { }
    default boolean getSceneMaskWaterActive() { return false; }
    default void setSceneMaskWaterActive(boolean value) { }
    default boolean getSceneMaskWaterSeeded() { return false; }
    default void setSceneMaskWaterSeeded(boolean value) { }
    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }
'''
if text.count(anchor) != 1:
    raise RuntimeError('VariableData scene-mask metadata anchor not found')
variable_data.write_text(text.replace(anchor, repl))

gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()
const_anchor = '''    private static final int SCENE_MASK_PAINT_MODE = 522;
    private static final int SCENE_MASK_BITS = 523;
    private static final int SCENE_MASK_WIDTH = 160;
    private static final int SCENE_MASK_HEIGHT = 168;
    private static final int SCENE_MASK_WORDS = ((SCENE_MASK_WIDTH * SCENE_MASK_HEIGHT) + 31) / 32;
    private static final int SCENE_MASK_LAYERS = 3;
'''
const_repl = '''    private static final int SCENE_MASK_PAINT_MODE = 522;
    private static final int SCENE_MASK_WATER_ACTIVE = 523;
    private static final int SCENE_MASK_WATER_SEEDED = 524;
    private static final int SCENE_MASK_BITS = 525;
    private static final int SCENE_MASK_WIDTH = 160;
    private static final int SCENE_MASK_HEIGHT = 168;
    private static final int SCENE_MASK_WORDS = ((SCENE_MASK_WIDTH * SCENE_MASK_HEIGHT) + 31) / 32;
    private static final int SCENE_MASK_LAYERS = 4;
'''
if text.count(const_anchor) != 1:
    raise RuntimeError('GwtVariableData scene-mask constants not found')
text = text.replace(const_anchor, const_repl)

if text.count('Defines.NUMVARS + Defines.NUMFLAGS + 2531') != 2:
    raise RuntimeError('GwtVariableData scene-mask capacity markers not found')
text = text.replace('Defines.NUMVARS + Defines.NUMFLAGS + 2531',
                    'Defines.NUMVARS + Defines.NUMFLAGS + 3373')

method_anchor = '''    @Override
    public void setSceneMaskPaintMode(boolean value) {
        variableArray.set(SCENE_MASK_PAINT_MODE, value ? TRUE : FALSE);
    }

    private int sceneMaskIndex(int layer, int x, int y) {
'''
method_repl = '''    @Override
    public void setSceneMaskPaintMode(boolean value) {
        variableArray.set(SCENE_MASK_PAINT_MODE, value ? TRUE : FALSE);
    }

    @Override
    public boolean getSceneMaskWaterActive() {
        return variableArray.get(SCENE_MASK_WATER_ACTIVE) == TRUE;
    }

    @Override
    public void setSceneMaskWaterActive(boolean value) {
        variableArray.set(SCENE_MASK_WATER_ACTIVE, value ? TRUE : FALSE);
    }

    @Override
    public boolean getSceneMaskWaterSeeded() {
        return variableArray.get(SCENE_MASK_WATER_SEEDED) == TRUE;
    }

    @Override
    public void setSceneMaskWaterSeeded(boolean value) {
        variableArray.set(SCENE_MASK_WATER_SEEDED, value ? TRUE : FALSE);
    }

    private int sceneMaskIndex(int layer, int x, int y) {
'''
if text.count(method_anchor) != 1:
    raise RuntimeError('GwtVariableData scene-mask paint-mode methods not found')
gwt.write_text(text.replace(method_anchor, method_repl))

# ---------------------------------------------------------------------------
# Worker semantics. Until WATER is edited, copy the original AGI control-color-3
# area into the shared cyan layer as a preview. Once edited, the painted layer is
# authoritative for ego's on.water test.
# ---------------------------------------------------------------------------
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
const = '    public static final int BEHIND = 2;\n'
if text.count(const) != 1:
    raise RuntimeError('SceneMaskRuntime BEHIND constant not found')
text = text.replace(const, const + '    public static final int WATER = 3;\n')

helper_anchor = '''    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
helpers = '''    public static void ensureWaterPreview(GameState state) {
        VariableData data = state.getVariableData();
        if (!editorOwnsRoom(state) || data.getSceneMaskWaterActive() || data.getSceneMaskWaterSeeded()) {
            return;
        }
        data.clearSceneMaskLayer(WATER);
        for (int y = 0; y < 168; y++) {
            for (int x = 0; x < 160; x++) {
                if (state.controlPixels[(y * 160) + x] == 3) {
                    data.setSceneMaskBit(WATER, x, y, true);
                }
            }
        }
        data.setSceneMaskWaterSeeded(true);
    }

    public static int effectiveControlPriority(GameState state, int objectNumber,
            int x, int y, int legacyPriority) {
        VariableData data = state.getVariableData();
        if (objectNumber != 0 || !editorOwnsRoom(state) || !data.getSceneMaskWaterActive()) {
            return legacyPriority;
        }
        if (x < 0 || x >= 160 || y < 0 || y >= 168) {
            return legacyPriority;
        }
        if (data.getSceneMaskBit(WATER, x, y)) {
            return 3;
        }
        // When custom water is active, old control-color-3 pixels become normal
        // passable land unless they are also painted into the WATER layer.
        return legacyPriority == 3 ? 4 : legacyPriority;
    }

    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
if text.count(helper_anchor) != 1:
    raise RuntimeError('SceneMaskRuntime movement helper anchor not found')
text = text.replace(helper_anchor, helpers)

update_anchor = '''    public static void updateOccluderFlag(GameState state) {
        VariableData data = state.getVariableData();
'''
update_repl = '''    public static void updateOccluderFlag(GameState state) {
        ensureWaterPreview(state);
        VariableData data = state.getVariableData();
'''
if text.count(update_anchor) != 1:
    raise RuntimeError('SceneMaskRuntime updateOccluderFlag anchor not found')
runtime.write_text(text.replace(update_anchor, update_repl))

# Feed the custom WATER layer into AGI's existing baseline water test. Everything
# after this line remains Sierra's normal canBeHere() logic, including ONWATER,
# stay.on.water / stay.on.land and the game's existing swimming animation logic.
animated = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
text = animated.read_text()
priority_line = '                int priority = state.controlPixels[pixelPos];\n'
priority_repl = '''                int priority = SceneMaskRuntime.effectiveControlPriority(
                        state, this.objectNumber, pixelPos % 160, y, state.controlPixels[pixelPos]);
'''
if text.count(priority_line) != 1:
    raise RuntimeError('AnimatedObject baseline control-pixel read not found')
animated.write_text(text.replace(priority_line, priority_repl))

# ---------------------------------------------------------------------------
# Editor UI/persistence: 4 selects WATER, cyan overlay, W toggles visibility.
# The first time WATER is edited it starts from the original Sierra water area.
# ---------------------------------------------------------------------------
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

const = '    private static final int BEHIND = 2;\n'
if text.count(const) != 1:
    raise RuntimeError('SceneMaskEditor BEHIND constant not found')
text = text.replace(const, const + '    private static final int WATER = 3;\n')

mask_field = '    private final boolean[][][] masks = new boolean[3][HEIGHT][WIDTH];\n'
if text.count(mask_field) != 1:
    raise RuntimeError('SceneMaskEditor mask array not found')
text = text.replace(mask_field, '    private final boolean[][][] masks = new boolean[4][HEIGHT][WIDTH];\n')

visible_field = '    private final boolean[] layerVisible = new boolean[] { true, true, true };\n'
if text.count(visible_field) != 1:
    raise RuntimeError('SceneMaskEditor layerVisible array not found')
text = text.replace(visible_field,
                    '    private final boolean[] layerVisible = new boolean[] { true, true, true, true };\n')

line_fields = '''    private int lineAnchorX = -1;
    private int lineAnchorY = -1;
'''
line_fields_repl = '''    private int lineAnchorX = -1;
    private int lineAnchorY = -1;
    private boolean waterActive;
    private boolean waterPreviewLoaded;
'''
if text.count(line_fields) != 1:
    raise RuntimeError('SceneMaskEditor line-anchor fields not found')
text = text.replace(line_fields, line_fields_repl)

room_reset = '''        lineAnchorX = -1;
        lineAnchorY = -1;
        for (int layer = 0; layer < 3; layer++) {
'''
room_reset_repl = '''        lineAnchorX = -1;
        lineAnchorY = -1;
        waterPreviewLoaded = false;
        for (int layer = 0; layer < 4; layer++) {
'''
if text.count(room_reset) != 1:
    raise RuntimeError('SceneMaskEditor room reset/load loop not found')
text = text.replace(room_reset, room_reset_repl)

load_anchor = '''        decode(prefs.getString(key("occluder"), ""), masks[OCCLUDER]);
        decode(prefs.getString(key("collision"), ""), masks[COLLISION]);
        decode(prefs.getString(key("behind"), ""), masks[BEHIND]);
        boolean active = prefs.getBoolean(key("active"), false);
'''
load_repl = '''        decode(prefs.getString(key("occluder"), ""), masks[OCCLUDER]);
        decode(prefs.getString(key("collision"), ""), masks[COLLISION]);
        decode(prefs.getString(key("behind"), ""), masks[BEHIND]);
        decode(prefs.getString(key("water"), ""), masks[WATER]);
        waterActive = prefs.getBoolean(key("waterActive"), false);
        waterPreviewLoaded = waterActive;
        boolean active = prefs.getBoolean(key("active"), false);
'''
if text.count(load_anchor) != 1:
    raise RuntimeError('SceneMaskEditor room decode block not found')
text = text.replace(load_anchor, load_repl)

save_anchor = '''        prefs.putString(key("occluder"), encode(masks[OCCLUDER]));
        prefs.putString(key("collision"), encode(masks[COLLISION]));
        prefs.putString(key("behind"), encode(masks[BEHIND]));
        prefs.putBoolean(key("active"), data.getSceneMaskEnabled());
'''
save_repl = '''        prefs.putString(key("occluder"), encode(masks[OCCLUDER]));
        prefs.putString(key("collision"), encode(masks[COLLISION]));
        prefs.putString(key("behind"), encode(masks[BEHIND]));
        prefs.putString(key("water"), encode(masks[WATER]));
        prefs.putBoolean(key("waterActive"), waterActive);
        prefs.putBoolean(key("active"), data.getSceneMaskEnabled());
'''
if text.count(save_anchor) != 1:
    raise RuntimeError('SceneMaskEditor save block not found')
text = text.replace(save_anchor, save_repl)

sync_old = '''    private void syncAll() {
        for (int layer = 0; layer < 3; layer++) {
            data.clearSceneMaskLayer(layer);
            for (int y = 0; y < HEIGHT; y++) {
                for (int x = 0; x < WIDTH; x++) {
                    if (masks[layer][y][x]) data.setSceneMaskBit(layer, x, y, true);
                }
            }
        }
    }
'''
sync_new = '''    private void refreshWaterPreview() {
        if (waterActive || waterPreviewLoaded || !data.getSceneMaskWaterSeeded()) return;
        for (int y = 0; y < HEIGHT; y++) {
            for (int x = 0; x < WIDTH; x++) {
                masks[WATER][y][x] = data.getSceneMaskBit(WATER, x, y);
            }
        }
        waterPreviewLoaded = true;
    }

    private void activateWaterMask() {
        refreshWaterPreview();
        waterActive = true;
        waterPreviewLoaded = true;
        data.setSceneMaskWaterActive(true);
        data.setSceneMaskWaterSeeded(true);
    }

    private void syncAll() {
        for (int layer = 0; layer < 4; layer++) {
            data.clearSceneMaskLayer(layer);
            if (layer == WATER && !waterActive) continue;
            for (int y = 0; y < HEIGHT; y++) {
                for (int x = 0; x < WIDTH; x++) {
                    if (masks[layer][y][x]) data.setSceneMaskBit(layer, x, y, true);
                }
            }
        }
        data.setSceneMaskWaterActive(waterActive);
        data.setSceneMaskWaterSeeded(waterActive);
    }
'''
if text.count(sync_old) != 1:
    raise RuntimeError('SceneMaskEditor syncAll method not found')
text = text.replace(sync_old, sync_new)

paint_anchor = '''    private void paint(int cx, int cy, boolean erase) {
        ensureRoom();
        erase = erase || eraser || optionEraseHeld();
        int layer = mode;
'''
paint_repl = '''    private void paint(int cx, int cy, boolean erase) {
        ensureRoom();
        if (mode == WATER) activateWaterMask();
        erase = erase || eraser || optionEraseHeld();
        int layer = mode;
'''
if text.count(paint_anchor) != 1:
    raise RuntimeError('SceneMaskEditor paint method start not found')
text = text.replace(paint_anchor, paint_repl)

morph_anchor = '''    private void morphSelectedLayer(boolean grow) {
        int layer = selectedLayer();
'''
morph_repl = '''    private void morphSelectedLayer(boolean grow) {
        int layer = selectedLayer();
        if (layer == WATER) activateWaterMask();
'''
if text.count(morph_anchor) != 1:
    raise RuntimeError('SceneMaskEditor morphSelectedLayer start not found')
text = text.replace(morph_anchor, morph_repl)

mode_keys = '''        if (keycode == Input.Keys.NUM_1) { mode = OCCLUDER; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_2) { mode = COLLISION; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_3) { mode = BEHIND; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
'''
mode_keys_repl = '''        if (keycode == Input.Keys.NUM_1) { mode = OCCLUDER; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_2) { mode = COLLISION; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_3) { mode = BEHIND; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_4) { mode = WATER; eraser = false; lineAnchorX = -1; lineAnchorY = -1; refreshWaterPreview(); }
'''
if text.count(mode_keys) != 1:
    raise RuntimeError('SceneMaskEditor fast-tool mode keys not found')
text = text.replace(mode_keys, mode_keys_repl)

visible_keys = '''        if (keycode == Input.Keys.R) { toggleLayerVisible(OCCLUDER, "RED"); return true; }
        if (keycode == Input.Keys.B) { toggleLayerVisible(COLLISION, "BLUE"); return true; }
        if (keycode == Input.Keys.G) { toggleLayerVisible(BEHIND, "GREEN"); return true; }
'''
visible_keys_repl = '''        if (keycode == Input.Keys.R) { toggleLayerVisible(OCCLUDER, "RED"); return true; }
        if (keycode == Input.Keys.B) { toggleLayerVisible(COLLISION, "BLUE"); return true; }
        if (keycode == Input.Keys.G) { toggleLayerVisible(BEHIND, "GREEN"); return true; }
        if (keycode == Input.Keys.W) { toggleLayerVisible(WATER, "WATER"); return true; }
'''
if text.count(visible_keys) != 1:
    raise RuntimeError('SceneMaskEditor visibility keys not found')
text = text.replace(visible_keys, visible_keys_repl)

clear_anchor = '''        else if (keycode == Input.Keys.C) {
            int layer = selectedLayer();
            for (int y = 0; y < HEIGHT; y++) {
'''
clear_repl = '''        else if (keycode == Input.Keys.C) {
            int layer = selectedLayer();
            if (layer == WATER) activateWaterMask();
            for (int y = 0; y < HEIGHT; y++) {
'''
if text.count(clear_anchor) != 1:
    raise RuntimeError('SceneMaskEditor clear-layer block not found')
text = text.replace(clear_anchor, clear_repl)

export_anchor = '''                + ",\\\"collision\\\":\\\"" + encode(masks[COLLISION]) + "\\\""
                + ",\\\"behind\\\":\\\"" + encode(masks[BEHIND]) + "\\\"}";
'''
export_repl = '''                + ",\\\"collision\\\":\\\"" + encode(masks[COLLISION]) + "\\\""
                + ",\\\"behind\\\":\\\"" + encode(masks[BEHIND]) + "\\\""
                + ",\\\"water\\\":\\\"" + encode(masks[WATER]) + "\\\""
                + ",\\\"waterActive\\\":" + waterActive + "}";
'''
if text.count(export_anchor) != 1:
    raise RuntimeError('SceneMaskEditor export JSON tail not found')
text = text.replace(export_anchor, export_repl)

render_anchor = '''        if (paintMode) {
            if (layerVisible[OCCLUDER]) drawMaskRuns(batch, masks[OCCLUDER], new Color(1f, 0.12f, 0.08f, 0.45f));
            if (layerVisible[COLLISION]) drawMaskRuns(batch, masks[COLLISION], new Color(0.08f, 0.35f, 1f, 0.50f));
            if (layerVisible[BEHIND]) drawMaskRuns(batch, masks[BEHIND], new Color(0.10f, 1f, 0.25f, 0.35f));
'''
render_repl = '''        if (paintMode) {
            if (mode == WATER) refreshWaterPreview();
            if (layerVisible[OCCLUDER]) drawMaskRuns(batch, masks[OCCLUDER], new Color(1f, 0.12f, 0.08f, 0.45f));
            if (layerVisible[COLLISION]) drawMaskRuns(batch, masks[COLLISION], new Color(0.08f, 0.35f, 1f, 0.50f));
            if (layerVisible[BEHIND]) drawMaskRuns(batch, masks[BEHIND], new Color(0.10f, 1f, 0.25f, 0.35f));
            if (layerVisible[WATER]) drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.42f));
'''
if text.count(render_anchor) != 1:
    raise RuntimeError('SceneMaskEditor fast-tool render block not found')
text = text.replace(render_anchor, render_repl)

mode_name = '            String baseMode = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : "BEHIND";\n'
mode_name_repl = '            String baseMode = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : mode == BEHIND ? "BEHIND" : "WATER";\n'
if text.count(mode_name) != 1:
    raise RuntimeError('SceneMaskEditor mode-name line not found')
text = text.replace(mode_name, mode_name_repl)

hud = '''            font.draw(batch, "Shift-click line | Option erase | +/- grow/shrink | R/G/B hide | SPACE+DRAG pan",
                    6, 184);
'''
hud_repl = '''            font.draw(batch, "1 front 2 block 3 behind 4 water | Shift-line | Option erase | R/G/B/W hide",
                    6, 184);
'''
if text.count(hud) != 1:
    raise RuntimeError('SceneMaskEditor fast-tool HUD line not found')
text = text.replace(hud, hud_repl)

editor.write_text(text)
print('Editable WATER mask installed: 4=water, cyan preview, W visibility, original shoreline imported until first edit')
