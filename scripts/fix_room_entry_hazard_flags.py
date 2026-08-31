#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_room_entry_hazard_flags.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
animated = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
text = animated.read_text()

old = '''        // If the object is ego then we need to determine the on.water and hit.special flag values.\n        if (this.objectNumber == 0) {\n            state.setFlag(Defines.ONWATER, entirelyOnWater);\n            state.setFlag(Defines.HITSPEC, hitSpecial);\n        }\n'''
new = '''        // If the object is ego then we need to determine the on.water and hit.special flag values.\n        if (this.objectNumber == 0) {\n            // Room-transition protection must override the *published AGI flags*,\n            // not merely the control pixel source. KQ1 room logic reacts to\n            // ONWATER/HITSPEC, so returning Sierra's legacy WATER value here can\n            // still kill Graham before he takes his first step into the room.\n            // Keep the positional hazard flags false until SceneMaskRuntime says\n            // the edge transition has reached a safe handoff point.\n            if (SceneMaskRuntime.roomEntryProtectionActive(state)) {\n                state.setFlag(Defines.ONWATER, false);\n                state.setFlag(Defines.HITSPEC, false);\n            } else {\n                state.setFlag(Defines.ONWATER, entirelyOnWater);\n                state.setFlag(Defines.HITSPEC, hitSpecial);\n            }\n        }\n'''

count = text.count(old)
if count != 1:
    raise RuntimeError(f'AnimatedObject hazard flag publish anchor: expected 1 match, found {count}')

animated.write_text(text.replace(old, new, 1))
print('Room-entry hazard flag suppression installed: ONWATER/HITSPEC stay false until edge-entry protection ends')
