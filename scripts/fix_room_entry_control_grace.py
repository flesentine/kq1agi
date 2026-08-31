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


# A room transition is a special case: Sierra has already chosen a legal entry
# coordinate on the opposite edge. The editable control map must not reinterpret
# that legal transition as WATER/FALL before Graham reaches a genuinely safe point
# in the new map. The first version used a fixed ten-pixel margin; that was too
# early for Room 1 because the edited WATER area can extend farther into the edge
# corridor. V2 keeps Sierra semantics until the editable map itself reports a
# hazard-free baseline, then hands authority back to the editable controls.
constructor = '''    private SceneMaskRuntime() {\n    }\n\n'''
helpers = '''    private static final int ROOM_ENTRY_MIN_TRAVEL = 12;\n    private static int roomEntryProtectionRoom = -1;\n    private static int roomEntryEdge = 0;\n    private static int roomEntryStartX = 0;\n    private static int roomEntryStartY = 0;\n    private static int roomEntrySafeSamples = 0;\n    private static boolean roomEntryProtectionActive = false;\n\n    private SceneMaskRuntime() {\n    }\n\n    /** Called synchronously by Commands.newRoom, before Logic 0 is rescanned. */\n    public static void beginRoomEntry(GameState state, int roomNum, int crossedEdge) {\n        roomEntryProtectionRoom = roomNum;\n        roomEntryEdge = crossedEdge;\n        roomEntryProtectionActive = true;\n        roomEntrySafeSamples = 0;\n\n        if (state != null) {\n            if (state.ego != null) {\n                roomEntryStartX = state.ego.x;\n                roomEntryStartY = state.ego.y;\n            }\n            // These flags describe ego's current coordinate. They must never leak\n            // from the old room into the first logic scan of the new room.\n            state.setFlag(Defines.ONWATER, false);\n            state.setFlag(Defines.HITSPEC, false);\n        }\n    }\n\n    private static int roomEntryTravel(GameState state) {\n        AnimatedObject ego = state.ego;\n        if (ego == null) return 0;\n        switch (roomEntryEdge) {\n            case Defines.RIGHT:\n                // Crossed the old room's RIGHT edge, so we spawned at new-room left.\n                return Math.max(0, ego.x - roomEntryStartX);\n            case Defines.LEFT:\n                // Crossed LEFT, so we spawned at new-room right and move leftward.\n                return Math.max(0, roomEntryStartX - ego.x);\n            case Defines.TOP:\n                // Crossed TOP, so we spawned at the new room's bottom.\n                return Math.max(0, roomEntryStartY - ego.y);\n            case Defines.BOTTOM:\n                // Crossed BOTTOM, so we spawned just under the new room horizon.\n                return Math.max(0, ego.y - roomEntryStartY);\n            default:\n                return Math.max(Math.abs(ego.x - roomEntryStartX),\n                        Math.abs(ego.y - roomEntryStartY));\n        }\n    }\n\n    private static boolean editableEntryBaselineSafe(GameState state) {\n        if (!unifiedControlReady(state)) return false;\n        AnimatedObject ego = state.ego;\n        if (ego == null || !ego.drawn) return false;\n\n        int y = ego.y;\n        if (y < 0 || y >= 168) return false;\n        int left = Math.max(0, ego.x);\n        int right = Math.min(159, ego.x + Math.max(1, ego.xSize()) - 1);\n        VariableData data = state.getVariableData();\n\n        for (int x = left; x <= right; x++) {\n            // BLOCK can stop the next movement but cannot kill Graham. The handoff\n            // specifically waits until WATER/FALL can no longer instantly fire a\n            // room death as soon as editable controls become authoritative.\n            if (data.getSceneMaskBit(WATER, x, y)\n                    || data.getSceneMaskBit(FALL, x, y)) {\n                return false;\n            }\n        }\n        return true;\n    }\n\n    private static void refreshRoomEntryProtection(GameState state) {\n        if (state == null) return;\n\n        int room = state.getVar(Defines.CURROOM);\n        if (room != roomEntryProtectionRoom) {\n            // Fallback for restore/restart paths that do not pass through newRoom.\n            beginRoomEntry(state, room, 0);\n        }\n\n        if (!roomEntryProtectionActive) return;\n        AnimatedObject ego = state.ego;\n        if (ego == null || !ego.drawn) return;\n\n        // Do not even consider handing off until Graham has actually walked away\n        // from the entry edge. Once he has, require two consecutive hazard-free\n        // samples so a one-pixel hole in WATER/FALL cannot end protection early.\n        if (roomEntryTravel(state) < ROOM_ENTRY_MIN_TRAVEL) {\n            roomEntrySafeSamples = 0;\n            return;\n        }\n\n        if (editableEntryBaselineSafe(state)) {\n            roomEntrySafeSamples++;\n            if (roomEntrySafeSamples >= 2) {\n                roomEntryProtectionActive = false;\n            }\n        } else {\n            roomEntrySafeSamples = 0;\n        }\n    }\n\n    public static boolean roomEntryProtectionActive(GameState state) {\n        refreshRoomEntryProtection(state);\n        return roomEntryProtectionActive;\n    }\n\n'''
one(constructor, helpers, 'SceneMaskRuntime constructor')

# During entry protection, use Sierra's original control pixel for WATER/FALL.
effective_anchor = '''        if (objectNumber != 0 || !unifiedControlReady(state)) return legacyPriority;\n        if (x < 0 || x >= 160 || y < 0 || y >= 168) return legacyPriority;\n\n        VariableData data = state.getVariableData();\n'''
effective_repl = '''        if (objectNumber != 0 || !unifiedControlReady(state)) return legacyPriority;\n        if (x < 0 || x >= 160 || y < 0 || y >= 168) return legacyPriority;\n        if (roomEntryProtectionActive(state)) return legacyPriority;\n\n        VariableData data = state.getVariableData();\n'''
one(effective_anchor, effective_repl, 'effectiveControlPriority entry guard')

# The separate hard-collision helper also uses the editable BLOCK plane. While
# entering, sample Sierra's 0/1 controls directly so the grace period does not turn
# into a wall-clipping window.
collision_anchor = '''            if (data.getSceneMaskPaintMode()) {\n                return true;\n            }\n            if (y < 0 || y >= 168) {\n                return false;\n            }\n            int left = Math.max(0, Math.min(leftX, rightX));\n            int right = Math.min(159, Math.max(leftX, rightX));\n            for (int x = left; x <= right; x++) {\n                if (data.getSceneMaskBit(COLLISION, x, y)) {\n                    return true;\n                }\n            }\n'''
collision_repl = '''            if (data.getSceneMaskPaintMode()) {\n                return true;\n            }\n            if (y < 0 || y >= 168) {\n                return false;\n            }\n            int left = Math.max(0, Math.min(leftX, rightX));\n            int right = Math.min(159, Math.max(leftX, rightX));\n            if (roomEntryProtectionActive(state)) {\n                for (int x = left; x <= right; x++) {\n                    int legacy = state.controlPixels[(y * 160) + x];\n                    if (legacy == 0 || legacy == 1) return true;\n                }\n                return false;\n            }\n            for (int x = left; x <= right; x++) {\n                if (data.getSceneMaskBit(COLLISION, x, y)) {\n                    return true;\n                }\n            }\n'''
one(collision_anchor, collision_repl, 'blocksEgoMovement entry guard')

runtime.write_text(text)

# Arm the transition at the actual AGI new.room boundary, before Logic 0 gets a
# chance to observe stale ONWATER/HITSPEC. Preserve EGOEDGE before newRoom resets it.
commands = root / 'core/src/main/java/com/agifans/agile/Commands.java'
ctext = commands.read_text()
old = '''        switch (state.getVar(Defines.EGOEDGE)) {\n'''
new = '''        int crossedEdge = state.getVar(Defines.EGOEDGE);\n        switch (crossedEdge) {\n'''
if ctext.count(old) != 1:
    raise RuntimeError(f'Commands newRoom EGOEDGE switch: expected 1 match, found {ctext.count(old)}')
ctext = ctext.replace(old, new, 1)

old = '''        // Change the room number.\n        state.setVar(Defines.PREVROOM, state.getVar(Defines.CURROOM));\n'''
new = '''        // Arm transition protection now, while crossedEdge and the newly placed\n        // ego coordinates are still available and before the next Logic 0 scan.\n        SceneMaskRuntime.beginRoomEntry(state, roomNum, crossedEdge);\n\n        // Change the room number.\n        state.setVar(Defines.PREVROOM, state.getVar(Defines.CURROOM));\n'''
if ctext.count(old) != 1:
    raise RuntimeError(f'Commands newRoom room-number anchor: expected 1 match, found {ctext.count(old)}')
commands.write_text(ctext.replace(old, new, 1))

print('Room-entry control grace v2 installed: clear stale hazard flags at new.room and keep Sierra controls until editable WATER/FALL has a safe handoff')
