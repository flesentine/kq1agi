#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_seed_tick.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
path = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
text = path.read_text()

old = '''        if (!inTick) {\n            inTick = true;\n\n            // Proceed only if the animation tick count has reached the set animation interval x 3.\n'''
new = '''        if (!inTick) {\n            inTick = true;\n\n            // The scene editor requests Sierra control and detected-script seeds from\n            // the UI thread. Those requests used to be serviced only from a scene\n            // redraw, which can stop while DEBUG paint mode freezes the room. Service\n            // only pending requests here instead; animationTick is guaranteed to keep\n            // running on the interpreter worker even when the picture itself is static.\n            int debugRoom = state.getVar(Defines.CURROOM);\n            VariableData debugData = state.getVariableData();\n            if (debugData.getSceneControlSeedState() == -(debugRoom + 1)) {\n                SceneMaskRuntime.ensureUnifiedControlSeed(state);\n            }\n            if (debugData.getSceneScriptDangerSeedState() == -(debugRoom + 1)) {\n                SceneMaskRuntime.ensureScriptDangerSeed(state);\n            }\n\n            // Proceed only if the animation tick count has reached the set animation interval x 3.\n'''

count = text.count(old)
if count != 1:
    raise RuntimeError(f'Interpreter animationTick seed-service anchor: expected 1, found {count}')

path.write_text(text.replace(old, new, 1))
print('Scene seed handshake fixed: pending control/script scans are serviced every interpreter tick')
