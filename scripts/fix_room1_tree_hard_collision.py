#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_room1_tree_hard_collision.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
path = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
text = path.read_text()

# The previous Room 1 blocker lived inside canBeHere(). That is too late for this
# modern prop: AGI can reject/reposition positions through its normal control-map
# machinery, which still allowed Graham to visibly enter the painted trunk during
# movement. Reject the proposed movement coordinate directly instead.
marker = '''            // Update X and Y to the new position.\n            this.x = ox;\n            this.y = oy;\n'''
replacement = '''            // Modern Room 1 tree collision is enforced directly on the proposed\n            // movement coordinate. Do this BEFORE AGI assigns the new position or\n            // invokes canBeHere()/findPosition(), so Graham can never be resolved\n            // into the painted trunk. The tree body itself is defined in\n            // ModernRoomDepth and is closed on its back/front/left/right sides.\n            if ((this.objectNumber == 0)\n                    && ModernRoomDepth.blocksEgoBaseline(\n                            state.gameId,\n                            state.getVar(Defines.CURROOM),\n                            ox,\n                            ox + this.xSize() - 1,\n                            oy)) {\n                ox = px;\n                oy = py;\n                this.direction = 0;\n                state.setVar(Defines.EGODIR, 0);\n            }\n\n            // Update X and Y to the new position.\n            this.x = ox;\n            this.y = oy;\n'''

if text.count(marker) != 1:
    raise RuntimeError(
        f'AnimatedObject update-position marker expected once, found {text.count(marker)}'
    )

path.write_text(text.replace(marker, replacement))
print('Room 1 tree hard collision installed directly in AnimatedObject.updatePosition()')
