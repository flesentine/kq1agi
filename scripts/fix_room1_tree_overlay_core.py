#!/usr/bin/env python3
from pathlib import Path
import sys

from PIL import Image, ImageChops, ImageDraw

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_room1_tree_overlay_core.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
background_path = root / 'assets/backgrounds/room_001_hires.png'
overlay_path = root / 'assets/backgrounds/room_001_tree_overlay.png'
state_path = root / 'core/src/main/java/com/agifans/agile/GameState.java'

if not background_path.exists() or not overlay_path.exists():
    raise RuntimeError('Room 1 background/tree overlay must exist before this pass')

with Image.open(background_path) as im:
    background = im.convert('RGBA')
with Image.open(overlay_path) as im:
    overlay = im.convert('RGBA')

w, h = background.size
if overlay.size != background.size:
    raise RuntimeError(f'Room 1 overlay/background size mismatch: {overlay.size} vs {background.size}')

# The color key gets the irregular OUTER bark edge nicely, but dark bark inside
# the fork and lower-left bole can fail the key and leave transparent holes.
# Those holes are what let Graham appear to stand *inside* the tree. Add solid,
# hand-traced interior cores while leaving the irregular grass-facing edge to the
# original key wherever possible.
#
# Coordinates are AGI picture coordinates (160 x 168), traced from the modern
# Room 1 painting. RGB still comes from the original painting; only alpha is added.
core_polygons = [
    # Left diagonal branch.
    [(116, 40), (122, 39), (124, 50), (127, 62), (130, 73),
     (134, 84), (136, 91), (133, 98), (129, 88), (126, 78),
     (122, 66), (119, 54)],

    # Nearly vertical centre branch entering the fork.
    [(129, 39), (136, 39), (136, 52), (137, 64), (138, 75),
     (141, 85), (141, 92), (136, 94), (134, 82), (133, 69),
     (132, 55)],

    # Main/right trunk from upper branch through the roots.
    [(143, 38), (150, 38), (149, 52), (147, 65), (145, 78),
     (144, 91), (145, 106), (148, 122), (151, 139), (145, 148),
     (135, 147), (135, 132), (136, 117), (136, 103), (138, 89),
     (140, 73), (142, 56)],

    # Solid fork/junction. This closes the dark V-shaped interior where several
    # screenshots showed Graham's head and torso leaking through bark.
    [(124, 77), (131, 77), (138, 81), (143, 88), (143, 96),
     (139, 103), (133, 100), (128, 95), (125, 88)],

    # NEW: lower-left dark bole. The color key consistently misses this because
    # it is mostly blue/black shadow rather than warm bark. It is still solid wood.
    # This polygon follows that shadowed trunk down into the root flare and is the
    # exact area exposed by the latest play-test close-up.
    [(128, 88), (135, 91), (138, 101), (138, 112), (139, 124),
     (140, 137), (137, 146), (127, 146), (123, 140), (124, 129),
     (125, 117), (125, 106), (126, 97)],

    # Root/floor core. Keep this inside the visible bark/root mass so Graham's
    # lower legs cannot show through the dark root area while he is behind it.
    [(123, 134), (130, 132), (139, 133), (149, 137), (153, 143),
     (149, 149), (137, 151), (124, 149), (119, 145)],
]


def sx(x):
    return int(round((x / 160.0) * w))


def sy(y):
    return int(round((y / 168.0) * h))

core = Image.new('L', (w, h), 0)
draw = ImageDraw.Draw(core)
for polygon in core_polygons:
    draw.polygon([(sx(x), sy(y)) for x, y in polygon], fill=255)

old_alpha = overlay.getchannel('A')
new_alpha = ImageChops.lighter(old_alpha, core)

# RGB always comes from the real room painting. Only alpha is synthetic.
result = background.copy()
result.putalpha(new_alpha)
result.save(overlay_path, format='PNG', optimize=True)

# A tree is depth-sorted at its ground/base line, not at the top edge of its
# collision footprint. Graham may legally walk around the BACK of the trunk at
# Y 116..140. While doing that, the painted tree must still composite over him.
# Once his baseline is below the roots (Y > 140), he is in front of the tree.
text = state_path.read_text()
thresholds = ('&& (ego.y <= 115);', '&& (ego.y <= 122);', '&& (ego.y <= 140);')
found = sum(text.count(t) for t in thresholds)
if found < 1:
    raise RuntimeError('Room 1 overlay depth threshold not found in GameState')
text = text.replace('&& (ego.y <= 115);', '&& (ego.y <= 140);')
text = text.replace('&& (ego.y <= 122);', '&& (ego.y <= 140);')
state_path.write_text(text)

print(
    'Room 1 tree overlay core applied: fork, lower-left bole and roots filled; '
    f'depth boundary Y<=140 ({found} site(s) located)'
)
