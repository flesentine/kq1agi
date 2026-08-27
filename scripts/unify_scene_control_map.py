#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: unify_scene_control_map.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()


def replace_one(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    path.write_text(text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# 1) Shared seed handshake.
#
# The editor and interpreter live on different browser threads. The UI requests
# a one-time import of Sierra's real control picture for the room. The worker
# merges those legacy controls into the editable BLOCK/WATER/FALL planes and
# marks the room ready. After that those editable planes are the ONE player
# control map; Sierra's hidden 0/1/2/3 controls no longer compete with it.
# ---------------------------------------------------------------------------
variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
text = variable_data.read_text()
anchor = '''    default boolean getSceneMaskFallActive() { return false; }\n    default void setSceneMaskFallActive(boolean value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n'''
replacement = '''    default boolean getSceneMaskFallActive() { return false; }\n    default void setSceneMaskFallActive(boolean value) { }\n    // 0 = idle; -(room+1) = UI requests Sierra control import; room+1 = ready.\n    default int getSceneControlSeedState() { return 0; }\n    default void setSceneControlSeedState(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n'''
if text.count(anchor) != 1:
    raise RuntimeError('VariableData FALL/control-seed anchor not found')
variable_data.write_text(text.replace(anchor, replacement, 1))


gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()
anchor = '''    private static final int SCENE_MASK_FALL_ACTIVE = 4142;\n    private static final int SCENE_MASK_FALL_BITS = 4143;\n'''
replacement = '''    private static final int SCENE_MASK_FALL_ACTIVE = 4142;\n    private static final int SCENE_MASK_FALL_BITS = 4143;\n    // One slot immediately after the 840-word FALL bit plane.\n    private static final int SCENE_CONTROL_SEED_STATE = 4983;\n'''
if text.count(anchor) != 1:
    raise RuntimeError('GwtVariableData FALL constants not found')
text = text.replace(anchor, replacement, 1)

capacity = 'Defines.NUMVARS + Defines.NUMFLAGS + 4471'
if text.count(capacity) != 2:
    raise RuntimeError(f'GwtVariableData unified capacity markers: found {text.count(capacity)}')
text = text.replace(capacity, 'Defines.NUMVARS + Defines.NUMFLAGS + 4472')

anchor = '''    @Override\n    public void setSceneMaskFallActive(boolean value) {\n        variableArray.set(SCENE_MASK_FALL_ACTIVE, value ? TRUE : FALSE);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
replacement = '''    @Override\n    public void setSceneMaskFallActive(boolean value) {\n        variableArray.set(SCENE_MASK_FALL_ACTIVE, value ? TRUE : FALSE);\n    }\n\n    @Override\n    public int getSceneControlSeedState() {\n        return variableArray.get(SCENE_CONTROL_SEED_STATE);\n    }\n\n    @Override\n    public void setSceneControlSeedState(int value) {\n        variableArray.set(SCENE_CONTROL_SEED_STATE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
if text.count(anchor) != 1:
    raise RuntimeError('GwtVariableData FALL methods anchor not found')
text = text.replace(anchor, replacement, 1)
gwt.write_text(text)


# ---------------------------------------------------------------------------
# 2) Worker runtime: import Sierra's actual control picture into the visible,
# editable masks, then use ONLY those masks for Graham's control semantics.
# Existing user/AI mask pixels win during migration so current edits are kept.
# ---------------------------------------------------------------------------
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
anchor = '''    public static boolean editorOwnsRoom(GameState state) {\n'''
helpers = '''    public static boolean unifiedControlReady(GameState state) {\n        if (state == null) return false;\n        VariableData data = state.getVariableData();\n        int room = state.getVar(Defines.CURROOM);\n        return editorOwnsRoom(state) && data.getSceneControlSeedState() == (room + 1);\n    }\n\n    /**\n     * Import Sierra's live control picture into the editable control planes.\n     *\n     * 0/1 -> BLOCK, 2 -> FALL/HITSPEC, 3 -> WATER. Existing editable pixels\n     * are treated as intentional overrides and are never overwritten. Once the\n     * import completes, Graham reads only these visible planes.\n     */\n    public static void ensureUnifiedControlSeed(GameState state) {\n        if (state == null || !editorOwnsRoom(state)) return;\n        VariableData data = state.getVariableData();\n        int room = state.getVar(Defines.CURROOM);\n        if (data.getSceneControlSeedState() != -(room + 1)) return;\n        if (state.controlPixels == null || state.controlPixels.length < (160 * 168)) return;\n\n        for (int y = 0; y < 168; y++) {\n            for (int x = 0; x < 160; x++) {\n                boolean alreadyEdited = data.getSceneMaskBit(COLLISION, x, y)\n                        || data.getSceneMaskBit(WATER, x, y)\n                        || data.getSceneMaskBit(FALL, x, y);\n                if (alreadyEdited) continue;\n\n                int legacy = state.controlPixels[(y * 160) + x];\n                if (legacy == 0 || legacy == 1) {\n                    data.setSceneMaskBit(COLLISION, x, y, true);\n                } else if (legacy == 2) {\n                    data.setSceneMaskBit(FALL, x, y, true);\n                } else if (legacy == 3) {\n                    data.setSceneMaskBit(WATER, x, y, true);\n                }\n            }\n        }\n\n        // Unified control semantics are always active after import, even when a\n        // particular room contains no WATER or FALL pixels.\n        data.setSceneMaskWaterActive(true);\n        data.setSceneMaskFallActive(true);\n        data.setSceneControlSeedState(room + 1);\n    }\n\n    public static boolean editorOwnsRoom(GameState state) {\n'''
if text.count(anchor) != 1:
    raise RuntimeError('SceneMaskRuntime editorOwnsRoom anchor not found')
text = text.replace(anchor, helpers, 1)

old = '''    public static int effectiveControlPriority(GameState state, int objectNumber,\n            int x, int y, int legacyPriority) {\n        VariableData data = state.getVariableData();\n        if (objectNumber != 0 || !editorOwnsRoom(state)) return legacyPriority;\n        if (x < 0 || x >= 160 || y < 0 || y >= 168) return legacyPriority;\n        boolean fallActive = data.getSceneMaskFallActive();\n        boolean waterActive = data.getSceneMaskWaterActive();\n        if (!fallActive && !waterActive) return legacyPriority;\n        if (fallActive && data.getSceneMaskBit(FALL, x, y)) return 2;\n        if (waterActive && data.getSceneMaskBit(WATER, x, y)) return 3;\n        if (fallActive && legacyPriority == 2) legacyPriority = 4;\n        if (waterActive && legacyPriority == 3) legacyPriority = 4;\n        return legacyPriority;\n    }\n'''
new = '''    public static int effectiveControlPriority(GameState state, int objectNumber,\n            int x, int y, int legacyPriority) {\n        // Preserve Sierra behavior for NPCs and during the split-second seed\n        // handshake. For Graham, the imported editable map becomes authoritative.\n        if (objectNumber != 0 || !unifiedControlReady(state)) return legacyPriority;\n        if (x < 0 || x >= 160 || y < 0 || y >= 168) return legacyPriority;\n\n        VariableData data = state.getVariableData();\n        if (data.getSceneMaskBit(FALL, x, y)) return 2;\n        if (data.getSceneMaskBit(WATER, x, y)) return 3;\n        if (data.getSceneMaskBit(COLLISION, x, y)) return 1;\n        return 4;\n    }\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskRuntime pre-unified effectiveControlPriority not found')
text = text.replace(old, new, 1)

anchor = '''    public static void updateOccluderFlag(GameState state) {\n        VariableData data = state.getVariableData();\n'''
replacement = '''    public static void updateOccluderFlag(GameState state) {\n        // This method already runs every scene redraw on the interpreter thread,\n        // making it a safe place to fulfil a UI-thread Sierra-map import request.\n        ensureUnifiedControlSeed(state);\n        VariableData data = state.getVariableData();\n'''
if text.count(anchor) != 1:
    raise RuntimeError('SceneMaskRuntime updateOccluderFlag anchor not found')
text = text.replace(anchor, replacement, 1)
runtime.write_text(text)


# The older Room 1 compatibility pass must not erase a BLOCK pixel from the new
# unified map merely because that pixel happens to sit in the old tree corridor.
animated = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
text = animated.read_text()
old = '''                if ((this.objectNumber == 0)\n                        && (priority == 0 || priority == 1)\n                        && ModernRoomDepth.insideOldTreeControlCorridor(\n'''
new = '''                if ((this.objectNumber == 0)\n                        && (priority == 0 || priority == 1)\n                        && !SceneMaskRuntime.unifiedControlReady(state)\n                        && ModernRoomDepth.insideOldTreeControlCorridor(\n'''
if text.count(old) != 1:
    raise RuntimeError(f'AnimatedObject old-tree compatibility block: found {text.count(old)}')
text = text.replace(old, new, 1)
animated.write_text(text)


# ---------------------------------------------------------------------------
# 3) UI editor migration.
#
# On first visit after this upgrade we keep every existing custom/AI pixel, ask
# the worker to merge Sierra's original controls, then pull that merged map back
# into the local editor arrays and persist it. Future loads start directly from
# the saved unified map. BLOCK/WATER/FALL painting is mutually exclusive per
# pixel so there is genuinely only one active control value at a coordinate.
# ---------------------------------------------------------------------------
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

old = '''    private boolean fallActive;\n    private boolean moveMode;\n'''
new = '''    private boolean fallActive;\n    private boolean waitingForControlSeed;\n    private boolean moveMode;\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor FALL/move field anchor not found')
text = text.replace(old, new, 1)

# Request Sierra import after the existing masks have been synchronised. This
# means existing custom pixels are already present in SharedArrayBuffer and win
# over the imported legacy value at the same coordinate.
old = '''        syncAll();\n        dirty = false;\n    }\n\n    private void syncAll() {\n'''
new = '''        syncAll();\n        boolean unifiedSaved = prefs.getBoolean(key("unifiedControlV1"), false);\n        if (unifiedSaved) {\n            waitingForControlSeed = false;\n            waterActive = true;\n            fallActive = true;\n            data.setSceneMaskWaterActive(true);\n            data.setSceneMaskFallActive(true);\n            data.setSceneControlSeedState(room + 1);\n        } else {\n            waitingForControlSeed = true;\n            data.setSceneControlSeedState(-(room + 1));\n        }\n        dirty = false;\n    }\n\n    private void adoptUnifiedControlSeedIfReady() {\n        if (!waitingForControlSeed || data.getSceneControlSeedState() != (room + 1)) return;\n\n        for (int y = 0; y < HEIGHT; y++) {\n            for (int x = 0; x < WIDTH; x++) {\n                boolean fall = data.getSceneMaskBit(FALL, x, y);\n                boolean water = !fall && data.getSceneMaskBit(WATER, x, y);\n                boolean block = !fall && !water && data.getSceneMaskBit(COLLISION, x, y);\n\n                masks[FALL][y][x] = fall;\n                masks[WATER][y][x] = water;\n                masks[COLLISION][y][x] = block;\n                data.setSceneMaskBit(FALL, x, y, fall);\n                data.setSceneMaskBit(WATER, x, y, water);\n                data.setSceneMaskBit(COLLISION, x, y, block);\n            }\n        }\n\n        waitingForControlSeed = false;\n        waterActive = true;\n        fallActive = true;\n        data.setSceneMaskWaterActive(true);\n        data.setSceneMaskFallActive(true);\n        prefs.putBoolean(key("unifiedControlV1"), true);\n        dirty = true;\n        saveRoom();\n        notice("SIERRA CONTROL MAP IMPORTED");\n    }\n\n    private void syncAll() {\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor ensureRoom/syncAll tail not found')
text = text.replace(old, new, 1)

old = '''    public void render(SpriteBatch batch) {\n        ensureRoom();\n'''
new = '''    public void render(SpriteBatch batch) {\n        ensureRoom();\n        adoptUnifiedControlSeedIfReady();\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor render ensureRoom anchor not found')
text = text.replace(old, new, 1)

# Make BLOCK/WATER/FALL one control value per point. Painting one replaces the
# other two at that coordinate; erasing makes that selected control walkable.
old = '''                masks[layer][y][x] = !erase;\n                data.setSceneMaskBit(layer, x, y, !erase);\n'''
new = '''                boolean value = !erase;\n                if (value && (layer == COLLISION || layer == WATER || layer == FALL)) {\n                    int[] controls = new int[] { COLLISION, WATER, FALL };\n                    for (int other : controls) {\n                        if (other == layer) continue;\n                        masks[other][y][x] = false;\n                        data.setSceneMaskBit(other, x, y, false);\n                    }\n                }\n                masks[layer][y][x] = value;\n                data.setSceneMaskBit(layer, x, y, value);\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor paint bit write not found')
text = text.replace(old, new, 1)

# Saved unified maps should always resume in authoritative mode, irrespective of
# the old per-layer activation flags that existed before this migration.
old = '''        prefs.putBoolean(key("active"), data.getSceneMaskEnabled());\n'''
new = '''        prefs.putBoolean(key("active"), data.getSceneMaskEnabled());\n        if (!waitingForControlSeed && data.getSceneControlSeedState() == (room + 1)) {\n            prefs.putBoolean(key("unifiedControlV1"), true);\n        }\n'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor save active line not found')
text = text.replace(old, new, 1)

editor.write_text(text)
print('Unified control map installed: Sierra BLOCK/WATER/FALL imported, visible, editable, and authoritative for Graham')
