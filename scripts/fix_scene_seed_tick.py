#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_seed_tick.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# A seed request is already room-specific: -(room + 1). Do not also require the
# editor's enabled/ownership flag. FALL seed work belongs to the interpreter
# worker and must not depend on whether the UI-side editor has claimed the room.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
guard = '        if (state == null || !editorOwnsRoom(state)) return;\n'
count = text.count(guard)
if count != 2:
    raise RuntimeError(f'SceneMaskRuntime seed ownership guards: expected 2, found {count}')
text = text.replace(guard, '        if (state == null) return;\n', 2)

# The raw screenshot diagnostic showed both Room 1 seed slots stuck at -2. That
# proves the browser request reached shared memory but the worker preload returned
# before servicing it. Do not gate worker-side preload on SCENE_MASK_ROOM; the
# request itself and CURROOM already identify the room.
anchor = '    public static boolean unifiedControlReady(GameState state) {\n'
helper = '''    public static void preloadSceneSeeds(GameState state) {\n        if (state == null) return;\n        VariableData data = state.getVariableData();\n        int room = state.getVar(Defines.CURROOM);\n        if (room <= 0) return;\n\n        int expected = room + 1;\n        int controlState = data.getSceneControlSeedState();\n        int scriptState = data.getSceneScriptDangerSeedState();\n\n        if (controlState != expected && controlState != -expected) {\n            data.setSceneControlSeedState(-expected);\n            controlState = -expected;\n        }\n        if (scriptState != expected && scriptState != -expected) {\n            data.setSceneScriptDangerSeedState(-expected);\n            scriptState = -expected;\n        }\n\n        if (controlState == -expected) ensureUnifiedControlSeed(state);\n        if (scriptState == -expected) ensureScriptDangerSeed(state);\n    }\n\n'''
if text.count(anchor) != 1:
    raise RuntimeError(f'SceneMaskRuntime preload anchor: expected 1, found {text.count(anchor)}')
text = text.replace(anchor, helper + anchor, 1)

# The normal redraw path is an early opportunity to finish preloading. Replace
# the two request-only calls installed by the earlier FALL patches with the
# consolidated preload/repair operation.
redraw = '''        ensureUnifiedControlSeed(state);\n        ensureScriptDangerSeed(state);\n        VariableData data = state.getVariableData();\n'''
redraw_repl = '''        preloadSceneSeeds(state);\n        VariableData data = state.getVariableData();\n'''
if text.count(redraw) != 1:
    raise RuntimeError(f'SceneMaskRuntime redraw seed calls: expected 1, found {text.count(redraw)}')
text = text.replace(redraw, redraw_repl, 1)
runtime.write_text(text)

# Keep an interpreter-tick route. This executes on the worker before the normal
# animation interval early-return and therefore services a negative browser
# request even when no new room frame is being rendered.
path = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
text = path.read_text()
anchor = '''            // Proceed only if the animation tick count has reached the set animation interval x 3.\n'''
insert = '''            // Service/repair FALL control and scripted-hazard seed state directly\n            // on the interpreter worker. No UI editor ownership is required.\n            SceneMaskRuntime.preloadSceneSeeds(state);\n\n            // Proceed only if the animation tick count has reached the set animation interval x 3.\n'''
count = text.count(anchor)
if count != 1:
    raise RuntimeError(f'Interpreter animationTick seed-preload anchor: expected 1, found {count}')
path.write_text(text.replace(anchor, insert, 1))

# Add a third, deterministic worker-side route exactly where Sierra's priority /
# control picture has just been split into state.controlPixels. This guarantees
# first-room setup can complete the scan without waiting for DEBUG or a redraw.
commands = root / 'core/src/main/java/com/agifans/agile/Commands.java'
text = commands.read_text()
anchor = '''        splitPriorityPixels();\n    }\n\n    /**\n     * Overlays an AGI Picture identified by the given picture number over the current picture.\n'''
insert = '''        splitPriorityPixels();\n\n        // controlPixels are authoritative and fully populated at this point. Seed\n        // FALL/HITSPEC and detected scripted hazards immediately on the worker.\n        SceneMaskRuntime.preloadSceneSeeds(state);\n    }\n\n    /**\n     * Overlays an AGI Picture identified by the given picture number over the current picture.\n'''
count = text.count(anchor)
if count != 1:
    raise RuntimeError(f'Commands updatePixelArrays seed anchor: expected 1, found {count}')
commands.write_text(text.replace(anchor, insert, 1))

# The worker can finish the Room 1 preload before the UI-side SceneMaskEditor sees
# the room. The old ensureRoom() sequence then called syncAll() first and overwrote
# that completed shared map with the editor's still-empty local arrays, finally
# replacing +2 with a fresh -2 request. That exactly matches the stalled screenshot.
#
# If the worker has already produced a room seed, adopt it into the local arrays
# BEFORE syncAll(). Existing saved unified maps remain authoritative; for older
# pre-unified custom maps, any positive local control pixels still win over the
# worker import. Then persist the adopted seed so future loads need no handshake.
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()
old = '''        syncAll();\n        boolean unifiedSaved = prefs.getBoolean(key("unifiedControlV1"), false);\n        if (unifiedSaved) {\n            waitingForControlSeed = false;\n            waterActive = true;\n            fallActive = true;\n            data.setSceneMaskWaterActive(true);\n            data.setSceneMaskFallActive(true);\n            data.setSceneControlSeedState(room + 1);\n        } else {\n            waitingForControlSeed = true;\n            data.setSceneControlSeedState(-(room + 1));\n        }\n        boolean scriptSaved = savedScriptFall.length() == HEIGHT * 40;\n        waitingForScriptDangerSeed = !scriptSaved;\n        data.setSceneScriptDangerSeedState(scriptSaved ? room + 1 : -(room + 1));\n        dirty = false;\n'''
new = '''        boolean unifiedSaved = prefs.getBoolean(key("unifiedControlV1"), false);\n        boolean scriptSaved = savedScriptFall.length() == HEIGHT * 40;\n        int expectedSceneSeed = room + 1;\n        boolean preloadedControlSeed = !unifiedSaved\n                && data.getSceneControlSeedState() == expectedSceneSeed;\n        boolean preloadedScriptSeed = !scriptSaved\n                && data.getSceneScriptDangerSeedState() == expectedSceneSeed;\n\n        if (preloadedControlSeed) {\n            for (int y = 0; y < HEIGHT; y++) {\n                for (int x = 0; x < WIDTH; x++) {\n                    // Preserve older custom additions that existed before the\n                    // unified-control migration. Otherwise adopt Sierra's map.\n                    boolean localFall = masks[FALL][y][x];\n                    boolean localWater = masks[WATER][y][x];\n                    boolean localBlock = masks[COLLISION][y][x];\n                    if (localFall || localWater || localBlock) continue;\n\n                    boolean fall = data.getSceneMaskBit(FALL, x, y);\n                    boolean water = !fall && data.getSceneMaskBit(WATER, x, y);\n                    boolean block = !fall && !water\n                            && data.getSceneMaskBit(COLLISION, x, y);\n                    masks[FALL][y][x] = fall;\n                    masks[WATER][y][x] = water;\n                    masks[COLLISION][y][x] = block;\n                }\n            }\n            waterActive = true;\n            fallActive = true;\n        }\n\n        if (preloadedScriptSeed) {\n            for (int y = 0; y < HEIGHT; y++) {\n                for (int x = 0; x < WIDTH; x++) {\n                    masks[SCRIPT_FALL][y][x] =\n                            data.getSceneMaskBit(SCRIPT_FALL, x, y);\n                }\n            }\n        }\n\n        // Only now publish the UI-side arrays. If the worker had already seeded\n        // this room, the local arrays contain that data instead of erasing it.\n        syncAll();\n\n        if (unifiedSaved || preloadedControlSeed) {\n            waitingForControlSeed = false;\n            waterActive = true;\n            fallActive = true;\n            data.setSceneMaskWaterActive(true);\n            data.setSceneMaskFallActive(true);\n            data.setSceneControlSeedState(expectedSceneSeed);\n        } else {\n            waitingForControlSeed = true;\n            data.setSceneControlSeedState(-expectedSceneSeed);\n        }\n\n        if (scriptSaved || preloadedScriptSeed) {\n            waitingForScriptDangerSeed = false;\n            data.setSceneScriptDangerSeedState(expectedSceneSeed);\n        } else {\n            waitingForScriptDangerSeed = true;\n            data.setSceneScriptDangerSeedState(-expectedSceneSeed);\n        }\n\n        // Persist only the planes that were genuinely preloaded. Do not call the\n        // general saveRoom() here because one seed can legitimately be ready while\n        // the other is still pending.\n        if (preloadedControlSeed) {\n            prefs.putString(key("collision"), encode(masks[COLLISION]));\n            prefs.putString(key("water"), encode(masks[WATER]));\n            prefs.putString(key("fall"), encode(masks[FALL]));\n            prefs.putBoolean(key("waterActive"), true);\n            prefs.putBoolean(key("fallActive"), true);\n            prefs.putBoolean(key("unifiedControlV1"), true);\n        }\n        if (preloadedScriptSeed) {\n            prefs.putString(key("scriptFall"), encode(masks[SCRIPT_FALL]));\n        }\n        if (preloadedControlSeed || preloadedScriptSeed) prefs.flush();\n        dirty = false;\n'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f'SceneMaskEditor preloaded-seed adoption block: expected 1, found {count}')
editor.write_text(text.replace(old, new, 1))

print('Scene seed worker/UI race fixed: completed FALL seeds are adopted before initial UI sync can erase them')
