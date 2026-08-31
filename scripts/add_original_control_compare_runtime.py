#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_original_control_compare_runtime.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()


def one(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    path.write_text(text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Read-only Sierra control-map snapshot for EDITED / ORIGINAL comparison.
# This is deliberately separate from the editable mask planes so looking at the
# original can never overwrite the user's authored BLOCK/WATER/FALL pixels.
# ---------------------------------------------------------------------------
variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
one(
    variable_data,
    '''    default int getSceneMaskDangerViewBridge() { return 0; }\n    default void setSceneMaskDangerViewBridge(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
    '''    default int getSceneMaskDangerViewBridge() { return 0; }\n    default void setSceneMaskDangerViewBridge(int value) { }\n    // Read-only copy of Sierra's original 0/1/2/3 control picture. Layers are\n    // 0=BLOCK (legacy 0/1), 1=FALL/HITSPEC (2), 2=WATER (3).\n    default int getSceneOriginalControlSeedState() { return 0; }\n    default void setSceneOriginalControlSeedState(int value) { }\n    default boolean getSceneOriginalControlBit(int layer, int x, int y) { return false; }\n    default void setSceneOriginalControlBit(int layer, int x, int y, boolean value) { }\n    default void clearSceneOriginalControlLayer(int layer) { }\n    default int getSceneMaskSourceViewBridge() { return 0; }\n    default void setSceneMaskSourceViewBridge(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
    'VariableData original-control API',
)


gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()
old = '    private static final int SCENE_MASK_DANGER_VIEW_BRIDGE = 5830;\n'
new = old + '''    private static final int SCENE_ORIGINAL_CONTROL_BITS = 5831;\n    private static final int SCENE_ORIGINAL_CONTROL_LAYERS = 3;\n    private static final int SCENE_ORIGINAL_CONTROL_SEED_STATE = 8351;\n    private static final int SCENE_MASK_SOURCE_VIEW_BRIDGE = 8352;\n'''
if text.count(old) != 1:
    raise RuntimeError('GwtVariableData original-control constant anchor not found')
text = text.replace(old, new, 1)

capacity = 'Defines.NUMVARS + Defines.NUMFLAGS + 5319'
if text.count(capacity) != 2:
    raise RuntimeError(f'GwtVariableData original-control capacity markers: expected 2, found {text.count(capacity)}')
text = text.replace(capacity, 'Defines.NUMVARS + Defines.NUMFLAGS + 7841')

old = '''    @Override\n    public void setSceneMaskDangerViewBridge(int value) {\n        variableArray.set(SCENE_MASK_DANGER_VIEW_BRIDGE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
new = '''    @Override\n    public void setSceneMaskDangerViewBridge(int value) {\n        variableArray.set(SCENE_MASK_DANGER_VIEW_BRIDGE, value);\n    }\n\n    @Override\n    public int getSceneOriginalControlSeedState() {\n        return variableArray.get(SCENE_ORIGINAL_CONTROL_SEED_STATE);\n    }\n\n    @Override\n    public void setSceneOriginalControlSeedState(int value) {\n        variableArray.set(SCENE_ORIGINAL_CONTROL_SEED_STATE, value);\n    }\n\n    private int sceneOriginalControlIndex(int layer, int x, int y) {\n        if (layer < 0 || layer >= SCENE_ORIGINAL_CONTROL_LAYERS\n                || x < 0 || x >= SCENE_MASK_WIDTH || y < 0 || y >= SCENE_MASK_HEIGHT) return -1;\n        int bitIndex = (y * SCENE_MASK_WIDTH) + x;\n        return SCENE_ORIGINAL_CONTROL_BITS + (layer * SCENE_MASK_WORDS) + (bitIndex >>> 5);\n    }\n\n    @Override\n    public boolean getSceneOriginalControlBit(int layer, int x, int y) {\n        int index = sceneOriginalControlIndex(layer, x, y);\n        if (index < 0) return false;\n        int bitIndex = (y * SCENE_MASK_WIDTH) + x;\n        return (variableArray.get(index) & (1 << (bitIndex & 31))) != 0;\n    }\n\n    @Override\n    public void setSceneOriginalControlBit(int layer, int x, int y, boolean value) {\n        int index = sceneOriginalControlIndex(layer, x, y);\n        if (index < 0) return;\n        int bitIndex = (y * SCENE_MASK_WIDTH) + x;\n        int bit = 1 << (bitIndex & 31);\n        int word = variableArray.get(index);\n        variableArray.set(index, value ? (word | bit) : (word & ~bit));\n    }\n\n    @Override\n    public void clearSceneOriginalControlLayer(int layer) {\n        if (layer < 0 || layer >= SCENE_ORIGINAL_CONTROL_LAYERS) return;\n        int start = SCENE_ORIGINAL_CONTROL_BITS + (layer * SCENE_MASK_WORDS);\n        for (int i = 0; i < SCENE_MASK_WORDS; i++) variableArray.set(start + i, 0);\n    }\n\n    @Override\n    public int getSceneMaskSourceViewBridge() {\n        return variableArray.get(SCENE_MASK_SOURCE_VIEW_BRIDGE);\n    }\n\n    @Override\n    public void setSceneMaskSourceViewBridge(int value) {\n        variableArray.set(SCENE_MASK_SOURCE_VIEW_BRIDGE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
if text.count(old) != 1:
    raise RuntimeError('GwtVariableData original-control methods anchor not found')
text = text.replace(old, new, 1)
gwt.write_text(text)


runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
anchor = '    public static boolean unifiedControlReady(GameState state) {\n'
helper = '''    /** Seed a non-destructive read-only snapshot of Sierra's original control picture. */\n    public static void ensureOriginalControlSeed(GameState state) {\n        if (state == null) return;\n        VariableData data = state.getVariableData();\n        int room = state.getVar(Defines.CURROOM);\n        if (data.getSceneOriginalControlSeedState() != -(room + 1)) return;\n        if (state.controlPixels == null || state.controlPixels.length < (160 * 168)) return;\n\n        for (int layer = 0; layer < 3; layer++) data.clearSceneOriginalControlLayer(layer);\n        for (int y = 0; y < 168; y++) {\n            for (int x = 0; x < 160; x++) {\n                int legacy = state.controlPixels[(y * 160) + x];\n                if (legacy == 0 || legacy == 1) data.setSceneOriginalControlBit(0, x, y, true);\n                else if (legacy == 2) data.setSceneOriginalControlBit(1, x, y, true);\n                else if (legacy == 3) data.setSceneOriginalControlBit(2, x, y, true);\n            }\n        }\n        data.setSceneOriginalControlSeedState(room + 1);\n    }\n\n'''
if text.count(anchor) != 1:
    raise RuntimeError('SceneMaskRuntime original-control helper anchor not found')
text = text.replace(anchor, helper + anchor, 1)

# The seed-race fix already consolidated control/script preloading into one worker
# path. Extend that same path instead of adding another redraw-only hook.
old = '''        int controlState = data.getSceneControlSeedState();\n        int scriptState = data.getSceneScriptDangerSeedState();\n\n        if (controlState != expected && controlState != -expected) {\n            data.setSceneControlSeedState(-expected);\n            controlState = -expected;\n        }\n        if (scriptState != expected && scriptState != -expected) {\n            data.setSceneScriptDangerSeedState(-expected);\n            scriptState = -expected;\n        }\n\n        if (controlState == -expected) ensureUnifiedControlSeed(state);\n        if (scriptState == -expected) ensureScriptDangerSeed(state);\n'''
new = '''        int controlState = data.getSceneControlSeedState();\n        int scriptState = data.getSceneScriptDangerSeedState();\n        int originalState = data.getSceneOriginalControlSeedState();\n\n        if (controlState != expected && controlState != -expected) {\n            data.setSceneControlSeedState(-expected);\n            controlState = -expected;\n        }\n        if (scriptState != expected && scriptState != -expected) {\n            data.setSceneScriptDangerSeedState(-expected);\n            scriptState = -expected;\n        }\n        if (originalState != expected && originalState != -expected) {\n            data.setSceneOriginalControlSeedState(-expected);\n            originalState = -expected;\n        }\n\n        if (controlState == -expected) ensureUnifiedControlSeed(state);\n        if (scriptState == -expected) ensureScriptDangerSeed(state);\n        if (originalState == -expected) ensureOriginalControlSeed(state);\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskRuntime consolidated seed-preload anchor not found')
text = text.replace(old, new, 1)
runtime.write_text(text)


editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

old = '    private final boolean[][] scriptFallDisplay = new boolean[HEIGHT][WIDTH];\n'
new = old + '    private final boolean[][][] originalControls = new boolean[3][HEIGHT][WIDTH];\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor original-control array anchor not found')
text = text.replace(old, new, 1)

old = '    private boolean dangerView;\n'
new = '    private boolean dangerView;\n    private boolean sourceOriginalView;\n    private boolean waitingForOriginalControlSeed;\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor original-view state anchor not found')
text = text.replace(old, new, 1)

# The worker may have preloaded ORIGINAL before the UI claims the room. Always arm
# one local adoption pass; request a seed only if it is not already ready.
old = '''        if (preloadedControlSeed || preloadedScriptSeed) prefs.flush();\n        dirty = false;\n'''
new = '''        if (preloadedControlSeed || preloadedScriptSeed) prefs.flush();\n        waitingForOriginalControlSeed = true;\n        if (data.getSceneOriginalControlSeedState() != expectedSceneSeed)\n            data.setSceneOriginalControlSeedState(-expectedSceneSeed);\n        dirty = false;\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor original seed request anchor not found')
text = text.replace(old, new, 1)

anchor = '    private void adoptUnifiedControlSeedIfReady() {\n'
helper = '''    private void adoptOriginalControlSeedIfReady() {\n        if (!waitingForOriginalControlSeed\n                || data.getSceneOriginalControlSeedState() != room + 1) return;\n        for (int y = 0; y < HEIGHT; y++) {\n            for (int x = 0; x < WIDTH; x++) {\n                for (int layer = 0; layer < 3; layer++)\n                    originalControls[layer][y][x] = data.getSceneOriginalControlBit(layer, x, y);\n            }\n        }\n        waitingForOriginalControlSeed = false;\n    }\n\n'''
if text.count(anchor) != 1:
    raise RuntimeError('SceneMaskEditor original adopt helper anchor not found')
text = text.replace(anchor, helper + anchor, 1)

old = '        adoptScriptDangerSeedIfReady();\n'
new = old + '        adoptOriginalControlSeedIfReady();\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor original adopt call anchor not found')
text = text.replace(old, new, 1)

# Direct browser bridge. 100=EDITED, 101=SIERRA ORIGINAL. If DANGER is toggled
# while Sierra source remains active, keep inspectMode read-only.
old = '''        int encodedDanger = data.getSceneMaskDangerViewBridge();\n        if (encodedDanger == 100 || encodedDanger == 101) {\n            setDangerView(encodedDanger == 101);\n            data.setSceneMaskDangerViewBridge(0);\n        }\n    }\n'''
new = '''        int encodedDanger = data.getSceneMaskDangerViewBridge();\n        if (encodedDanger == 100 || encodedDanger == 101) {\n            setDangerView(encodedDanger == 101);\n            if (sourceOriginalView) inspectMode = true;\n            data.setSceneMaskDangerViewBridge(0);\n        }\n\n        int encodedSource = data.getSceneMaskSourceViewBridge();\n        if (encodedSource == 100 || encodedSource == 101) {\n            sourceOriginalView = encodedSource == 101;\n            if (sourceOriginalView) {\n                eraser = false;\n                moveMode = false;\n                inspectMode = true;\n                notice("SIERRA ORIGINAL - READ ONLY");\n            } else {\n                inspectMode = dangerView;\n                notice("EDITED MAP");\n            }\n            data.setSceneMaskSourceViewBridge(0);\n        }\n    }\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor original source bridge consume anchor not found')
text = text.replace(old, new, 1)

# A real paint-layer selection exits the comparison source in the engine too.
for mode in ('OCCLUDER', 'COLLISION', 'BEHIND', 'WATER', 'FALL'):
    old = f'dangerView = false; inspectMode = false; moveMode = false; mode = {mode};'
    new = f'sourceOriginalView = false; dangerView = false; inspectMode = false; moveMode = false; mode = {mode};'
    if text.count(old) != 1:
        raise RuntimeError(f'SceneMaskEditor {mode} original-view exit anchor: found {text.count(old)}')
    text = text.replace(old, new, 1)

# DANGER's accessible renderer is indented one level by the accessibility wrapper.
old = '''                if (dangerView) {\n                    // WATER is one source. Scripted marks expose bridge/death positions\n                    // that do not coincide with WATER pixels.\n                    drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.50f));\n                    rebuildScriptFallDisplay();\n                    drawAccessibleEditableFall(batch);\n                    drawAccessibleScriptFall(batch);\n                }\n'''
new = '''                if (sourceOriginalView) {\n                    if (dangerView) {\n                        drawMaskRuns(batch, originalControls[2], new Color(0.08f, 0.92f, 1f, 0.50f));\n                        drawMaskRuns(batch, originalControls[1], new Color(1f, 0.72f, 0.10f, 0.55f));\n                        rebuildScriptFallDisplay();\n                        drawAccessibleScriptFall(batch);\n                    } else {\n                        drawMaskRuns(batch, originalControls[0], new Color(0.08f, 0.35f, 1f, 0.50f));\n                        drawMaskRuns(batch, originalControls[2], new Color(0.08f, 0.92f, 1f, 0.48f));\n                        drawMaskRuns(batch, originalControls[1], new Color(1f, 0.72f, 0.10f, 0.55f));\n                    }\n                } else if (dangerView) {\n                    // EDITED DANGER: authored WATER/FALL plus scripted game triggers.\n                    drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.50f));\n                    rebuildScriptFallDisplay();\n                    drawAccessibleEditableFall(batch);\n                    drawAccessibleScriptFall(batch);\n                }\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor source-aware DANGER render anchor not found')
text = text.replace(old, new, 1)

# Ordinary authored overlays disappear while ORIGINAL is displayed.
for old, new, label in [
    ('if (!dangerView && layerVisible[OCCLUDER])', 'if (!sourceOriginalView && !dangerView && layerVisible[OCCLUDER])', 'FRONT'),
    ('if (!dangerView && layerVisible[COLLISION])', 'if (!sourceOriginalView && !dangerView && layerVisible[COLLISION])', 'BLOCK'),
    ('if (!dangerView && layerVisible[BEHIND])', 'if (!sourceOriginalView && !dangerView && layerVisible[BEHIND])', 'BEHIND'),
    ('if (!dangerView && layerVisible[WATER])', 'if (!sourceOriginalView && !dangerView && layerVisible[WATER])', 'WATER'),
    ('if (!dangerView && layerVisible[FALL])', 'if (!sourceOriginalView && !dangerView && layerVisible[FALL])', 'FALL'),
]:
    if text.count(old) != 1:
        raise RuntimeError(f'SceneMaskEditor {label} original-render guard: found {text.count(old)}')
    text = text.replace(old, new, 1)

editor.write_text(text)
print('ORIGINAL/EDITED control comparison installed: non-destructive Sierra BLOCK/FALL/WATER snapshot + source-aware DANGER')
