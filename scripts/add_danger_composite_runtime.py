#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_danger_composite_runtime.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()


def one(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    path.write_text(text.replace(old, new, 1))

runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()

# Death/fall handlers frequently print the death text and then new.room(99).
# The original scripted-danger scanner rejected *every* IF that changed rooms,
# which filtered out exactly these legitimate death zones (including the castle
# bridge/moat edge). A room change is only disqualifying for heuristic motion
# sequences; explicit danger/death text is strong enough evidence on its own.
old = '        return !roomChange && (text || (programControl && motion));\n'
new = '        return text || (!roomChange && programControl && motion);\n'
if text.count(old) != 1:
    raise RuntimeError(f'dangerIf room-change rule: expected 1 match, found {text.count(old)}')
text = text.replace(old, new, 1)

# Track whether this room contains an explicit deadly ONWATER branch. DANGER can
# then show WATER only when the room logic actually treats being in water as a
# death/fall hazard, rather than labeling every harmless lake as lethal.
old = '''    private static final Set<Integer> SCRIPT_DANGER = new HashSet<Integer>();
    private static int scriptDangerRoom = -1;
'''
new = '''    private static final Set<Integer> SCRIPT_DANGER = new HashSet<Integer>();
    private static int scriptDangerRoom = -1;
    private static int deadlyWaterRoom = -1;
    private static boolean deadlyWater;
'''
if text.count(old) != 1:
    raise RuntimeError('script danger fields anchor not found')
text = text.replace(old, new, 1)

old = '''    private static boolean dangerText(Logic logic, Action a) {
'''
helper = '''    private static boolean hasPositiveFlag(List<Condition> src, int flag) {
        for (Condition c : src) {
            if (c instanceof NotCondition) continue;
            if (c instanceof OrCondition) {
                if (hasPositiveFlag(c.operands.get(0).asConditions(), flag)) return true;
                continue;
            }
            if (c.operation.opcode == 7 && c.operands.size() > 0
                    && c.operands.get(0).asByte() == flag) return true;
        }
        return false;
    }

    private static boolean dangerText(Logic logic, Action a) {
'''
if text.count(old) != 1:
    raise RuntimeError('dangerText helper anchor not found')
text = text.replace(old, helper, 1)

# Broaden text recognition just enough to catch Sierra's many death phrasings.
old = '''        return s.contains("fall") || s.contains("fell") || s.contains("drown")
                || s.contains("dead") || s.contains("died") || s.contains("death")
                || s.contains("killed") || s.contains("plunge") || s.contains("splash")
                || s.contains("bridge");
'''
new = '''        return s.contains("fall") || s.contains("fell") || s.contains("drown")
                || s.contains("dead") || s.contains("died") || s.contains("death")
                || s.contains("killed") || s.contains("plunge") || s.contains("splash")
                || s.contains("bridge") || s.contains("moat") || s.contains("alligator")
                || s.contains("current") || s.contains("slip down") || s.contains("false move");
'''
if text.count(old) != 1:
    raise RuntimeError('dangerText vocabulary anchor not found')
text = text.replace(old, new, 1)

old = '''        SCRIPT_DANGER.clear();
        scriptDangerRoom = room;
        VariableData data = state.getVariableData();
'''
new = '''        SCRIPT_DANGER.clear();
        scriptDangerRoom = room;
        deadlyWaterRoom = room;
        deadlyWater = false;
        VariableData data = state.getVariableData();
'''
if text.count(old) != 1:
    raise RuntimeError('scanDanger reset anchor not found')
text = text.replace(old, new, 1)

old = '''                Action a = logic.actions.get(i);
                if (!(a instanceof IfAction) || !dangerIf(logic, i, (IfAction)a)) continue;
                java.util.ArrayList<Condition> list = new java.util.ArrayList<Condition>();
                addPos(((IfAction)a).operands.get(0).asConditions(), list);
'''
new = '''                Action a = logic.actions.get(i);
                if (!(a instanceof IfAction) || !dangerIf(logic, i, (IfAction)a)) continue;
                IfAction danger = (IfAction)a;
                List<Condition> conditions = danger.operands.get(0).asConditions();
                if (hasPositiveFlag(conditions, Defines.ONWATER)) deadlyWater = true;
                java.util.ArrayList<Condition> list = new java.util.ArrayList<Condition>();
                addPos(conditions, list);
'''
if text.count(old) != 1:
    raise RuntimeError('scanDanger IF anchor not found')
text = text.replace(old, new, 1)

anchor = '''    public static boolean filterScriptDangerPositionCondition(
'''
method = '''    public static boolean roomHasDeadlyWater(GameState state) {
        if (state == null) return false;
        scanDanger(state, false);
        return deadlyWaterRoom == state.getVar(Defines.CURROOM) && deadlyWater;
    }

    public static boolean filterScriptDangerPositionCondition(
'''
if text.count(anchor) != 1:
    raise RuntimeError('roomHasDeadlyWater insertion anchor not found')
text = text.replace(anchor, method, 1)
runtime.write_text(text)

editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

old = '    private boolean outlineMode;\n'
new = '    private boolean outlineMode;\n    private boolean dangerView;\n'
if text.count(old) != 1:
    raise RuntimeError('editor outlineMode field anchor not found')
text = text.replace(old, new, 1)

# DANGER is a read-only composite view on key 7. It cannot accidentally paint.
key_anchor = '''        if (!paintMode) return false;

        if (keycode == Input.Keys.U) {
'''
key_repl = '''        if (!paintMode) return false;

        if (keycode == Input.Keys.NUM_7) {
            dangerView = !dangerView;
            inspectMode = dangerView;
            moveMode = false;
            eraser = false;
            movingObject = false;
            if (dangerView) {
                for (int i = 0; i < layerVisible.length; i++) layerVisible[i] = false;
                layerVisible[FALL] = true;
                layerVisible[SCRIPT_FALL] = true;
                notice("DANGER VIEW - READ ONLY");
            } else {
                notice("DANGER VIEW OFF");
            }
            return true;
        }

        if (keycode == Input.Keys.U) {
'''
if text.count(key_anchor) != 1:
    raise RuntimeError('editor keyDown danger anchor not found')
text = text.replace(key_anchor, key_repl, 1)

# Any explicit paint/sprite mode exits DANGER.
for old_mode in [
    'inspectMode = false; moveMode = false; mode = OCCLUDER;',
    'inspectMode = false; moveMode = false; mode = COLLISION;',
    'inspectMode = false; moveMode = false; mode = BEHIND;',
    'inspectMode = false; moveMode = false; mode = WATER;',
    'inspectMode = false; moveMode = false; mode = FALL;',
]:
    if text.count(old_mode) != 1:
        raise RuntimeError(f'paint-mode danger exit anchor missing: {old_mode}')
    text = text.replace(old_mode, 'dangerView = false; ' + old_mode, 1)

old = '''        if (keycode == Input.Keys.I) {
            inspectMode = !inspectMode;
'''
new = '''        if (keycode == Input.Keys.I) {
            dangerView = false;
            inspectMode = !inspectMode;
'''
if text.count(old) != 1:
    raise RuntimeError('inspect danger exit anchor not found')
text = text.replace(old, new, 1)

old = '''        else if (keycode == Input.Keys.NUM_6) {
            inspectMode = false;
            moveMode = true;
'''
new = '''        else if (keycode == Input.Keys.NUM_6) {
            dangerView = false;
            inspectMode = false;
            moveMode = true;
'''
if text.count(old) != 1:
    raise RuntimeError('sprite move danger exit anchor not found')
text = text.replace(old, new, 1)

# Suppress normal overlays in DANGER and draw only actual hazard sources:
# deadly water (cyan), scripted position hazards (orange), editable FALL (pink).
normal_draws = [
    ('                if (layerVisible[OCCLUDER])', '                if (!dangerView && layerVisible[OCCLUDER])'),
    ('                if (layerVisible[COLLISION])', '                if (!dangerView && layerVisible[COLLISION])'),
    ('                if (layerVisible[BEHIND])', '                if (!dangerView && layerVisible[BEHIND])'),
    ('                if (layerVisible[WATER])', '                if (!dangerView && layerVisible[WATER])'),
    ('                if (layerVisible[FALL]) {', '                if (!dangerView && layerVisible[FALL]) {'),
]
for old_draw, new_draw in normal_draws:
    if text.count(old_draw) != 1:
        raise RuntimeError(f'normal overlay danger guard missing: {old_draw}')
    text = text.replace(old_draw, new_draw, 1)

anchor = '''                if (!dangerView && layerVisible[FALL]) {
                    rebuildScriptFallDisplay();
                    drawMaskRuns(batch, scriptFallDisplay, new Color(1f, 0.48f, 0.05f, 0.55f));
                    drawMaskRuns(batch, masks[FALL], new Color(1f, 0.08f, 0.62f, 0.52f));
                }
'''
repl = anchor + '''                if (dangerView) {
                    rebuildScriptFallDisplay();
                    if (SceneMaskRuntime.roomHasDeadlyWater(state)) {
                        drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.58f));
                    }
                    drawMaskRuns(batch, scriptFallDisplay, new Color(1f, 0.48f, 0.05f, 0.68f));
                    drawMaskRuns(batch, masks[FALL], new Color(1f, 0.08f, 0.62f, 0.66f));
                }
'''
if text.count(anchor) != 1:
    raise RuntimeError('danger composite render anchor not found')
text = text.replace(anchor, repl, 1)

editor.write_text(text)
print('Composite DANGER runtime installed: death room-changes count as scripted hazards; deadly WATER + scripted + editable FALL render read-only on key 7')
