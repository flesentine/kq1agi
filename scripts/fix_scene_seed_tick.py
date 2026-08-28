#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_seed_tick.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# SharedArray is backed by Uint32Array. Negative sentinels such as -(room + 1)
# are therefore read by the worker as 4294967294, not -2, and can never match a
# JavaScript comparison against a negative number. Use a positive request band
# that cannot collide with the ready values (room + 1, i.e. 1..256).
SEED_REQUEST_BASE = 1000

# A seed request is already room-specific. Do not also require the editor's
# enabled/ownership flag; the sidebar can request a scan before Java paint mode
# is fully active.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
guard = '        if (state == null || !editorOwnsRoom(state)) return;\n'
count = text.count(guard)
if count != 2:
    raise RuntimeError(f'SceneMaskRuntime seed ownership guards: expected 2, found {count}')
text = text.replace(guard, '        if (state == null) return;\n', 2)

runtime_replacements = [
    (
        'data.getSceneControlSeedState() != -(room + 1)',
        f'data.getSceneControlSeedState() != {SEED_REQUEST_BASE} + room + 1',
        'control seed request encoding',
    ),
    (
        'data.getSceneScriptDangerSeedState() != -(room + 1)',
        f'data.getSceneScriptDangerSeedState() != {SEED_REQUEST_BASE} + room + 1',
        'script seed request encoding',
    ),
]
for old, new, label in runtime_replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'SceneMaskRuntime {label}: expected 1, found {count}')
    text = text.replace(old, new, 1)
runtime.write_text(text)

# SceneMaskEditor originates both room scan requests. Encode them in the same
# positive request band so both UI and worker see the identical integer value.
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()
old_request = '-(room + 1)'
count = text.count(old_request)
if count != 2:
    raise RuntimeError(f'SceneMaskEditor seed requests: expected 2, found {count}')
text = text.replace(old_request, f'{SEED_REQUEST_BASE} + room + 1', 2)
editor.write_text(text)

# Service only explicit pending requests on every interpreter tick. This remains
# safe while DEBUG freezes the scene because animationTick continues to run.
path = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
text = path.read_text()
anchor = '''            // Proceed only if the animation tick count has reached the set animation interval x 3.\n'''
insert = f'''            // Service room-specific scene seed requests even if DEBUG paint mode has\n            // not yet toggled SceneMaskRuntime.editorOwnsRoom(). SharedArray uses\n            // Uint32Array, so pending requests use a positive request band.\n            int debugRoom = state.getVar(Defines.CURROOM);\n            VariableData debugData = state.getVariableData();\n            if (debugData.getSceneControlSeedState() == {SEED_REQUEST_BASE} + debugRoom + 1) {{\n                SceneMaskRuntime.ensureUnifiedControlSeed(state);\n            }}\n            if (debugData.getSceneScriptDangerSeedState() == {SEED_REQUEST_BASE} + debugRoom + 1) {{\n                SceneMaskRuntime.ensureScriptDangerSeed(state);\n            }}\n\n            // Proceed only if the animation tick count has reached the set animation interval x 3.\n'''
count = text.count(anchor)
if count != 1:
    raise RuntimeError(f'Interpreter animationTick seed-service anchor: expected 1, found {count}')
path.write_text(text.replace(anchor, insert, 1))
print('Scene seed handshake fixed: unsigned-safe room requests are serviced every interpreter tick')
