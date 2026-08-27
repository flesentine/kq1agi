#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scripted_fall_zones.py /path/to/agile-gdx')
root = Path(sys.argv[1]).resolve()

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {n}')
    return text.replace(old, new, 1)

# Shared API + browser transport for a sixth, debug-only SCRIPT_FALL bit plane.
p = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
t = p.read_text()
t = one(t,
'''    default int getSceneControlSeedState() { return 0; }
    default void setSceneControlSeedState(int value) { }
    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }
''',
'''    default int getSceneControlSeedState() { return 0; }
    default void setSceneControlSeedState(int value) { }
    default int getSceneScriptDangerSeedState() { return 0; }
    default void setSceneScriptDangerSeedState(int value) { }
    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }
''', 'VariableData seed API')
p.write_text(t)

p = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
t = p.read_text()
t = one(t, '    private static final int SCENE_MASK_LAYERS = 5;\n',
        '    private static final int SCENE_MASK_LAYERS = 6;\n', 'GWT layer count')
t = one(t, '    private static final int SCENE_CONTROL_SEED_STATE = 4983;\n',
'''    private static final int SCENE_CONTROL_SEED_STATE = 4983;
    private static final int SCENE_SCRIPT_FALL_BITS = 4984;
    private static final int SCENE_SCRIPT_DANGER_SEED_STATE = 5824;
''', 'GWT script fall constants')
if t.count('Defines.NUMVARS + Defines.NUMFLAGS + 4472') != 2:
    raise RuntimeError('GWT capacity markers not found')
t = t.replace('Defines.NUMVARS + Defines.NUMFLAGS + 4472',
              'Defines.NUMVARS + Defines.NUMFLAGS + 5313')
t = one(t,
'''    @Override
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
''', 'GWT seed methods')
t = one(t,
'''        int base = (layer == 4)
                ? SCENE_MASK_FALL_BITS
                : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);
''',
'''        int base = (layer == 4) ? SCENE_MASK_FALL_BITS
                : (layer == 5) ? SCENE_SCRIPT_FALL_BITS
                : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);
''', 'GWT mask index')
t = one(t,
'''        int start = (layer == 4)
                ? SCENE_MASK_FALL_BITS
                : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);
''',
'''        int start = (layer == 4) ? SCENE_MASK_FALL_BITS
                : (layer == 5) ? SCENE_SCRIPT_FALL_BITS
                : SCENE_MASK_BITS + (layer * SCENE_MASK_WORDS);
''', 'GWT clear index')
p.write_text(t)

# Runtime static analysis: find ego position tests whose IF body looks like a
# fall/death sequence. We deliberately reject any body that changes rooms.
p = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
t = p.read_text()
t = one(t, 'package com.agifans.agile;\n',
'''package com.agifans.agile;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import com.agifans.agile.agilib.Logic;
import com.agifans.agile.agilib.Logic.Action;
import com.agifans.agile.agilib.Logic.Condition;
import com.agifans.agile.agilib.Logic.IfAction;
import com.agifans.agile.agilib.Logic.NotCondition;
import com.agifans.agile.agilib.Logic.OrCondition;
''', 'runtime imports')
t = one(t, '    public static final int FALL = 4;\n',
        '    public static final int FALL = 4;\n    public static final int SCRIPT_FALL = 5;\n',
        'runtime SCRIPT_FALL constant')
anchor = '    public static boolean unifiedControlReady(GameState state) {\n'
helpers = r'''    private static final Set<Integer> SCRIPT_DANGER = new HashSet<Integer>();
    private static int scriptDangerRoom = -1;

    private static int dangerKey(Condition c) {
        return ((c.logic.index & 0xFF) << 16) | (c.address & 0xFFFF);
    }

    private static boolean egoPos(Condition c) {
        int op = c.operation.opcode;
        return (op == 11 || op == 16 || op == 17 || op == 18)
                && c.operands.size() >= 5 && c.operands.get(0).asByte() == 0;
    }

    private static void addPos(List<Condition> src, List<Condition> out) {
        for (Condition c : src) {
            if (c instanceof NotCondition) continue;
            if (c instanceof OrCondition) {
                addPos(c.operands.get(0).asConditions(), out);
            } else if (egoPos(c)) {
                out.add(c);
            }
        }
    }

    private static boolean dangerText(Logic logic, Action a) {
        int msg = -1;
        if (a.operation.opcode == 101 && a.operands.size() > 0) msg = a.operands.get(0).asByte();
        if (a.operation.opcode == 103 && a.operands.size() > 2) msg = a.operands.get(2).asByte();
        if (msg <= 0 || msg >= logic.messages.size() || logic.messages.get(msg) == null) return false;
        String s = logic.messages.get(msg).toLowerCase();
        return s.contains("fall") || s.contains("fell") || s.contains("drown")
                || s.contains("dead") || s.contains("died") || s.contains("death")
                || s.contains("killed") || s.contains("plunge") || s.contains("splash")
                || s.contains("bridge");
    }

    private static boolean egoMotion(Action a) {
        if (a.operands.size() == 0) return false;
        int op = a.operation.opcode;
        boolean motion = op == 35 || op == 36 || op == 40 || op == 41 || op == 42
                || op == 43 || op == 44 || op == 45 || op == 46 || op == 47 || op == 48
                || op == 77 || op == 78 || op == 81 || op == 82;
        return motion && a.operands.get(0).asByte() == 0;
    }

    private static boolean dangerIf(Logic logic, int index, IfAction iff) {
        int end = Math.min(iff.getDestinationActionIndex(), logic.actions.size());
        boolean roomChange = false, programControl = false, motion = false, text = false;
        for (int i = index + 1; i < end; i++) {
            Action a = logic.actions.get(i);
            int op = a.operation.opcode;
            if (op == 18 || op == 19) roomChange = true;
            if (op == 131) programControl = true;
            if (egoMotion(a)) motion = true;
            if (dangerText(logic, a)) text = true;
        }
        return !roomChange && (text || (programControl && motion));
    }

    private static void scanDanger(GameState state, boolean paint) {
        int room = state.getVar(Defines.CURROOM);
        if (!paint && scriptDangerRoom == room && !SCRIPT_DANGER.isEmpty()) return;
        SCRIPT_DANGER.clear();
        scriptDangerRoom = room;
        VariableData data = state.getVariableData();
        int[] nums = room == 0 ? new int[] { 0 } : new int[] { 0, room };
        for (int n : nums) {
            if (n < 0 || n >= state.logics.length || state.logics[n] == null) continue;
            Logic logic = state.logics[n];
            for (int i = 0; i < logic.actions.size(); i++) {
                Action a = logic.actions.get(i);
                if (!(a instanceof IfAction) || !dangerIf(logic, i, (IfAction)a)) continue;
                java.util.ArrayList<Condition> list = new java.util.ArrayList<Condition>();
                addPos(((IfAction)a).operands.get(0).asConditions(), list);
                for (Condition c : list) {
                    SCRIPT_DANGER.add(dangerKey(c));
                    if (!paint) continue;
                    int x1 = c.operands.get(1).asByte(), y1 = c.operands.get(2).asByte();
                    int x2 = c.operands.get(3).asByte(), y2 = c.operands.get(4).asByte();
                    int l = Math.max(0, Math.min(x1, x2)), r = Math.min(159, Math.max(x1, x2));
                    int top = Math.max(0, Math.min(y1, y2)), bot = Math.min(167, Math.max(y1, y2));
                    for (int y = top; y <= bot; y++) for (int x = l; x <= r; x++)
                        data.setSceneMaskBit(SCRIPT_FALL, x, y, true);
                }
            }
        }
    }

    public static void ensureScriptDangerSeed(GameState state) {
        if (state == null || !editorOwnsRoom(state)) return;
        VariableData data = state.getVariableData();
        int room = state.getVar(Defines.CURROOM);
        if (data.getSceneScriptDangerSeedState() != -(room + 1)) {
            scanDanger(state, false);
            return;
        }
        data.clearSceneMaskLayer(SCRIPT_FALL);
        scanDanger(state, true);
        data.setSceneScriptDangerSeedState(room + 1);
    }

    public static boolean filterScriptDangerPositionCondition(
            GameState state, Condition c, boolean result) {
        if (!result || state == null || !egoPos(c)) return result;
        int room = state.getVar(Defines.CURROOM);
        VariableData data = state.getVariableData();
        if (data.getSceneScriptDangerSeedState() != room + 1) return result;
        scanDanger(state, false);
        if (!SCRIPT_DANGER.contains(dangerKey(c))) return result;
        AnimatedObject ego = state.animatedObjects[0];
        int x = c.operation.opcode == 18 ? ego.x + ego.xSize() - 1 : ego.x + ego.xSize() / 2;
        int y = ego.y;
        return x < 0 || x >= 160 || y < 0 || y >= 168
                ? result : data.getSceneMaskBit(SCRIPT_FALL, x, y);
    }

'''
if t.count(anchor) != 1:
    raise RuntimeError('runtime unifiedControlReady anchor not found')
t = t.replace(anchor, helpers + anchor, 1)
t = one(t,
'''        ensureUnifiedControlSeed(state);
        VariableData data = state.getVariableData();
''',
'''        ensureUnifiedControlSeed(state);
        ensureScriptDangerSeed(state);
        VariableData data = state.getVariableData();
''', 'runtime seed call')
p.write_text(t)

# Every AGI condition still evaluates normally. Only after a known danger position
# test returns true do we require its SCRIPT_FALL pixel to remain painted.
p = root / 'core/src/main/java/com/agifans/agile/Commands.java'
t = p.read_text()
t = one(t,
'''        return result;
    }

    /**
     * Executes the given Action command.
''',
'''        result = SceneMaskRuntime.filterScriptDangerPositionCondition(state, condition, result);
        return result;
    }

    /**
     * Executes the given Action command.
''', 'Commands condition hook')
p.write_text(t)

# Editor: keep SCRIPT_FALL as a hidden sixth plane rendered under FALL in orange.
# Its exact pixels continue to control gameplay. The debug view expands them by
# two AGI pixels in every direction so tiny one-pixel Sierra tests are legible.
p = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
t = p.read_text()
t = one(t, '    private static final int FALL = 4;\n',
        '    private static final int FALL = 4;\n    private static final int SCRIPT_FALL = 5;\n    private static final int SCRIPT_FALL_DISPLAY_RADIUS = 2;\n',
        'editor constant')
t = one(t, '    private final boolean[][][] masks = new boolean[5][HEIGHT][WIDTH];\n',
        '    private final boolean[][][] masks = new boolean[6][HEIGHT][WIDTH];\n    private final boolean[][] scriptFallDisplay = new boolean[HEIGHT][WIDTH];\n',
        'editor mask count')
t = one(t,
        '    private final boolean[] layerVisible = new boolean[] { true, true, true, true, true };\n',
        '    private final boolean[] layerVisible = new boolean[] { true, true, true, true, true, true };\n',
        'editor visibility count')
t = one(t,
'''    private boolean waitingForControlSeed;
    private boolean moveMode;
''',
'''    private boolean waitingForControlSeed;
    private boolean waitingForScriptDangerSeed;
    private boolean moveMode;
''', 'editor wait field')
t = one(t, '        String savedFall = prefs.getString(key("fall"), "");\n',
        '        String savedFall = prefs.getString(key("fall"), "");\n'
        '        String savedScriptFall = prefs.getString(key("scriptFall"), "");\n',
        'editor scriptFall load')
t = one(t,
'''        decode(savedFall, masks[FALL]);
        fallActive = prefs.getBoolean(key("fallActive"), false);
''',
'''        decode(savedFall, masks[FALL]);
        decode(savedScriptFall, masks[SCRIPT_FALL]);
        fallActive = prefs.getBoolean(key("fallActive"), false);
''', 'editor scriptFall decode')
t = one(t,
'''        prefs.putString(key("fall"), encode(masks[FALL]));
        prefs.putBoolean(key("fallActive"), fallActive);
''',
'''        prefs.putString(key("fall"), encode(masks[FALL]));
        prefs.putString(key("scriptFall"), encode(masks[SCRIPT_FALL]));
        prefs.putBoolean(key("fallActive"), fallActive);
''', 'editor scriptFall save')
if t.count('        for (int layer = 0; layer < 5; layer++) {\n') != 2:
    raise RuntimeError('editor layer loops not found')
t = t.replace('        for (int layer = 0; layer < 5; layer++) {\n',
              '        for (int layer = 0; layer < 6; layer++) {\n')

needle = '        dirty = false;\n    }\n\n    private void adoptUnifiedControlSeedIfReady() {\n'
insert = '''        boolean scriptSaved = savedScriptFall.length() == HEIGHT * 40;
        waitingForScriptDangerSeed = !scriptSaved;
        data.setSceneScriptDangerSeedState(scriptSaved ? room + 1 : -(room + 1));
        dirty = false;
    }

    private void adoptScriptDangerSeedIfReady() {
        if (!waitingForScriptDangerSeed
                || data.getSceneScriptDangerSeedState() != room + 1) return;
        for (int y = 0; y < HEIGHT; y++) for (int x = 0; x < WIDTH; x++)
            masks[SCRIPT_FALL][y][x] = data.getSceneMaskBit(SCRIPT_FALL, x, y);
        waitingForScriptDangerSeed = false;
        dirty = true;
        saveRoom();
        notice("SCRIPTED FALL ZONES IMPORTED");
    }

    private void adoptUnifiedControlSeedIfReady() {
'''
t = one(t, needle, insert, 'editor script seed request')
call = '        adoptUnifiedControlSeedIfReady();\n'
if t.count(call) != 1:
    raise RuntimeError(f'editor unified adopt call: found {t.count(call)}')
t = t.replace(call, call + '        adoptScriptDangerSeedIfReady();\n', 1)

t = one(t,
'''                masks[layer][y][x] = value;
                data.setSceneMaskBit(layer, x, y, value);
''',
'''                masks[layer][y][x] = value;
                data.setSceneMaskBit(layer, x, y, value);
                if (erase && layer == FALL) {
                    // SCRIPT_FALL is displayed with a 2-pixel debug halo. Erasing
                    // anywhere in that visible halo clears nearby exact trigger
                    // pixels, but never enlarges the gameplay trigger itself.
                    for (int sy = Math.max(0, y - SCRIPT_FALL_DISPLAY_RADIUS);
                            sy <= Math.min(HEIGHT - 1, y + SCRIPT_FALL_DISPLAY_RADIUS); sy++) {
                        for (int sx = Math.max(0, x - SCRIPT_FALL_DISPLAY_RADIUS);
                                sx <= Math.min(WIDTH - 1, x + SCRIPT_FALL_DISPLAY_RADIUS); sx++) {
                            if (!masks[SCRIPT_FALL][sy][sx]) continue;
                            masks[SCRIPT_FALL][sy][sx] = false;
                            data.setSceneMaskBit(SCRIPT_FALL, sx, sy, false);
                        }
                    }
                }
''', 'editor erase scripted fall')

draw_anchor = '''                if (layerVisible[FALL]) drawMaskRuns(batch, masks[FALL], new Color(1f, 0.08f, 0.62f, 0.52f));
'''
draw_repl = '''                if (layerVisible[FALL]) {
                    rebuildScriptFallDisplay();
                    drawMaskRuns(batch, scriptFallDisplay, new Color(1f, 0.48f, 0.05f, 0.55f));
                    drawMaskRuns(batch, masks[FALL], new Color(1f, 0.08f, 0.62f, 0.52f));
                }
'''
t = one(t, draw_anchor, draw_repl, 'editor script fall draw')

method_anchor = '''    public void render(SpriteBatch batch) {
'''
method = '''    private void rebuildScriptFallDisplay() {
        for (int y = 0; y < HEIGHT; y++) {
            for (int x = 0; x < WIDTH; x++) scriptFallDisplay[y][x] = false;
        }
        for (int y = 0; y < HEIGHT; y++) {
            for (int x = 0; x < WIDTH; x++) {
                if (!masks[SCRIPT_FALL][y][x]) continue;
                int top = Math.max(0, y - SCRIPT_FALL_DISPLAY_RADIUS);
                int bottom = Math.min(HEIGHT - 1, y + SCRIPT_FALL_DISPLAY_RADIUS);
                int left = Math.max(0, x - SCRIPT_FALL_DISPLAY_RADIUS);
                int right = Math.min(WIDTH - 1, x + SCRIPT_FALL_DISPLAY_RADIUS);
                for (int yy = top; yy <= bottom; yy++) {
                    for (int xx = left; xx <= right; xx++) scriptFallDisplay[yy][xx] = true;
                }
            }
        }
    }

    public void render(SpriteBatch batch) {
'''
t = one(t, method_anchor, method, 'editor expanded script fall helper')
t = one(t, '5 FALL 6 MOVE | orange=script fall | V hide fall',
        '5 FALL 6 MOVE | orange=script fall expanded | V hide fall',
        'editor help')
p.write_text(t)

# Force browsers to fetch the updated runtime; gameplay trigger geometry is
# unchanged, only the orange debug representation is expanded.
web = root.parent / 'web/index.html'
if web.exists():
    wt = web.read_text()
    old_tag = "const BUILD_TAG = '20260827-script-fall-1';"
    new_tag = "const BUILD_TAG = '20260827-script-fall-visible-2';"
    if old_tag in wt:
        web.write_text(wt.replace(old_tag, new_tag, 1))
    elif new_tag not in wt:
        raise RuntimeError('web BUILD_TAG anchor not found')

print('Scripted FALL installed: orange script hazards use a 5x5 debug footprint; exact gameplay triggers remain unchanged')
