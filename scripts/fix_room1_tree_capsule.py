#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_room1_tree_capsule.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# ---------------------------------------------------------------------------
# Room 1 tree collision is a GROUND-PLANE footprint, not the visible trunk.
#
# The painted foreground overlay owns visual depth: Graham may walk behind the
# trunk at higher screen Y and the tree is composited over him. Physical collision
# should therefore exist only where the trunk/roots meet the ground. A closed
# root ellipse prevents Graham from crossing through the tree from back/front or
# either side, without creating an invisible wall several pixels away from bark.
#
# Hand tuned in AGI 160x168 coordinates from the painted Room 1 tree:
#   back edge  : Y=132
#   front edge : Y=142
# ---------------------------------------------------------------------------
modern_depth = root / 'core/src/main/java/com/agifans/agile/ModernRoomDepth.java'
text = modern_depth.read_text()

capsule = '''    private static boolean treeBasePoint(int x, int y) {
        switch (y) {
            case 132: return x >= 138 && x <= 149;
            case 133: return x >= 136 && x <= 151;
            case 134: return x >= 135 && x <= 152;
            case 135: return x >= 134 && x <= 153;
            case 136: return x >= 133 && x <= 154;
            case 137: return x >= 133 && x <= 155;
            case 138: return x >= 134 && x <= 155;
            case 139: return x >= 135 && x <= 154;
            case 140: return x >= 136 && x <= 153;
            case 141: return x >= 137 && x <= 152;
            case 142: return x >= 139 && x <= 150;
            default: return false;
        }
    }

'''

pattern = re.compile(
    r'    private static boolean treeBasePoint\(int x, int y\) \{.*?^    \}\n\n(?=    public static boolean blocksEgoBaseline)',
    re.MULTILINE | re.DOTALL,
)
text, count = pattern.subn(capsule, text, count=1)
if count != 1:
    raise RuntimeError(f'ModernRoomDepth treeBasePoint replacement count={count}')
modern_depth.write_text(text)

# Visual depth stays tied to the tree's ground line, not the collision back edge.
# The later overlay-core pass also normalises this to Y<=140. Keep this fallback
# replacement here so the script remains safe when run by itself.
game_state = root / 'core/src/main/java/com/agifans/agile/GameState.java'
text = game_state.read_text()
replaced = 0
for old in ('&& (ego.y <= 122);', '&& (ego.y <= 115);'):
    count = text.count(old)
    if count:
        text = text.replace(old, '&& (ego.y <= 140);')
        replaced += count
game_state.write_text(text)

print(
    'Room 1 root-only collision applied: Y=132..142, '
    f'visual tree depth Y<=140; updated {replaced} overlay flag site(s)'
)
