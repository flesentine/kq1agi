#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scripted_fall_zones.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# Add a sixth debug mask for SCRIPT_FALL. It records position-based room-script
# danger triggers (bridge edges, scripted plunges, etc.) so FALL debug can show
# them without turning those script rectangles into a second collision system.

# Shared state API.
p = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
text = p.read_text()
old = '''    default int getSceneControlSeedState() { return 0; }
    default void setSceneControlSeedState(int value) { }
    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }
'''
new = '''    default int getSceneControlSeedState() { return 0; }
    default void setSceneControlSeedState(int value) { }
    // Separate one-time handshake for position-based scripted danger regions.
    default int getSceneScriptDangerSeedState() { return 0; }
    default void setSceneScriptDangerSeedState(int value) { }
    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }
'''
if text.count(old) != 1:
    raise RuntimeError('VariableData unified seed anchor not found')
p.write_text(text.replace(old, new, 1))

# SharedArrayBuffer transport. Layer 5 lives after the unified-control seed slot.
p = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = p.read_text()
repls = [
    ('    private static final int SCENE_MASK_LAYERS = 5;\n',
     '    private static final int SCENE_MASK_LAYERS = 6;\n',
     'GWT mask layer count'),
    ('''    private static final int SCENE_CONTROL_SEED_STATE = 4983;
''',
     '''    private static final int SCENE_CONTROL_SEED_STATE = 4983;
    private static final int SCENE_SCRIPT_FALL_BITS = 4984;
    private static final int SCENE_SCRIPT_DANGER_SEED_STATE = 5824;
''',
     'GWT unified seed constant'),
    ('Defines.NUMVARS + Defines.NUMFLAGS + 4472',
     'Defines.NUMVARS + Defines.NUMFLAGS + 5313',
     'GWT variable capacity'),
    ('''    @Override
    public void setSceneControlSeedState(int value) {
        variableArray.set(SCENE_CONTROL_SEED_STATE, value);
    }

    private int sceneMaskIndex(int layer, int x, int y) {
''',
     '''    @Override
    public void setSceneControlSeedState(int value) {
        variableArray.set(SCENE_CONTROL_SEED_STATE, value);
    }

    @Override
    public int getSceneScriptDangerSeedState() {
        return variableArray.get(SCENE_SCRIPT_DANGER_SEED_STATE);
    }

    @Override
    public void setSceneScriptDangerSeedState(int value) {
        variableArray.set(SCENE_SCRIPT_DANGER_SEED_STATE, value);
    }

    private int sceneMaskIndex(int layer, int x, int y) {
''',
     'GWT unified seed methods'),
    ('''        int base = (layer == 4)
                ? SCENE_MASK_FALL_BITS
                : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);
''',
     '''        int base = (layer == 4)
                ? SCENE_MASK_FALL_BITS
                : (layer == 5)
                    ? SCENE_SCRIPT_FALL_BITS
                    : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);
''',
     'GWT mask index'),
    ('''        int start = (layer == 4)
                ? SCENE_MASK_FALL_BITS
                : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);
''',
     '''        int start = (layer == 4)
                ? SCENE_MASK_FALL_BITS
                : (layer == 5)
                    ? SCENE_SCRIPT_FALL_BITS
                    : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);
''',
     'GWT clear layer index'),
]
for old, new, label in repls:
    count = text.count(old)
    if label == 'GWT variable capacity':
        if count != 2:
            raise RuntimeError(f'{label}: expected 2 matches, found {count}')
        text = text.replace(old, new)
    else:
        if count != 1:
            raise RuntimeError(f'{label}: expected 1 match, found {count}')
        text = text.replace(old, new, 1)
p.write_text(text)

# Worker-side logic scanner. AGI room scripts often use posn()/center.posn()/
# right.posn() rectangles for hazards that are not control-colour 2. Identify
# position tests whose IF body looks like a fall/death cinematic while excluding
# room-change branches.
p = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = p.read_text()
package_anchor = 'package com.agifans.agile;\n'
imports = '''package com.agifans.agile;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

import com.agifans.agile.agilib.Logic;
import com.agifans.agile.agilib.Logic.Action;
import com.agifans.agile.agilib.Logic.Condition;
import com.agifans.agile.agilib.Logic.IfAction;
import com.agifans.agile.agilib.Logic.NotCondition;
import com.agifans.agile.agilib.Logic.OrCondition;
'''
if text.count(package_anchor) != 1:
    raise RuntimeError('SceneMaskRuntime package anchor not found')
text = text.replace(package_anchor, imports, 1)
fall_constant = '    public static final int FALL = 4;\n'
if text.count(fall_constant) != 1:
    raise RuntimeError('SceneMaskRuntime FALL constant not found')
text = text.replace(fall_constant, fall_constant + '    public static final int SCRIPT_FALL = 5;\n', 1)

anchor = '''    public static boolean unifiedControlReady(GameState state) {
'''
helpers = r'''    private static final Set<Integer> SCRIPT_DANGER_CONDITIONS = new HashSet<Integer>();
    private static int scriptDangerRoom = -1;

    private static int scriptDangerKey(Condition condition) {
        return ((condition.logic.index & 0xFF) << 16) | (condition.address & 0xFFFF);
    }

    private static boolean isEgoPositionCondition(Condition condition) {
        int opcode = condition.operation.opcode;
        if (opcode != 11 && opcode != 16 && opcode != 17 && opcode != 18) return false;
        return condition.operands.size() >= 5 && condition.operands.get(0).asByte() == 0;
    }

    private static void collectPositiveEgoPositionConditions(
            List<Condition> conditions, List<Condition> out) {
        for (Condition condition : conditions) {
            if (condition instanceof NotCondition) continue;
            if (condition instanceof OrCondition) {
                collectPositiveEgoPositionConditions(condition.operands.get(0).asConditions(), out);
                continue;
            }
            if (isEgoPositionCondition(condition)) out.add(condition);
        }
    }

    private static boolean messageLooksDangerous(Logic logic, Action action) {
        int opcode = action.operation.opcode;
        int messageNum = -1;
        if (opcode == 101 && action.operands.size() >= 1) {
            messageNum = action.operands.get(0).asByte();
        } else if (opcode == 103 && action.operands.size() >= 3) {
            messageNum = action.operands.get(2).asByte();
        }
        if (messageNum <= 0 || messageNum >= logic.messages.size()) return false;
        String message = logic.messages.get(messageNum);
        if (message == null) return false;
        String lower = message.toLowerCase();
        return lower.contains("fall") || lower.contains("fell")
                || lower.contains("drown") || lower.contains("dead")
                || lower.contains("died") || lower.contains("death")
                || lower.contains("killed") || lower.contains("plunge")
                || lower.contains("splash") || lower.contains("bridge");
    }

    private static boolean actionChangesEgoMotion(Action action) {
        int opcode = action.operation.opcode;
        if (action.operands.size() < 1) return false;
        boolean egoOperation = opcode == 35 || opcode == 36 || opcode == 40
                || opcode == 41 || opcode == 42 || opcode == 43 || opcode == 44
                || opcode == 45 || opcode == 46 || opcode == 47 || opcode == 48
                || opcode == 77 || opcode == 78 || opcode == 81 || opcode == 82;
        return egoOperation && action.operands.get(0).asByte() == 0;
    }

    private static boolean ifBodyLooksLikeScriptDanger(
            Logic logic, int actionIndex, IfAction ifAction) {
        int end = Math.min(ifAction.getDestinationActionIndex(), logic.actions.size());
        boolean changesRoom = false;
        boolean programControl = false;
        boolean egoMotion = false;
        boolean dangerText = false;
        for (int i = actionIndex + 1; i < end; i++) {
            Action action = logic.actions.get(i);
            int opcode = action.operation.opcode;
            if (opcode == 18 || opcode == 19) changesRoom = true;
            if (opcode == 131) programControl = true;
            if (actionChangesEgoMotion(action)) egoMotion = true;
            if (messageLooksDangerous(logic, action)) dangerText = true;
        }
        return !changesRoom && (dangerText || (programControl && egoMotion));
    }

    private static void rebuildScriptDangerConditions(GameState state) {
        int room = state.getVar(Defines.CURROOM);
        if (scriptDangerRoom == room && !SCRIPT_DANGER_CONDITIONS.isEmpty()) return;
        scriptDangerRoom = room;
        SCRIPT_DANGER_CONDITIONS.clear();
        int[] logicNums = room == 0 ? new int[] { 0 } : new int[] { 0, room };
        for (int logicNum : logicNums) {
            if (logicNum < 0 || logicNum >= state.logics.length) continue;
            Logic logic = state.logics[logicNum];
            if (logic == null) continue;
            for (int i = 0; i < logic.actions.size(); i++) {
                Action action = logic.actions.get(i);
                if (!(action instanceof IfAction)) continue;
                IfAction ifAction = (IfAction)action;
                if (!ifBodyLooksLikeScriptDanger(logic, i, ifAction)) continue;
                java.util.ArrayList<Condition> positions = new java.util.ArrayList<Condition>();
                collectPositiveEgoPositionConditions(
                        ifAction.operands.get(0).asConditions(), positions);
                for (Condition condition : positions) {
                    SCRIPT_DANGER_CONDITIONS.add(scriptDangerKey(condition));
                }
            }
        }
    }

    private static void paintScriptDangerCondition(VariableData data, Condition condition) {
        int x1 = condition.operands.get(1).asByte();
        int y1 = condition.operands.get(2).asByte();
        int x2 = condition.operands.get(3).asByte();
        int y2 = condition.operands.get(4).asByte();
        int left = Math.max(0, Math.min(x1, x2));
        int right = Math.min(159, Math.max(x1, x2));
        int top = Math.max(0, Math.min(y1, y2));
        int bottom = Math.min(167, Math.max(y1, y2));
        for (int y = top; y <= bottom; y++) {
            for (int x = left; x <= right; x++) {
                data.setSceneMaskBit(SCRIPT_FALL, x, y, true);
            }
        }
    }

    public static void ensureScriptDangerSeed(GameState state) {
        if (state == null || !editorOwnsRoom(state)) return;
        VariableData data = state.getVariableData();
        int room = state.getVar(Defines.CURROOM);
        rebuildScriptDangerConditions(state);
        if (data.getSceneScriptDangerSeedState() != -(room + 1)) return;
        data.clearSceneMaskLayer(SCRIPT_FALL);
        int[] logicNums = room == 0 ? new int[] { 0 } : new int[] { 0, room };
        for (int logicNum : logicNums) {
            if (logicNum < 0 || logicNum >= state.logics.length) continue;
            Logic logic = state.logics[logicNum];
            if (logic == null) continue;
            for (int i = 0; i < logic.actions.size(); i++) {
                Action action = logic.actions.get(i);
                if (!(action instanceof IfAction)) continue;
                IfAction ifAction = (IfAction)action;
                if (!ifBodyLooksLikeScriptDanger(logic, i, ifAction)) continue;
                java.util.ArrayList<Condition> positions = new java.util.ArrayList<Condition>();
                collectPositiveEgoPositionConditions(
                        ifAction.operands.get(0).asConditions(), positions);
                for (Condition condition : positions) paintScriptDangerCondition(data, condition);
            }
        }
        data.setSceneScriptDangerSeedState(room + 1);
    }

    public static boolean filterScriptDangerPositionCondition(
            GameState state, Condition condition, boolean originalResult) {
        if (!originalResult || state == null || !isEgoPositionCondition(condition)) {
            return originalResult;
        }
        int room = state.getVar(Defines.CURROOM);
        VariableData data = state.getVariableData();
        if (data.getSceneScriptDangerSeedState() != (room + 1)) return originalResult;
        rebuildScriptDangerConditions(state);
        if (!SCRIPT_DANGER_CONDITIONS.contains(scriptDangerKey(condition))) return originalResult;
        AnimatedObject ego = state.animatedObjects[0];
        int x = condition.operation.opcode == 18
                ? ego.x + ego.xSize() - 1
                : ego.x + (ego.xSize() / 2);
        int y = ego.y;
        if (x < 0 || x >= 160 || y < 0 || y >= 168) return originalResult;
        return data.getSceneMaskBit(SCRIPT_FALL, x, y);
    }

    public static boolean unifiedControlReady(GameState state) {
'''
if text.count(anchor) != 1:
    raise RuntimeError('SceneMaskRuntime unifiedControlReady anchor not found')
text = text.replace(anchor, helpers, 1)
old = '''        ensureUnifiedControlSeed(state);
        VariableData data = state.getVariableData();
'''
new = '''        ensureUnifiedControlSeed(state);
        ensureScriptDangerSeed(state);
        VariableData data = state.getVariableData();
'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskRuntime updateOccluder seed anchor not found')
text = text.replace(old, new, 1)
p.write_text(text)

# Hook condition evaluation so an erased SCRIPT_FALL pixel suppresses only the
# matching original scripted position condition.
p = root / 'core/src/main/java/com/agifans/agile/Commands.java'
text = p.read_text()
old = '''        return result;
    }

    /**
     * Executes the given Action command.
'''
new = '''        result = SceneMaskRuntime.filterScriptDangerPositionCondition(
                state, condition, result);
        return result;
    }

    /**
     * Executes the given Action command.
'''
if text.count(old) != 1:
    raise RuntimeError('Commands condition return anchor not found')
p.write_text(text.replace(old, new, 1))

# Editor integration. SCRIPT_FALL renders together with FALL. FALL erase also
# erases SCRIPT_FALL, making the original scripted trigger suppressible.
p = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = p.read_text()
repls = [
    ('    private static final int FALL = 4;\n',
     '    private static final int FALL = 4;\n    private static final int SCRIPT_FALL = 5;\n',
     'editor FALL constant'),
    ('    private final boolean[][][] masks = new boolean[5][HEIGHT][WIDTH];\n',
     '    private final boolean[][][] masks = new boolean[6][HEIGHT][WIDTH];\n',
     'editor mask array'),
    ('    private final boolean[] layerVisible = new boolean[] { true, true, true, true, true };\n',
     '    private final boolean[] layerVisible = new boolean[] { true, true, true, true, true, true };\n',
     'editor visibility array'),
    ('''    private boolean waitingForControlSeed;
    private boolean moveMode;
''',
     '''    private boolean waitingForControlSeed;
    private boolean waitingForScriptDangerSeed;
    private boolean moveMode;
''',
     'editor seed fields'),
    ('        String savedFall = prefs.getString(key("fall"), "");\n',
     '        String savedFall = prefs.getString(key("fall"), "");\n        String savedScriptFall = prefs.getString(key("scriptFall"), "");\n',
     'editor saved FALL'),
    ('''        decode(savedFall, masks[FALL]);
        fallActive = prefs.getBoolean(key("fallActive"), false);
''',
     '''        decode(savedFall, masks[FALL]);
        decode(savedScriptFall, masks[SCRIPT_FALL]);
        fallActive = prefs.getBoolean(key("fallActive"), false);
''',
     'editor FALL decode'),
    ('''        prefs.putString(key("fall"), encode(masks[FALL]));
        prefs.putBoolean(key("fallActive"), fallActive);
''',
     '''        prefs.putString(key("fall"), encode(masks[FALL]));
        prefs.putString(key("scriptFall"), encode(masks[SCRIPT_FALL]));
        prefs.putBoolean(key("fallActive"), fallActive);
''',
     'editor FALL save'),
]
for old, new, label in repls:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)
loop = '        for (int layer = 0; layer < 5; layer++) {\n'
count = text.count(loop)
if count != 2:
    raise RuntimeError(f'editor five-layer loops: expected 2, found {count}')
text = text.replace(loop, '        for (int layer = 0; layer < 6; layer++) {\n')

old = '''        }
        dirty = false;
    }

    private void adoptUnifiedControlSeedIfReady() {
'''
new = '''        }
        boolean scriptDangerSaved = prefs.getBoolean(key("scriptDangerV1"), false);
        if (scriptDangerSaved) {
            waitingForScriptDangerSeed = false;
            data.setSceneScriptDangerSeedState(room + 1);
        } else {
            waitingForScriptDangerSeed = true;
            data.setSceneScriptDangerSeedState(-(room + 1));
        }
        dirty = false;
    }

    private void adoptScriptDangerSeedIfReady() {
        if (!waitingForScriptDangerSeed
                || data.getSceneScriptDangerSeedState() != (room + 1)) return;
        for (int y = 0; y < HEIGHT; y++) {
            for (int x = 0; x < WIDTH; x++) {
                masks[SCRIPT_FALL][y][x] = data.getSceneMaskBit(SCRIPT_FALL, x, y);
            }
        }
        waitingForScriptDangerSeed = false;
        prefs.putBoolean(key("scriptDangerV1"), true);
        dirty = true;
        saveRoom();
        notice("SCRIPTED FALL ZONES IMPORTED");
    }

    private void adoptUnifiedControlSeedIfReady() {
'''
if text.count(old) != 1:
    raise RuntimeError('editor ensureRoom migration tail not found')
text = text.replace(old, new, 1)
old = '''        adoptUnifiedControlSeedIfReady();
        if (!data.getSceneMaskEnabled() && !paintMode) return;
'''
new = '''        adoptUnifiedControlSeedIfReady();
        adoptScriptDangerSeedIfReady();
        if (!data.getSceneMaskEnabled() && !paintMode) return;
'''
if text.count(old) != 1:
    raise RuntimeError('editor render migration anchor not found')
text = text.replace(old, new, 1)
old = '''                masks[layer][y][x] = value;
                data.setSceneMaskBit(layer, x, y, value);
'''
new = '''                masks[layer][y][x] = value;
                data.setSceneMaskBit(layer, x, y, value);
                if (erase && layer == FALL) {
                    masks[SCRIPT_FALL][y][x] = false;
                    data.setSceneMaskBit(SCRIPT_FALL, x, y, false);
                }
'''
if text.count(old) != 1:
    raise RuntimeError('editor unified paint write anchor not found')
text = text.replace(old, new, 1)
old = '''                if (layerVisible[FALL]) drawMaskRuns(batch, masks[FALL], new Color(1f, 0.08f, 0.62f, 0.52f));
'''
new = '''                if (layerVisible[FALL]) {
                    drawMaskRuns(batch, masks[SCRIPT_FALL], new Color(1f, 0.48f, 0.05f, 0.48f));
                    drawMaskRuns(batch, masks[FALL], new Color(1f, 0.08f, 0.62f, 0.52f));
                }
'''
if text.count(old) != 1:
    raise RuntimeError('editor FALL overlay anchor not found')
text = text.replace(old, new, 1)
old = '''        if (!waitingForControlSeed && data.getSceneControlSeedState() == (room + 1)) {
            prefs.putBoolean(key("unifiedControlV1"), true);
        }
'''
new = '''        if (!waitingForControlSeed && data.getSceneControlSeedState() == (room + 1)) {
            prefs.putBoolean(key("unifiedControlV1"), true);
        }
        if (!waitingForScriptDangerSeed
                && data.getSceneScriptDangerSeedState() == (room + 1)) {
            prefs.putBoolean(key("scriptDangerV1"), true);
        }
'''
if text.count(old) != 1:
    raise RuntimeError('editor unified save marker anchor not found')
text = text.replace(old, new, 1)
old = '''                + ",\\\"fall\\\":\\\"" + encode(masks[FALL]) + "\\\""
                + ",\\\"fallActive\\\":" + fallActive + "}";
'''
new = '''                + ",\\\"fall\\\":\\\"" + encode(masks[FALL]) + "\\\""
                + ",\\\"scriptFall\\\":\\\"" + encode(masks[SCRIPT_FALL]) + "\\\""
                + ",\\\"fallActive\\\":" + fallActive + "}";
'''
if text.count(old) != 1:
    raise RuntimeError('editor FALL export anchor not found')
text = text.replace(old, new, 1)
old = '5 FALL 6 MOVE | V hide fall'
if text.count(old) != 1:
    raise RuntimeError('editor FALL HUD help anchor not found')
text = text.replace(old, '5 FALL 6 MOVE | orange=script fall | V hide fall', 1)
p.write_text(text)
print('Scripted fall zones installed: script danger rectangles visible in FALL and erasable/suppressible')
