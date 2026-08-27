#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scene_mask_fall.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# Add a fifth editable mask plane for FALL / AGI special control colour 2.
# KQ1 already turns control colour 2 into HITSPEC, so the painted mask feeds the
# original room logic instead of inventing a second fall/death system.

# ---------------------------------------------------------------------------
# 1) Shared metadata.
# ---------------------------------------------------------------------------
variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
text = variable_data.read_text()
old = '''    default boolean getSceneMaskWaterActive() { return false; }\n    default void setSceneMaskWaterActive(boolean value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n'''
new = '''    default boolean getSceneMaskWaterActive() { return false; }\n    default void setSceneMaskWaterActive(boolean value) { }\n    default boolean getSceneMaskFallActive() { return false; }\n    default void setSceneMaskFallActive(boolean value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n'''
if text.count(old) != 1:
    raise RuntimeError('VariableData WATER metadata anchor not found')
variable_data.write_text(text.replace(old, new, 1))

# ---------------------------------------------------------------------------
# 2) GWT SharedArrayBuffer transport.
#
# Do NOT insert the new plane before the sprite tables: browser RESET SPRITE and
# debug metadata intentionally use their established indices 3981/3982. Append
# FALL after the visual-offset table instead.
# ---------------------------------------------------------------------------
gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()

old = '    private static final int SCENE_MASK_LAYERS = 4;\n'
new = '    private static final int SCENE_MASK_LAYERS = 5;\n'
if text.count(old) != 1:
    raise RuntimeError('GwtVariableData four-layer constant not found')
text = text.replace(old, new, 1)

old = '    private static final int SCENE_VISUAL_OFFSET_FIELDS = 5;\n'
new = '''    private static final int SCENE_VISUAL_OFFSET_FIELDS = 5;\n\n    // Appended so existing browser debug table offsets remain stable.\n    private static final int SCENE_MASK_FALL_ACTIVE = 4142;\n    private static final int SCENE_MASK_FALL_BITS = 4143;\n'''
if text.count(old) != 1:
    raise RuntimeError('GwtVariableData visual-offset constant tail not found')
text = text.replace(old, new, 1)

capacity = 'Defines.NUMVARS + Defines.NUMFLAGS + 3630'
if text.count(capacity) != 2:
    raise RuntimeError('GwtVariableData final capacity markers not found')
text = text.replace(capacity, 'Defines.NUMVARS + Defines.NUMFLAGS + 4471')

old = '''    @Override\n    public void setSceneMaskWaterActive(boolean value) {\n        variableArray.set(SCENE_MASK_WATER_ACTIVE, value ? TRUE : FALSE);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
new = '''    @Override\n    public void setSceneMaskWaterActive(boolean value) {\n        variableArray.set(SCENE_MASK_WATER_ACTIVE, value ? TRUE : FALSE);\n    }\n\n    @Override\n    public boolean getSceneMaskFallActive() {\n        return variableArray.get(SCENE_MASK_FALL_ACTIVE) == TRUE;\n    }\n\n    @Override\n    public void setSceneMaskFallActive(boolean value) {\n        variableArray.set(SCENE_MASK_FALL_ACTIVE, value ? TRUE : FALSE);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
if text.count(old) != 1:
    raise RuntimeError('GwtVariableData WATER method anchor not found')
text = text.replace(old, new, 1)

old = '''        int bitIndex = (y * SCENE_MASK_WIDTH) + x;\n        return SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS) + (bitIndex >>> 5);\n'''
new = '''        int bitIndex = (y * SCENE_MASK_WIDTH) + x;\n        int base = (layer == 4)\n                ? SCENE_MASK_FALL_BITS\n                : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);\n        return base + (bitIndex >>> 5);\n'''
if text.count(old) != 1:
    raise RuntimeError('GwtVariableData sceneMaskIndex formula not found')
text = text.replace(old, new, 1)

old = '        int start = SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);\n'
new = '''        int start = (layer == 4)\n                ? SCENE_MASK_FALL_BITS\n                : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);\n'''
if text.count(old) != 1:
    raise RuntimeError('GwtVariableData clearSceneMaskLayer start not found')
text = text.replace(old, new, 1)
gwt.write_text(text)

# ---------------------------------------------------------------------------
# 3) Runtime semantics: painted FALL synthesizes control colour 2 / HITSPEC.
# FALL wins an accidental FALL+WATER overlap. Before either custom plane has been
# edited, the original AGI special/water controls remain untouched.
# ---------------------------------------------------------------------------
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
old = '    public static final int WATER = 3;\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskRuntime WATER constant not found')
text = text.replace(old, old + '    public static final int FALL = 4;\n', 1)

old = '''    public static int effectiveControlPriority(GameState state, int objectNumber,\n            int x, int y, int legacyPriority) {\n        VariableData data = state.getVariableData();\n        if (objectNumber != 0 || !editorOwnsRoom(state) || !data.getSceneMaskWaterActive()) {\n            return legacyPriority;\n        }\n        if (x < 0 || x >= 160 || y < 0 || y >= 168) {\n            return legacyPriority;\n        }\n        if (data.getSceneMaskBit(WATER, x, y)) {\n            return 3;\n        }\n        return legacyPriority == 3 ? 4 : legacyPriority;\n    }\n'''
new = '''    public static int effectiveControlPriority(GameState state, int objectNumber,\n            int x, int y, int legacyPriority) {\n        VariableData data = state.getVariableData();\n        if (objectNumber != 0 || !editorOwnsRoom(state)) return legacyPriority;\n        if (x < 0 || x >= 160 || y < 0 || y >= 168) return legacyPriority;\n\n        boolean fallActive = data.getSceneMaskFallActive();\n        boolean waterActive = data.getSceneMaskWaterActive();\n        if (!fallActive && !waterActive) return legacyPriority;\n\n        // Special/fall is the more dangerous control, so it wins overlaps.\n        if (fallActive && data.getSceneMaskBit(FALL, x, y)) return 2;\n        if (waterActive && data.getSceneMaskBit(WATER, x, y)) return 3;\n\n        // An edited custom plane replaces only its corresponding legacy colour.\n        if (fallActive && legacyPriority == 2) legacyPriority = 4;\n        if (waterActive && legacyPriority == 3) legacyPriority = 4;\n        return legacyPriority;\n    }\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskRuntime WATER effectiveControlPriority method not found')
runtime.write_text(text.replace(old, new, 1))

# ---------------------------------------------------------------------------
# 4) Editor authoring, persistence and overlay.
# ---------------------------------------------------------------------------
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

old = '    private static final int WATER = 3;\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor WATER constant not found')
text = text.replace(old, old + '    private static final int FALL = 4;\n', 1)

old = '    private final boolean[][][] masks = new boolean[4][HEIGHT][WIDTH];\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor four-layer mask array not found')
text = text.replace(old, '    private final boolean[][][] masks = new boolean[5][HEIGHT][WIDTH];\n', 1)

old = '    private final boolean[] layerVisible = new boolean[] { true, true, true, true };\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor four-layer visibility array not found')
text = text.replace(old,
                    '    private final boolean[] layerVisible = new boolean[] { true, true, true, true, true };\n', 1)

old = '''    private boolean waterActive;\n    private boolean moveMode;\n'''
new = '''    private boolean waterActive;\n    private boolean fallActive;\n    private boolean moveMode;\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor WATER/move fields not found')
text = text.replace(old, new, 1)

old = '        for (int layer = 0; layer < 4; layer++) {\n'
if text.count(old) != 2:
    raise RuntimeError('SceneMaskEditor expected two four-layer loops')
text = text.replace(old, '        for (int layer = 0; layer < 5; layer++) {\n')

old = '        String savedWater = prefs.getString(key("water"), "");\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor saved WATER line not found')
text = text.replace(old, old + '        String savedFall = prefs.getString(key("fall"), "");\n', 1)

old = '''        decode(savedWater, masks[WATER]);\n        waterActive = prefs.getBoolean(key("waterActive"), false);\n        data.setSceneMaskWaterActive(waterActive);\n        data.setSceneMaskRoom(room);\n'''
new = '''        decode(savedWater, masks[WATER]);\n        waterActive = prefs.getBoolean(key("waterActive"), false);\n        data.setSceneMaskWaterActive(waterActive);\n        decode(savedFall, masks[FALL]);\n        fallActive = prefs.getBoolean(key("fallActive"), false);\n        data.setSceneMaskFallActive(fallActive);\n        data.setSceneMaskRoom(room);\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor WATER load block not found')
text = text.replace(old, new, 1)

# syncAll has a second WATER metadata write. Locate it by method so the WATER
# write retained in loadRoom above is not accidentally patched twice.
sync_start = text.index('    private void syncAll() {')
sync_marker = '        data.setSceneMaskWaterActive(waterActive);\n'
sync_pos = text.index(sync_marker, sync_start)
text = (text[:sync_pos]
        + sync_marker
        + '        data.setSceneMaskFallActive(fallActive);\n'
        + text[sync_pos + len(sync_marker):])

old = '''        prefs.putString(key("water"), encode(masks[WATER]));\n        prefs.putBoolean(key("waterActive"), waterActive);\n        prefs.putBoolean(key("active"), data.getSceneMaskEnabled());\n'''
new = '''        prefs.putString(key("water"), encode(masks[WATER]));\n        prefs.putBoolean(key("waterActive"), waterActive);\n        prefs.putString(key("fall"), encode(masks[FALL]));\n        prefs.putBoolean(key("fallActive"), fallActive);\n        prefs.putBoolean(key("active"), data.getSceneMaskEnabled());\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor WATER save block not found')
text = text.replace(old, new, 1)

old = '''    private void activateWaterMask() {\n        waterActive = true;\n        data.setSceneMaskWaterActive(true);\n    }\n\n'''
new = '''    private void activateWaterMask() {\n        waterActive = true;\n        data.setSceneMaskWaterActive(true);\n    }\n\n    private void activateFallMask() {\n        fallActive = true;\n        data.setSceneMaskFallActive(true);\n    }\n\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor activateWaterMask method not found')
text = text.replace(old, new, 1)

old = '        if (mode == WATER) activateWaterMask();\n'
if text.count(old) != 2:
    raise RuntimeError('SceneMaskEditor expected WATER activation in paint and morph')
text = text.replace(old,
                    '        if (mode == WATER) activateWaterMask();\n        if (mode == FALL) activateFallMask();\n')

old = '''        else if (keycode == Input.Keys.NUM_5) {\n            moveMode = true;\n'''
new = '''        else if (keycode == Input.Keys.NUM_5) { moveMode = false; mode = FALL; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }\n        else if (keycode == Input.Keys.NUM_6) {\n            moveMode = true;\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor MOVE key-5 block not found')
text = text.replace(old, new, 1)

old = '        if (keycode == Input.Keys.W) { toggleLayerVisible(WATER, "WATER"); return true; }\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor WATER visibility key not found')
text = text.replace(old, old + '        if (keycode == Input.Keys.V) { toggleLayerVisible(FALL, "FALL"); return true; }\n', 1)

old = '            if (layer == WATER) activateWaterMask();\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor clear WATER activation not found')
text = text.replace(old, old + '            if (layer == FALL) activateFallMask();\n', 1)

old = '''                + ",\\\"water\\\":\\\"" + encode(masks[WATER]) + "\\\""\n                + ",\\\"waterActive\\\":" + waterActive + "}";\n'''
new = '''                + ",\\\"water\\\":\\\"" + encode(masks[WATER]) + "\\\""\n                + ",\\\"waterActive\\\":" + waterActive\n                + ",\\\"fall\\\":\\\"" + encode(masks[FALL]) + "\\\""\n                + ",\\\"fallActive\\\":" + fallActive + "}";\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor WATER export tail not found')
text = text.replace(old, new, 1)

old = '                if (layerVisible[WATER]) drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.42f));\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor WATER overlay line not found')
text = text.replace(old,
                    old + '                if (layerVisible[FALL]) drawMaskRuns(batch, masks[FALL], new Color(1f, 0.08f, 0.62f, 0.52f));\n', 1)

old = '            String baseMode = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : mode == BEHIND ? "BEHIND" : "WATER";\n'
new = '            String baseMode = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : mode == BEHIND ? "BEHIND" : mode == WATER ? "WATER" : "FALL";\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor mode-name expression not found')
text = text.replace(old, new, 1)

old = '                            : "1 front 2 block 3 behind 4 water 5 MOVE | Shift-line | Option erase | R/G/B/W hide",\n'
new = '                            : "1 front 2 block 3 behind 4 water 5 FALL 6 MOVE | V hide fall | Shift-line | Option erase",\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor paint HUD line not found')
text = text.replace(old, new, 1)

text = text.replace('1=foreground/occluder, 2=collision, 3=behind-zone,',
                    '1=foreground/occluder, 2=collision, 3=behind-zone, 4=water, 5=fall/special,')

editor.write_text(text)
print('FALL mask installed: 5 paints AGI HITSPEC danger, 6 moves sprites; magenta overlay persists per room')
