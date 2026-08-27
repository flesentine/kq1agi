#!/usr/bin/env python3
from pathlib import Path
import sys
import runpy

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scene_mask_fall.py /path/to/agile-gdx')
root = Path(sys.argv[1]).resolve()

def replace_one(path, old, new, label):
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError(label + f' (found {text.count(old)})')
    path.write_text(text.replace(old, new, 1))

# FALL is a fifth editable mask. It maps to original AGI control colour 2, which
# KQ1 already exposes as HITSPEC, so existing room logic handles the danger.

# Shared API.
p = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
replace_one(p,
'''    default boolean getSceneMaskWaterActive() { return false; }\n    default void setSceneMaskWaterActive(boolean value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
'''    default boolean getSceneMaskWaterActive() { return false; }\n    default void setSceneMaskWaterActive(boolean value) { }\n    default boolean getSceneMaskFallActive() { return false; }\n    default void setSceneMaskFallActive(boolean value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''', 'VariableData WATER metadata anchor not found')

# GWT transport. Append FALL after the existing sprite/visual debug tables so the
# browser RESET SPRITE table remains at its established 3981/3982 indices.
p = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = p.read_text()
checks = [
    ('    private static final int SCENE_MASK_LAYERS = 4;\n',
     '    private static final int SCENE_MASK_LAYERS = 5;\n', 'mask layer count'),
    ('    private static final int SCENE_VISUAL_OFFSET_FIELDS = 5;\n',
     '''    private static final int SCENE_VISUAL_OFFSET_FIELDS = 5;\n\n    // Appended so existing browser debug table offsets remain stable.\n    private static final int SCENE_MASK_FALL_ACTIVE = 4142;\n    private static final int SCENE_MASK_FALL_BITS = 4143;\n''', 'visual offset tail'),
    ('''    @Override\n    public void setSceneMaskWaterActive(boolean value) {\n        variableArray.set(SCENE_MASK_WATER_ACTIVE, value ? TRUE : FALSE);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n''',
     '''    @Override\n    public void setSceneMaskWaterActive(boolean value) {\n        variableArray.set(SCENE_MASK_WATER_ACTIVE, value ? TRUE : FALSE);\n    }\n\n    @Override\n    public boolean getSceneMaskFallActive() {\n        return variableArray.get(SCENE_MASK_FALL_ACTIVE) == TRUE;\n    }\n\n    @Override\n    public void setSceneMaskFallActive(boolean value) {\n        variableArray.set(SCENE_MASK_FALL_ACTIVE, value ? TRUE : FALSE);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n''', 'water methods'),
    ('''        int bitIndex = (y * SCENE_MASK_WIDTH) + x;\n        return SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS) + (bitIndex >>> 5);\n''',
     '''        int bitIndex = (y * SCENE_MASK_WIDTH) + x;\n        int base = (layer == 4)\n                ? SCENE_MASK_FALL_BITS\n                : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);\n        return base + (bitIndex >>> 5);\n''', 'mask index'),
    ('        int start = SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);\n',
     '''        int start = (layer == 4)\n                ? SCENE_MASK_FALL_BITS\n                : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);\n''', 'clear layer start'),
]
for old, new, label in checks:
    if text.count(old) != 1:
        raise RuntimeError('GwtVariableData ' + label + f' not found (found {text.count(old)})')
    text = text.replace(old, new, 1)
capacity = 'Defines.NUMVARS + Defines.NUMFLAGS + 3630'
if text.count(capacity) != 2:
    raise RuntimeError('GwtVariableData capacity markers not found')
text = text.replace(capacity, 'Defines.NUMVARS + Defines.NUMFLAGS + 4471')
p.write_text(text)

# Runtime: custom FALL => AGI special control 2; custom WATER => 3. An edited
# plane becomes authoritative only for its matching original control colour.
p = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = p.read_text()
old = '    public static final int WATER = 3;\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskRuntime WATER constant not found')
text = text.replace(old, old + '    public static final int FALL = 4;\n', 1)
old = '''    public static int effectiveControlPriority(GameState state, int objectNumber,\n            int x, int y, int legacyPriority) {\n        VariableData data = state.getVariableData();\n        if (objectNumber != 0 || !editorOwnsRoom(state) || !data.getSceneMaskWaterActive()) {\n            return legacyPriority;\n        }\n        if (x < 0 || x >= 160 || y < 0 || y >= 168) {\n            return legacyPriority;\n        }\n        if (data.getSceneMaskBit(WATER, x, y)) {\n            return 3;\n        }\n        return legacyPriority == 3 ? 4 : legacyPriority;\n    }\n'''
new = '''    public static int effectiveControlPriority(GameState state, int objectNumber,\n            int x, int y, int legacyPriority) {\n        VariableData data = state.getVariableData();\n        if (objectNumber != 0 || !editorOwnsRoom(state)) return legacyPriority;\n        if (x < 0 || x >= 160 || y < 0 || y >= 168) return legacyPriority;\n        boolean fallActive = data.getSceneMaskFallActive();\n        boolean waterActive = data.getSceneMaskWaterActive();\n        if (!fallActive && !waterActive) return legacyPriority;\n        if (fallActive && data.getSceneMaskBit(FALL, x, y)) return 2;\n        if (waterActive && data.getSceneMaskBit(WATER, x, y)) return 3;\n        if (fallActive && legacyPriority == 2) legacyPriority = 4;\n        if (waterActive && legacyPriority == 3) legacyPriority = 4;\n        return legacyPriority;\n    }\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskRuntime water control method not found')
p.write_text(text.replace(old, new, 1))

# Editor.
p = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = p.read_text()
repls = [
    ('    private static final int WATER = 3;\n',
     '    private static final int WATER = 3;\n    private static final int FALL = 4;\n', 'WATER constant'),
    ('    private final boolean[][][] masks = new boolean[4][HEIGHT][WIDTH];\n',
     '    private final boolean[][][] masks = new boolean[5][HEIGHT][WIDTH];\n', 'mask array'),
    ('    private final boolean[] layerVisible = new boolean[] { true, true, true, true };\n',
     '    private final boolean[] layerVisible = new boolean[] { true, true, true, true, true };\n', 'visibility array'),
    ('''    private boolean waterActive;\n    private boolean moveMode;\n''',
     '''    private boolean waterActive;\n    private boolean fallActive;\n    private boolean moveMode;\n''', 'water/move fields'),
    ('        String savedWater = prefs.getString(key("water"), "");\n',
     '        String savedWater = prefs.getString(key("water"), "");\n        String savedFall = prefs.getString(key("fall"), "");\n', 'saved water'),
    ('''        decode(savedWater, masks[WATER]);\n        waterActive = prefs.getBoolean(key("waterActive"), false);\n        data.setSceneMaskWaterActive(waterActive);\n        data.setSceneMaskRoom(room);\n''',
     '''        decode(savedWater, masks[WATER]);\n        waterActive = prefs.getBoolean(key("waterActive"), false);\n        data.setSceneMaskWaterActive(waterActive);\n        decode(savedFall, masks[FALL]);\n        fallActive = prefs.getBoolean(key("fallActive"), false);\n        data.setSceneMaskFallActive(fallActive);\n        data.setSceneMaskRoom(room);\n''', 'water load'),
    ('''        prefs.putString(key("water"), encode(masks[WATER]));\n        prefs.putBoolean(key("waterActive"), waterActive);\n        prefs.putBoolean(key("active"), data.getSceneMaskEnabled());\n''',
     '''        prefs.putString(key("water"), encode(masks[WATER]));\n        prefs.putBoolean(key("waterActive"), waterActive);\n        prefs.putString(key("fall"), encode(masks[FALL]));\n        prefs.putBoolean(key("fallActive"), fallActive);\n        prefs.putBoolean(key("active"), data.getSceneMaskEnabled());\n''', 'water save'),
    ('''    private void activateWaterMask() {\n        waterActive = true;\n        data.setSceneMaskWaterActive(true);\n    }\n\n''',
     '''    private void activateWaterMask() {\n        waterActive = true;\n        data.setSceneMaskWaterActive(true);\n    }\n\n    private void activateFallMask() {\n        fallActive = true;\n        data.setSceneMaskFallActive(true);\n    }\n\n''', 'activate water'),
    ('''        else if (keycode == Input.Keys.NUM_5) {\n            moveMode = true;\n''',
     '''        else if (keycode == Input.Keys.NUM_5) { moveMode = false; mode = FALL; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }\n        else if (keycode == Input.Keys.NUM_6) {\n            moveMode = true;\n''', 'MOVE key 5'),
    ('        if (keycode == Input.Keys.W) { toggleLayerVisible(WATER, "WATER"); return true; }\n',
     '        if (keycode == Input.Keys.W) { toggleLayerVisible(WATER, "WATER"); return true; }\n        if (keycode == Input.Keys.V) { toggleLayerVisible(FALL, "FALL"); return true; }\n', 'W visibility'),
    ('''                + ",\\\"water\\\":\\\"" + encode(masks[WATER]) + "\\\""\n                + ",\\\"waterActive\\\":" + waterActive + "}";\n''',
     '''                + ",\\\"water\\\":\\\"" + encode(masks[WATER]) + "\\\""\n                + ",\\\"waterActive\\\":" + waterActive\n                + ",\\\"fall\\\":\\\"" + encode(masks[FALL]) + "\\\""\n                + ",\\\"fallActive\\\":" + fallActive + "}";\n''', 'water export'),
    ('                if (layerVisible[WATER]) drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.42f));\n',
     '                if (layerVisible[WATER]) drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.42f));\n                if (layerVisible[FALL]) drawMaskRuns(batch, masks[FALL], new Color(1f, 0.08f, 0.62f, 0.52f));\n', 'water overlay'),
    ('            String baseMode = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : mode == BEHIND ? "BEHIND" : "WATER";\n',
     '            String baseMode = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : mode == BEHIND ? "BEHIND" : mode == WATER ? "WATER" : "FALL";\n', 'mode name'),
    ('                            : "1 front 2 block 3 behind 4 water 5 MOVE | Shift-line | Option erase | R/G/B/W hide",\n',
     '                            : "1 front 2 block 3 behind 4 water 5 FALL 6 MOVE | V hide fall | Shift-line | Option erase",\n', 'HUD'),
]
for old, new, label in repls:
    if text.count(old) != 1:
        raise RuntimeError('SceneMaskEditor ' + label + f' not found (found {text.count(old)})')
    text = text.replace(old, new, 1)

loop = '        for (int layer = 0; layer < 4; layer++) {\n'
if text.count(loop) != 2:
    raise RuntimeError(f'SceneMaskEditor four-layer loops: found {text.count(loop)}')
text = text.replace(loop, '        for (int layer = 0; layer < 5; layer++) {\n')

# Add FALL metadata to syncAll without touching loadRoom's WATER write.
sync_start = text.index('    private void syncAll() {')
marker = '        data.setSceneMaskWaterActive(waterActive);\n'
pos = text.index(marker, sync_start)
text = text[:pos] + marker + '        data.setSceneMaskFallActive(fallActive);\n' + text[pos + len(marker):]

# paint() checks mode; morphSelectedLayer() and CLEAR both check local layer.
mode_water = '        if (mode == WATER) activateWaterMask();\n'
if text.count(mode_water) != 1:
    raise RuntimeError(f'SceneMaskEditor paint WATER activation: found {text.count(mode_water)}')
text = text.replace(mode_water, mode_water + '        if (mode == FALL) activateFallMask();\n', 1)
layer_water = '        if (layer == WATER) activateWaterMask();\n'
if text.count(layer_water) != 2:
    raise RuntimeError(f'SceneMaskEditor morph/clear WATER activation: found {text.count(layer_water)}')
text = text.replace(layer_water, layer_water + '        if (layer == FALL) activateFallMask();\n')

text = text.replace('1=foreground/occluder, 2=collision, 3=behind-zone,',
                    '1=foreground/occluder, 2=collision, 3=behind-zone, 4=water, 5=fall/special,')
p.write_text(text)
print('FALL mask installed: 5 paints AGI HITSPEC danger, 6 moves sprites; magenta overlay persists per room')

# Immediately migrate Sierra's hidden 0/1/2/3 control picture into the same
# visible/editable BLOCK/WATER/FALL planes. Keeping this chained here guarantees
# the unified pass runs after FALL exists in every browser build.
runpy.run_path(str(Path(__file__).with_name('unify_scene_control_map.py')), run_name='__main__')
