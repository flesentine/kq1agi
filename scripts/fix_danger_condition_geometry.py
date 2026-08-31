#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_danger_condition_geometry.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()


def one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Detector v3: preserve the geometry of nested AGI IF conditions.
#
# v2 walked the complete bytecode span of every IF, including nested IF bodies.
# If an outer condition said "Graham is near the bottom of the room" and an
# inner condition narrowed that to the bridge before showing the death text,
# both IFs were classified as deadly. The resulting union looked like a giant
# horizontal band plus the real bridge rectangle.
#
# v3 only considers actions that are DIRECT children of an IF when deciding
# whether that IF performs a death/fall sequence. When it paints the hazard, it
# intersects the spatial conditions of that IF with all enclosing IF conditions.
# OR groups are unioned only when every alternative is itself spatial; otherwise
# they are ignored as a spatial restriction rather than guessed.
# ---------------------------------------------------------------------------

old = '''    private static void addPos(List<Condition> src, List<Condition> out) {
        for (Condition c : src) {
            if (c instanceof NotCondition) continue;
            if (c instanceof OrCondition) {
                addPos(c.operands.get(0).asConditions(), out);
            } else if (egoPos(c)) {
                out.add(c);
            }
        }
    }
'''
new = old + r'''
    private static void clearSpatialMask(boolean[][] mask) {
        for (int y = 0; y < 168; y++)
            for (int x = 0; x < 160; x++) mask[y][x] = false;
    }

    private static void fillSpatialMask(boolean[][] mask) {
        for (int y = 0; y < 168; y++)
            for (int x = 0; x < 160; x++) mask[y][x] = true;
    }

    private static void orSpatialMask(boolean[][] into, boolean[][] add) {
        for (int y = 0; y < 168; y++)
            for (int x = 0; x < 160; x++) into[y][x] |= add[y][x];
    }

    private static void andSpatialMask(boolean[][] into, boolean[][] term) {
        for (int y = 0; y < 168; y++)
            for (int x = 0; x < 160; x++) into[y][x] &= term[y][x];
    }

    private static boolean spatialConditionMask(Condition c, boolean[][] out) {
        clearSpatialMask(out);
        if (c instanceof NotCondition) return false;
        if (c instanceof OrCondition) {
            List<Condition> alternatives = c.operands.get(0).asConditions();
            if (alternatives == null || alternatives.isEmpty()) return false;
            boolean any = false;
            for (Condition alternative : alternatives) {
                boolean[][] branch = new boolean[168][160];
                // An OR is a safe spatial restriction only when every branch is
                // spatial. A flag/non-position alternative could make the whole
                // OR true anywhere, so do not invent geometry in that case.
                if (!spatialConditionMask(alternative, branch)) return false;
                orSpatialMask(out, branch);
                any = true;
            }
            return any;
        }
        if (!egoPos(c)) return false;

        int x1 = c.operands.get(1).asByte(), y1 = c.operands.get(2).asByte();
        int x2 = c.operands.get(3).asByte(), y2 = c.operands.get(4).asByte();
        int l = Math.max(0, Math.min(x1, x2)), r = Math.min(159, Math.max(x1, x2));
        int top = Math.max(0, Math.min(y1, y2)), bot = Math.min(167, Math.max(y1, y2));
        if (l > r || top > bot) return false;
        for (int y = top; y <= bot; y++)
            for (int x = l; x <= r; x++) out[y][x] = true;
        return true;
    }

    private static boolean intersectSpatialConditions(
            List<Condition> conditions, boolean[][] composite) {
        boolean found = false;
        if (conditions == null) return false;
        for (Condition c : conditions) {
            boolean[][] term = new boolean[168][160];
            if (!spatialConditionMask(c, term)) continue;
            andSpatialMask(composite, term);
            found = true;
        }
        return found;
    }

    private static boolean paintDangerGeometry(
            GameState state, Logic logic, int ifIndex, boolean paint) {
        boolean[][] composite = new boolean[168][160];
        fillSpatialMask(composite);
        boolean foundSpatial = false;

        // Include the dangerous IF itself plus every enclosing IF in the same
        // logic. This preserves constructs such as:
        //   if (bottom band) { if (bridge x-range) { death... } }
        // as the INTERSECTION rather than two unrelated deadly rectangles.
        for (int i = 0; i <= ifIndex; i++) {
            Action candidate = logic.actions.get(i);
            if (!(candidate instanceof IfAction)) continue;
            IfAction owner = (IfAction)candidate;
            boolean ownsDanger = i == ifIndex
                    || (i < ifIndex && owner.getDestinationActionIndex() > ifIndex);
            if (!ownsDanger) continue;
            if (intersectSpatialConditions(owner.operands.get(0).asConditions(), composite))
                foundSpatial = true;
        }

        if (!foundSpatial || !paint) return foundSpatial;
        VariableData data = state.getVariableData();
        for (int y = 0; y < 168; y++)
            for (int x = 0; x < 160; x++)
                if (composite[y][x]) data.setSceneMaskBit(SCRIPT_FALL, x, y, true);
        return true;
    }
'''
one(old, new, 'spatial condition helpers')

old = '''    private static boolean dangerIf(Logic logic, int index, IfAction iff) {
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
        return text || (!roomChange && programControl && motion);
    }
'''
new = '''    private static boolean dangerIf(Logic logic, int index, IfAction iff) {
        int end = Math.min(iff.getDestinationActionIndex(), logic.actions.size());
        boolean roomChange = false, programControl = false, motion = false, text = false;
        for (int i = index + 1; i < end; i++) {
            Action a = logic.actions.get(i);
            if (a instanceof IfAction) {
                // A death inside a nested IF does not make this entire parent IF
                // deadly. Skip the child body; the child is evaluated separately
                // by scanDanger and will inherit this parent's spatial bounds.
                int nestedEnd = Math.min(((IfAction)a).getDestinationActionIndex(), end);
                if (nestedEnd > i + 1) {
                    i = nestedEnd - 1;
                    continue;
                }
            }
            int op = a.operation.opcode;
            if (op == 18 || op == 19) roomChange = true;
            if (op == 131) programControl = true;
            if (egoMotion(a)) motion = true;
            if (dangerText(logic, a)) text = true;
        }
        return text || (!roomChange && programControl && motion);
    }
'''
one(old, new, 'direct-child danger scan')

old = '''                java.util.ArrayList<Condition> list = new java.util.ArrayList<Condition>();
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
'''
new = '''                java.util.ArrayList<Condition> list = new java.util.ArrayList<Condition>();
                addPos(((IfAction)a).operands.get(0).asConditions(), list);
                for (Condition c : list) SCRIPT_DANGER.add(dangerKey(c));
                paintDangerGeometry(state, logic, i, paint);
'''
one(old, new, 'composite danger painting')

runtime.write_text(text)

# Force one clean reseed in every browser. Detector v2 caches contain the broad
# parent rectangles, so accepting them would make the code fix appear ineffective.
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()
replacements = [
    ('scriptDetectorVersion >= 2', 'scriptDetectorVersion >= 3'),
    ('prefs.putInteger(key("scriptFallDetectorVersion"), 2);',
     'prefs.putInteger(key("scriptFallDetectorVersion"), 3);'),
]
for old, new in replacements:
    count = text.count(old)
    if count < 1:
        raise RuntimeError(f'detector-v3 cache marker not found: {old}')
    text = text.replace(old, new)
editor.write_text(text)

print('DANGER detector v3 installed: nested IF hazards keep enclosing AND geometry; cached v2 masks are reseeded')
