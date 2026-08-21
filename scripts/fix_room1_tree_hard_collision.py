#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_room1_tree_hard_collision.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
path = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
text = path.read_text()

# Room 1's modern tree uses its own physical ground-plane footprint. Reject the
# proposed movement coordinate directly so AGI cannot resolve Graham into the
# painted trunk through the legacy control map.
#
# IMPORTANT: collision must use Graham's FEET, not his entire cel width. AGI cels
# contain transparent/visual width outside the actual ground contact area. Using
# x..x+xSize-1 made Graham stop visibly several pixels away from the bark on both
# sides. A centered three-pixel foot box matches the part of the sprite that is
# actually standing on the ground while still preventing passage through the
# closed tree capsule.
marker = '''            // Update X and Y to the new position.\n            this.x = ox;\n            this.y = oy;\n'''
replacement = '''            // Modern Room 1 tree collision is enforced directly on the proposed\n            // movement coordinate. Test a narrow FOOT BOX rather than the whole\n            // cel width; transparent/upper-body sprite width must not create an\n            // invisible gap between Graham and the painted bark.\n            if (this.objectNumber == 0) {\n                int footCenter = ox + (this.xSize() / 2);\n                int footLeft = footCenter - 1;\n                int footRight = footCenter + 1;\n\n                if (ModernRoomDepth.blocksEgoBaseline(\n                        state.gameId,\n                        state.getVar(Defines.CURROOM),\n                        footLeft,\n                        footRight,\n                        oy)) {\n                    ox = px;\n                    oy = py;\n                    this.direction = 0;\n                    state.setVar(Defines.EGODIR, 0);\n                }\n            }\n\n            // Update X and Y to the new position.\n            this.x = ox;\n            this.y = oy;\n'''

if text.count(marker) != 1:
    raise RuntimeError(
        f'AnimatedObject update-position marker expected once, found {text.count(marker)}'
    )

path.write_text(text.replace(marker, replacement))
print('Room 1 direct tree collision installed using Graham centered 3-pixel foot box')
