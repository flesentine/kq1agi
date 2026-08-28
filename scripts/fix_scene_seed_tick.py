#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_seed_tick.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# A seed request is already room-specific: -(room + 1). Do not also require the
# editor's enabled/ownership flag. The sidebar can request a scan before Java
# paint mode is fully active, and that used to leave the request pending forever.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
guard = '        if (state == null || !editorOwnsRoom(state)) return;\n'
count = text.count(guard)
if count != 2:
    raise RuntimeError(f'SceneMaskRuntime seed ownership guards: expected 2, found {count}')
text = text.replace(guard, '        if (state == null) return;\n', 2)
runtime.write_text(text)

# Service only explicit pending requests on every interpreter tick. This remains
# safe while DEBUG freezes the scene because animationTick continues to run.
path = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
text = path.read_text()
anchor = '''            // Proceed only if the animation tick count has reached the set animation interval x 3.\n'''
insert = '''            // Service room-specific scene seed requests even if DEBUG paint mode has\n            // not yet toggled SceneMaskRuntime.editorOwnsRoom(). The negative seed\n            // value itself is the request and includes the room identity.\n            int debugRoom = state.getVar(Defines.CURROOM);\n            VariableData debugData = state.getVariableData();\n            if (debugData.getSceneControlSeedState() == -(debugRoom + 1)) {\n                SceneMaskRuntime.ensureUnifiedControlSeed(state);\n            }\n            if (debugData.getSceneScriptDangerSeedState() == -(debugRoom + 1)) {\n                SceneMaskRuntime.ensureScriptDangerSeed(state);\n            }\n\n            // Proceed only if the animation tick count has reached the set animation interval x 3.\n'''
count = text.count(anchor)
if count != 1:
    raise RuntimeError(f'Interpreter animationTick seed-service anchor: expected 1, found {count}')
path.write_text(text.replace(anchor, insert, 1))
print('Scene seed handshake fixed: explicit room requests no longer depend on editor enabled state')
