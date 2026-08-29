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

print('Scene seed worker fix installed: no editor-room gate + tick/redraw/picture completion paths')
