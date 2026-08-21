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
# the fork can fail the key and leave transparent holes. Those holes are what let
# Graham show "inside" the tree. Add only conservative interior cores here; the
# existing keyed alpha still owns all of the outside edges.
#
# Coordinates are AGI picture coordinates (160 x 168), hand-traced from the
# actual painted Room 1 tree. The polygons intentionally sit a little INSIDE the
# bark so no surrounding grass is added to the foreground overlay.
core_polygons = [
    # Left diagonal branch.
    [(118, 42), (122, 42), (125, 58), (128, 70), (132, 80),
     (135, 89), (133, 94), (130, 86), (127, 76), (124, 66)],

    # Nearly vertical centre branch entering the fork.
    [(131, 42), (135, 42), (136, 57), (137, 70), (139, 82),
     (139, 88), (136, 90), (134, 77), (133, 62)],

    # Main/right trunk from upper branch through the roots.
    [(144, 42), (148, 42), (147, 55), (145, 67), (144, 78),
     (143, 90), (145, 108), (148, 133), (137, 133), (137, 112),
     (137, 101), (139, 88), (141, 73), (142, 58)],

    # Solid fork/junction. This is the exact area where play-test screenshots
    # showed Graham's head/torso leaking through dark bark.
    [(127, 79), (132, 80), (138, 84), (141, 91), (139, 99),
     (134, 96), (131, 91), (128, 87)],
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
count_115 = text.count('&& (ego.y <= 115);')
count_122 = text.count('&& (ego.y <= 122);')
if (count_115 + count_122) < 1:
    raise RuntimeError('Room 1 overlay depth threshold not found in GameState')
text = text.replace('&& (ego.y <= 115);', '&& (ego.y <= 140);')
text = text.replace('&& (ego.y <= 122);', '&& (ego.y <= 140);')
state_path.write_text(text)

print(
    'Room 1 tree overlay core applied: dark fork/branch holes filled; '
    f'depth boundary set to Y<=140 ({count_115 + count_122} site(s))'
)
