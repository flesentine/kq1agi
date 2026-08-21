#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_room1_tree_capsule.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# ---------------------------------------------------------------------------
# The tree overlay solved visual clipping, but the first physical footprint began
# too low (Y=123). Play testing showed Graham could therefore enter the painted
# trunk around Y=120 before collision was ever consulted.
#
# Treat the trunk as a CLOSED ground-plane capsule instead:
#   back edge  : Y=116
#   front edge : Y=140
#   sides      : follow a hand-tuned trunk/root silhouette
#
# This leaves the meadow behind the tree walkable, but Graham must route around
# the trunk rather than passing through it from any direction.
# ---------------------------------------------------------------------------
modern_depth = root / 'core/src/main/java/com/agifans/agile/ModernRoomDepth.java'
text = modern_depth.read_text()

capsule = '''    private static boolean treeBasePoint(int x, int y) {
        switch (y) {
            case 116: return x >= 139 && x <= 146;
            case 117: return x >= 138 && x <= 147;
            case 118: return x >= 137 && x <= 148;
            case 119: return x >= 136 && x <= 149;
            case 120: return x >= 135 && x <= 150;
            case 121: return x >= 134 && x <= 151;
            case 122: return x >= 133 && x <= 152;
            case 123: return x >= 132 && x <= 153;
            case 124: return x >= 131 && x <= 154;
            case 125: return x >= 130 && x <= 154;
            case 126: return x >= 129 && x <= 155;
            case 127: return x >= 129 && x <= 155;
            case 128: return x >= 129 && x <= 155;
            case 129: return x >= 129 && x <= 155;
            case 130: return x >= 129 && x <= 155;
            case 131: return x >= 129 && x <= 155;
            case 132: return x >= 129 && x <= 155;
            case 133: return x >= 128 && x <= 156;
            case 134: return x >= 128 && x <= 156;
            case 135: return x >= 127 && x <= 157;
            case 136: return x >= 127 && x <= 157;
            case 137: return x >= 128 && x <= 156;
            case 138: return x >= 129 && x <= 155;
            case 139: return x >= 130 && x <= 154;
            case 140: return x >= 132 && x <= 153;
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

# Make the visual depth boundary meet the collision capsule exactly. Graham is
# behind the tree through Y=115. Y=116..140 is physically occupied by the trunk,
# and once he routes around to Y>=141 he is in front.
game_state = root / 'core/src/main/java/com/agifans/agile/GameState.java'
text = game_state.read_text()
old = '&& (ego.y <= 122);'
count = text.count(old)
if count < 1:
    raise RuntimeError('GameState Room 1 overlay depth threshold not found')
text = text.replace(old, '&& (ego.y <= 115);')
game_state.write_text(text)

print(
    f'Room 1 tree collision capsule applied: Y=116..140, '
    f'overlay depth boundary Y<=115; updated {count} overlay flag site(s)'
)
