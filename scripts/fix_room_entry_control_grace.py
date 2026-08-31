#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_room_entry_control_grace.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()


def one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


# Room changes place Graham on an outer screen edge. The replacement editable
# control map can legitimately differ from Sierra's old picture in the interior,
# but it must not turn a valid room-entry coordinate into WATER/FALL before Graham
# has even taken a step. Keep Sierra's original control semantics during the short
# edge-entry phase, then hand authority back to the editable map once ego is safely
# inside the new room.
constructor = '''    private SceneMaskRuntime() {\n    }\n\n'''
helpers = '''    private static final int ROOM_ENTRY_MARGIN_X = 10;\n    private static final int ROOM_ENTRY_MARGIN_Y = 8;\n    private static int roomEntryProtectionRoom = -1;\n    private static boolean roomEntryProtectionActive = false;\n\n    private SceneMaskRuntime() {\n    }\n\n    private static void refreshRoomEntryProtection(GameState state) {\n        if (state == null) return;\n\n        int room = state.getVar(Defines.CURROOM);\n        if (room != roomEntryProtectionRoom) {\n            roomEntryProtectionRoom = room;\n            roomEntryProtectionActive = true;\n\n            // ONWATER/HITSPEC describe the current coordinate. They must be\n            // recomputed in the new room rather than leaking across a room change.\n            state.setFlag(Defines.ONWATER, false);\n            state.setFlag(Defines.HITSPEC, false);\n        }\n\n        if (!roomEntryProtectionActive) return;\n        AnimatedObject ego = state.ego;\n        if (ego == null || !ego.drawn) return;\n\n        int width = Math.max(1, ego.xSize());\n        int left = ego.x;\n        int right = ego.x + width - 1;\n        int baseline = ego.y;\n\n        boolean clearOfHorizontalEntryEdges = left >= ROOM_ENTRY_MARGIN_X\n                && right <= (159 - ROOM_ENTRY_MARGIN_X);\n        boolean clearOfVerticalEntryEdges = baseline >= (state.horizon + ROOM_ENTRY_MARGIN_Y)\n                && baseline <= (167 - ROOM_ENTRY_MARGIN_Y);\n\n        if (clearOfHorizontalEntryEdges && clearOfVerticalEntryEdges) {\n            roomEntryProtectionActive = false;\n        }\n    }\n\n    public static boolean roomEntryProtectionActive(GameState state) {\n        refreshRoomEntryProtection(state);\n        return roomEntryProtectionActive;\n    }\n\n'''
one(constructor, helpers, 'SceneMaskRuntime constructor')

# During entry protection, use Sierra's original control pixel for WATER/FALL.
# This is the key fix for entering Room 1 from the right and instantly drowning.
effective_anchor = '''        if (objectNumber != 0 || !unifiedControlReady(state)) return legacyPriority;\n        if (x < 0 || x >= 160 || y < 0 || y >= 168) return legacyPriority;\n\n        VariableData data = state.getVariableData();\n'''
effective_repl = '''        if (objectNumber != 0 || !unifiedControlReady(state)) return legacyPriority;\n        if (x < 0 || x >= 160 || y < 0 || y >= 168) return legacyPriority;\n        if (roomEntryProtectionActive(state)) return legacyPriority;\n\n        VariableData data = state.getVariableData();\n'''
one(effective_anchor, effective_repl, 'effectiveControlPriority entry guard')

# The separate hard-collision helper also uses the editable BLOCK plane. While
# entering, sample Sierra's 0/1 controls directly so the grace period does not turn
# into a brief wall-clipping window.
collision_anchor = '''            if (data.getSceneMaskPaintMode()) {\n                return true;\n            }\n            if (y < 0 || y >= 168) {\n                return false;\n            }\n            int left = Math.max(0, Math.min(leftX, rightX));\n            int right = Math.min(159, Math.max(leftX, rightX));\n            for (int x = left; x <= right; x++) {\n                if (data.getSceneMaskBit(COLLISION, x, y)) {\n                    return true;\n                }\n            }\n'''
collision_repl = '''            if (data.getSceneMaskPaintMode()) {\n                return true;\n            }\n            if (y < 0 || y >= 168) {\n                return false;\n            }\n            int left = Math.max(0, Math.min(leftX, rightX));\n            int right = Math.min(159, Math.max(leftX, rightX));\n            if (roomEntryProtectionActive(state)) {\n                for (int x = left; x <= right; x++) {\n                    int legacy = state.controlPixels[(y * 160) + x];\n                    if (legacy == 0 || legacy == 1) return true;\n                }\n                return false;\n            }\n            for (int x = left; x <= right; x++) {\n                if (data.getSceneMaskBit(COLLISION, x, y)) {\n                    return true;\n                }\n            }\n'''
one(collision_anchor, collision_repl, 'blocksEgoMovement entry guard')

runtime.write_text(text)
print('Room-entry control grace installed: edge transitions keep Sierra WATER/FALL/BLOCK semantics until Graham is safely inside')
