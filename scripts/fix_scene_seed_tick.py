#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_seed_tick.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# A seed request is already room-specific: -(room + 1). Do not also require the
# editor's enabled/ownership flag. The scene editor exists and loads the room even
# while TEST/play mode is active, so seed work must not depend on PAINT mode.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
guard = '        if (state == null || !editorOwnsRoom(state)) return;\n'
count = text.count(guard)
if count != 2:
    raise RuntimeError(f'SceneMaskRuntime seed ownership guards: expected 2, found {count}')
text = text.replace(guard, '        if (state == null) return;\n', 2)

# Preload both scene seed products as soon as the UI-side SceneMaskEditor has
# loaded/synchronised the current room. This happens during ordinary play, before
# DEBUG/FALL is opened, so the sidebar should normally see completed data instantly.
# A completed persisted seed is left untouched; stale/cleared state is repaired.
anchor = '    public static boolean unifiedControlReady(GameState state) {\n'
helper = '''    public static void preloadSceneSeeds(GameState state) {\n        if (state == null) return;\n        VariableData data = state.getVariableData();\n        int room = state.getVar(Defines.CURROOM);\n        if (room <= 0 || data.getSceneMaskRoom() != room) return;\n\n        int expected = room + 1;\n        int controlState = data.getSceneControlSeedState();\n        int scriptState = data.getSceneScriptDangerSeedState();\n\n        if (controlState != expected && controlState != -expected) {\n            data.setSceneControlSeedState(-expected);\n            controlState = -expected;\n        }\n        if (scriptState != expected && scriptState != -expected) {\n            data.setSceneScriptDangerSeedState(-expected);\n            scriptState = -expected;\n        }\n\n        if (controlState == -expected) ensureUnifiedControlSeed(state);\n        if (scriptState == -expected) ensureScriptDangerSeed(state);\n    }\n\n'''
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

# Keep an interpreter-tick path as a second independent route. Unlike the old
# implementation, this proactively starts the current room's scan instead of
# waiting for the browser/FALL panel to create a negative request first.
path = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
text = path.read_text()
anchor = '''            // Proceed only if the animation tick count has reached the set animation interval x 3.\n'''
insert = '''            // Preload/repair scene control and scripted-hazard data during normal\n            // gameplay. By the time DEBUG -> FALL opens, these should already be ready.\n            SceneMaskRuntime.preloadSceneSeeds(state);\n\n            // Proceed only if the animation tick count has reached the set animation interval x 3.\n'''
count = text.count(anchor)
if count != 1:
    raise RuntimeError(f'Interpreter animationTick seed-preload anchor: expected 1, found {count}')
path.write_text(text.replace(anchor, insert, 1))
print('Scene seed preload installed: FALL scans run during normal play with tick/redraw repair paths')
