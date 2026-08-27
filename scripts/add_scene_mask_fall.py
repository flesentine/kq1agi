#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scene_mask_fall.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# ---------------------------------------------------------------------------
# Add a fifth editable mask plane for FALL / AGI special control colour 2.
#
# KQ1 already reacts to control colour 2 through the standard HITSPEC flag.
# Painting FALL therefore uses the original room logic for cliffs, drops and
# other special danger triggers instead of inventing a parallel death system.
# Until FALL is edited in a room, its original control-colour-2 pixels remain
# authoritative, exactly like WATER behaves before its first custom edit.
# ---------------------------------------------------------------------------

# 1) Shared metadata hook.
variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
text = variable_data.read_text()
anchor = '''    default boolean getSceneMaskWaterActive() { return false; }\n    default void setSceneMaskWaterActive(boolean value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n'''
repl = '''    default boolean getSceneMaskWaterActive() { return false; }\n    default void setSceneMaskWaterActive(boolean value) { }\n    default boolean getSceneMaskFallActive() { return false; }\n    default void setSceneMaskFallActive(boolean value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n'''
if text.count(anchor) != 1:
    raise RuntimeError('VariableData WATER metadata anchor not found')
variable_data.write_text(text.replace(anchor, repl, 1))

# 2) Browser SharedArrayBuffer transport.
# Keep the existing four mask planes and sprite-move tables at their current
# indices so debug metadata and RESET SPRITE remain backwards compatible.
# FALL gets a separate metadata word and bit-plane appended after those tables.
gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()

layers_old = '    private static final int SCENE_MASK_LAYERS = 4;\n'
layers_new = '''    private static final int SCENE_MASK_LAYERS = 5;\n'''
if text.count(layers_old) != 1:
    raise RuntimeError('GwtVariableData 4-layer mask constant not found')
text = text.replace(layers_old, layers_new, 1)

move_tail = '''    private static final int SCENE_VISUAL_OFFSET_FIELDS = 5;\n'''
move_tail_repl = '''    private static final int SCENE_VISUAL_OFFSET_FIELDS = 5;\n\n    // Appended rather than inserted so the already-published sprite debug table\n    // stays at indices 3981/3982 for the browser RESET SPRITE safety control.\n    private static final int SCENE_MASK_FALL_ACTIVE = 4142;\n    private static final int SCENE_MASK_FALL_BITS = 4143;\n'''
if text.count(move_tail) != 1:
    raise RuntimeError('GwtVariableData visual-offset constant tail not found')
text = text.replace(move_tail, move_tail_repl, 1)

capacity = 'Defines.NUMVARS + Defines.NUMFLAGS + 3630'
if text.count(capacity) != 2:
    raise RuntimeError('GwtVariableData final capacity markers not found')
text = text.replace(capacity, 'Defines.NUMVARS + Defines.NUMFLAGS + 4471')

water_methods = '''    @Override\n    public void setSceneMaskWaterActive(boolean value) {\n        variableArray.set(SCENE_MASK_WATER_ACTIVE, value ? TRUE : FALSE);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
water_methods_repl = '''    @Override\n    public void setSceneMaskWaterActive(boolean value) {\n        variableArray.set(SCENE_MASK_WATER_ACTIVE, value ? TRUE : FALSE);\n    }\n\n    @Override\n    public boolean getSceneMaskFallActive() {\n        return variableArray.get(SCENE_MASK_FALL_ACTIVE) == TRUE;\n    }\n\n    @Override\n    public void setSceneMaskFallActive(boolean value) {\n        variableArray.set(SCENE_MASK_FALL_ACTIVE, value ? TRUE : FALSE);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
if text.count(water_methods) != 1:
    raise RuntimeError('GwtVariableData WATER methods anchor not found')
text = text.replace(water_methods, water_methods_repl, 1)

index_old = '''        int bitIndex = (y * SCENE_MASK_WIDTH) + x;\n        return SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS) + (bitIndex >>> 5);\n'''
index_new = '''        int bitIndex = (y * SCENE_MASK_WIDTH) + x;\n        int base = (layer == 4)\n                ? SCENE_MASK_FALL_BITS\n                : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);\n        return base + (bitIndex >>> 5);\n'''
if text.count(index_old) != 1:
    raise RuntimeError('GwtVariableData sceneMaskIndex formula not found')
text = text.replace(index_old, index_new, 1)

clear_old = '        int start = SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);\n'
clear_new = '''        int start = (layer == 4)\n                ? SCENE_MASK_FALL_BITS\n                : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);\n'''
if text.count(clear_old) != 1:
    raise RuntimeError('GwtVariableData clearSceneMaskLayer start not found')
text = text.replace(clear_old, clear_new, 1)
gwt.write_text(text)

# 3) Runtime semantics. FALL becomes AGI priority/control colour 2, which drives
# the interpreter's existing HITSPEC flag. If FALL and WATER overlap, FALL wins.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
water_const = '    public static final int WATER = 3;\n'
if text.count(water_const) != 1:
    raise RuntimeError('SceneMaskRuntime WATER constant not found')
text = text.replace(water_const, water_const + '    public static final int FALL = 4;\n', 1)

control_old = '''    public static int effectiveControlPriority(GameState state, int objectNumber,\n            int x, int y, int legacyPriority) {\n        VariableData data = state.getVariableData();\n        if (objectNumber != 0 || !editorOwnsRoom(state) || !data.getSceneMaskWaterActive()) {\n            return legacyPriority;\n        }\n        if (x < 0 || x >= 160 || y < 0 || y >= 168) {\n            return legacyPriority;\n        }\n        if (data.getSceneMaskBit(WATER, x, y)) {\n            return 3;\n        }\n        return legacyPriority == 3 ? 4 : legacyPriority;\n    }\n'''
control_new = '''    public static int effectiveControlPriority(GameState state, int objectNumber,\n            int x, int y, int legacyPriority) {\n        VariableData data = state.getVariableData();\n        if (objectNumber != 0 || !editorOwnsRoom(state)) {\n            return legacyPriority;\n        }\n        if (x < 0 || x >= 160 || y < 0 || y >= 168) {\n            return legacyPriority;\n        }\n\n        boolean fallActive = data.getSceneMaskFallActive();\n        boolean waterActive = data.getSceneMaskWaterActive();\n        if (!fallActive && !waterActive) return legacyPriority;\n\n        // Special/fall wins an accidental overlap because it is the dangerous\n        // control and KQ1 room logic expects HITSPEC to fire immediately.\n        if (fallActive && data.getSceneMaskBit(FALL, x, y)) return 2;\n        if (waterActive && data.getSceneMaskBit(WATER, x, y)) return 3;\n\n        // Once a custom plane is edited, that plane becomes authoritative and\n        // replaces only the matching legacy control colour outside the new mask.\n        if (fallActive && legacyPriority == 2) legacyPriority = 4;\n        if (waterActive && legacyPriority == 3) legacyPriority = 4;\n        return legacyPriority;\n    }\n'''
if text.count(control_old) != 1:
    raise RuntimeError('SceneMaskRuntime WATER effectiveControlPriority method not found')
text = text.replace(control_old, control_new, 1)
runtime.write_text(text)

# 4) SceneMaskEditor: persistence, authoring, overlay and keyboard controls.
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

const = '    private static final int WATER = 3;\n'
if text.count(const) != 1:
    raise RuntimeError('SceneMaskEditor WATER constant not found')
text = text.replace(const, const + '    private static final int FALL = 4;\n', 1)

mask_field = '    private final boolean[][][] masks = new boolean[4][HEIGHT][WIDTH];\n'
if text.count(mask_field) != 1:
    raise RuntimeError('SceneMaskEditor four-layer mask array not found')
text = text.replace(mask_field, '    private final boolean[][][] masks = new boolean[5][HEIGHT][WIDTH];\n', 1)

visible_field = '    private final boolean[] layerVisible = new boolean[] { true, true, true, true };\n'
if text.count(visible_field) != 1:
    raise RuntimeError('SceneMaskEditor four-layer visibility array not found')
text = text.replace(visible_field,
                    '    private final boolean[] layerVisible = new boolean[] { true, true, true, true, true };\n', 1)

water_field = '''    private boolean waterActive;\n    private boolean moveMode;\n'''
water_field_repl = '''    private boolean waterActive;\n    private boolean fallActive;\n    private boolean moveMode;\n'''
if text.count(water_field) != 1:
    raise RuntimeError('SceneMaskEditor WATER/move field anchor not found')
text = text.replace(water_field, water_field_repl, 1)

loop_old = '        for (int layer = 0; layer < 4; layer++) {\n'
loop_count = text.count(loop_old)
if loop_count != 2:
    raise RuntimeError(f'SceneMaskEditor expected two four-layer loops, found {loop_count}')
text = text.replace(loop_old, '        for (int layer = 0; layer < 5; layer++) {\n')

saved_water = '        String savedWater = prefs.getString(key("water"), "");\n'
if text.count(saved_water) != 1:
    raise RuntimeError('SceneMaskEditor saved WATER line not found')
text = text.replace(saved_water,
                    saved_water + '        String savedFall = prefs.getString(key("fall"), "");\n', 1)

load_water = '''        decode(savedWater, masks[WATER]);\n        waterActive = prefs.getBoolean(key("waterActive"), false);\n        data.setSceneMaskWaterActive(waterActive);\n        data.setSceneMaskRoom(room);\n'''
load_fall = '''        decode(savedWater, masks[WATER]);\n        waterActive = prefs.getBoolean(key("waterActive"), false);\n        data.setSceneMaskWaterActive(waterActive);\n        decode(savedFall, masks[FALL]);\n        fallActive = prefs.getBoolean(key("fallActive"), false);\n        data.setSceneMaskFallActive(fallActive);\n        data.setSceneMaskRoom(room);\n'''
if text.count(load_water) != 1:
    raise RuntimeError('SceneMaskEditor WATER room-load tail not found')
text = text.replace(load_water, load_fall, 1)

sync_water = '        data.setSceneMaskWaterActive(waterActive);\n'
# One occurrence is in loadRoom above and has already been replaced; the remaining
# occurrence is syncAll().
if text.count(sync_water) != 1:
    raise RuntimeError('SceneMaskEditor syncAll WATER metadata line not found')
text = text.replace(sync_water,
                    '        data.setSceneMaskWaterActive(waterActive);\n        data.setSceneMaskFallActive(fallActive);\n', 1)

save_water = '''        prefs.putString(key("water"), encode(masks[WATER]));\n        prefs.putBoolean(key("waterActive"), waterActive);\n        prefs.putBoolean(key("active"), data.getSceneMaskEnabled());\n'''
save_fall = '''        prefs.putString(key("water"), encode(masks[WATER]));\n        prefs.putBoolean(key("waterActive"), waterActive);\n        prefs.putString(key("fall"), encode(masks[FALL]));\n        prefs.putBoolean(key("fallActive"), fallActive);\n        prefs.putBoolean(key("active"), data.getSceneMaskEnabled());\n'''
if text.count(save_water) != 1:
    raise RuntimeError('SceneMaskEditor save WATER block not found')
text = text.replace(save_water, save_fall, 1)

activate_water = '''    private void activateWaterMask() {\n        waterActive = true;\n        data.setSceneMaskWaterActive(true);\n    }\n\n'''
activate_both = '''    private void activateWaterMask() {\n        waterActive = true;\n        data.setSceneMaskWaterActive(true);\n    }\n\n    private void activateFallMask() {\n        fallActive = true;\n        data.setSceneMaskFallActive(true);\n    }\n\n'''
if text.count(activate_water) != 1:
    raise RuntimeError('SceneMaskEditor activateWaterMask method not found')
text = text.replace(activate_water, activate_both, 1)

paint_water = '        if (mode == WATER) activateWaterMask();\n'
if text.count(paint_water) != 2:
    raise RuntimeError('SceneMaskEditor expected WATER activation in paint+morph')
text = text.replace(paint_water,
                    '        if (mode == WATER) activateWaterMask();\n        if (mode == FALL) activateFallMask();\n')

move_key = '''        else if (keycode == Input.Keys.NUM_5) {\n            moveMode = true;\n'''
move_key_repl = '''        else if (keycode == Input.Keys.NUM_5) { moveMode = false; mode = FALL; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }\n        else if (keycode == Input.Keys.NUM_6) {\n            moveMode = true;\n'''
if text.count(move_key) != 1:
    raise RuntimeError('SceneMaskEditor MOVE key 5 block not found')
text = text.replace(move_key, move_key_repl, 1)

visible_water = '        if (keycode == Input.Keys.W) { toggleLayerVisible(WATER, "WATER"); return true; }\n'
if text.count(visible_water) != 1:
    raise RuntimeError('SceneMaskEditor WATER visibility key not found')
text = text.replace(visible_water,
                    visible_water + '        if (keycode == Input.Keys.V) { toggleLayerVisible(FALL, "FALL"); return true; }\n', 1)

clear_water = '            if (layer == WATER) activateWaterMask();\n'
if text.count(clear_water) != 1:
    raise RuntimeError('SceneMaskEditor clear WATER activation not found')
text = text.replace(clear_water,
                    clear_water + '            if (layer == FALL) activateFallMask();\n', 1)

export_water = '''                + ",\\\"water\\\":\\\"" + encode(masks[WATER]) + "\\\""\n                + ",\\\"waterActive\\\":" + waterActive + "}";\n'''
export_fall = '''                + ",\\\"water\\\":\\\"" + encode(masks[WATER]) + "\\\""\n                + ",\\\"waterActive\\\":" + waterActive\n                + ",\\\"fall\\\":\\\"" + encode(masks[FALL]) + "\\\""\n                + ",\\\"fallActive\\\":" + fallActive + "}";\n'''
if text.count(export_water) != 1:
    raise RuntimeError('SceneMaskEditor WATER export tail not found')
text = text.replace(export_water, export_fall, 1)

render_water = '                if (layerVisible[WATER]) drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.42f));\n'
if text.count(render_water) != 1:
    raise RuntimeError('SceneMaskEditor WATER overlay render line not found')
text = text.replace(render_water,
                    render_water + '                if (layerVisible[FALL]) drawMaskRuns(batch, masks[FALL], new Color(1f, 0.08f, 0.62f, 0.52f));\n', 1)

mode_name = '            String baseMode = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : mode == BEHIND ? "BEHIND" : "WATER";\n'
mode_name_repl = '            String baseMode = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : mode == BEHIND ? "BEHIND" : mode == WATER ? "WATER" : "FALL";\n'
if text.count(mode_name) != 1:
    raise RuntimeError('SceneMaskEditor mode-name expression not found')
text = text.replace(mode_name, mode_name_repl, 1)

hud_old = '                            : "1 front 2 block 3 behind 4 water 5 MOVE | Shift-line | Option erase | R/G/B/W hide",\n'
hud_new = '                            : "1 front 2 block 3 behind 4 water 5 FALL 6 MOVE | V hide fall | Shift-line | Option erase",\n'
if text.count(hud_old) != 1:
    raise RuntimeError('SceneMaskEditor paint HUD line not found')
text = text.replace(hud_old, hud_new, 1)

# Keep the class documentation useful for anyone debugging from the source.
text = text.replace('1=foreground/occluder, 2=collision, 3=behind-zone,',
                    '1=foreground/occluder, 2=collision, 3=behind-zone, 4=water, 5=fall/special,')

editor.write_text(text)
print('FALL mask installed: 5 paints AGI special/HITSPEC danger, 6 moves sprites, magenta overlay persisted per room')
