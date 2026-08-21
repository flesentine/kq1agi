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


def sx(x):
    return int(round((x / 160.0) * w))


def sy(y):
    return int(round((y / 168.0) * h))


# IMPORTANT: the raw colour-key overlay also finds a few brown/olive pixels in
# the meadow. Those pixels are invisible on the static room because they are the
# same painting, but when the overlay is composited AFTER Graham they paint grass
# over his sprite and make him look chopped apart even when he is not touching
# the tree.
#
# Therefore the key is no longer allowed to define WHERE foreground pixels may
# exist. It only refines the irregular bark edge INSIDE these hand-traced wood
# envelopes. Anything outside these envelopes is guaranteed transparent.
# Coordinates are AGI picture coordinates (160 x 168), traced from the painted
# Room 1 tree.
allowed_polygons = [
    # Left diagonal limb from the upper-left canopy into the fork.
    [(108, 0), (119, 0), (121, 18), (124, 34), (127, 51),
     (131, 69), (138, 88), (136, 99), (131, 88), (127, 73),
     (123, 55), (118, 34), (113, 16)],

    # Centre limb descending into the fork.
    [(125, 0), (139, 0), (138, 22), (138, 43), (140, 63),
     (142, 79), (140, 93), (135, 91), (133, 74), (131, 54),
     (129, 31)],

    # Right limb/main trunk.
    [(142, 0), (160, 0), (158, 23), (155, 44), (152, 63),
     (149, 80), (151, 99), (154, 119), (158, 141), (153, 149),
     (143, 151), (137, 140), (137, 118), (138, 99), (140, 82),
     (142, 60)],

    # Lower-left shadowed trunk and root flare.
    [(128, 83), (137, 82), (144, 90), (146, 104), (147, 120),
     (151, 139), (147, 148), (136, 151), (128, 145), (125, 133),
     (126, 116), (127, 101)],
]

allowed = Image.new('L', (w, h), 0)
allowed_draw = ImageDraw.Draw(allowed)
for polygon in allowed_polygons:
    allowed_draw.polygon([(sx(x), sy(y)) for x, y in polygon], fill=255)

# Conservative solid interior cores. These fill dark bark holes in the key but
# deliberately sit inside the visible wood boundary so they can never add grass.
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

    # Solid fork/junction.
    [(127, 79), (132, 80), (138, 84), (141, 91), (139, 99),
     (134, 96), (131, 91), (128, 87)],

    # Dark lower-left bole/root core seen in play-test closeups.
    [(128, 88), (133, 87), (138, 92), (140, 101), (139, 112),
     (142, 126), (144, 139), (138, 144), (132, 140), (130, 128),
     (131, 116), (130, 104)],
]

core = Image.new('L', (w, h), 0)
core_draw = ImageDraw.Draw(core)
for polygon in core_polygons:
    core_draw.polygon([(sx(x), sy(y)) for x, y in polygon], fill=255)

old_alpha = overlay.getchannel('A')

# First DELETE every keyed pixel outside the traced tree envelope. Then fill only
# conservative bark interiors. This is the important change: meadow/shadow pixels
# can no longer become foreground occluders merely because their colour resembles
# wood.
trimmed_alpha = ImageChops.multiply(old_alpha, allowed)
new_alpha = ImageChops.lighter(trimmed_alpha, core)

# RGB always comes from the real room painting. Only alpha is synthetic.
result = background.copy()
result.putalpha(new_alpha)
result.save(overlay_path, format='PNG', optimize=True)

# Depth-sort the tree at its ground/root line. Graham may move behind the trunk;
# while his baseline is at or above Y=140 the foreground tree is drawn over him.
# Below the roots he is in front.
text = state_path.read_text()
thresholds = ('&& (ego.y <= 115);', '&& (ego.y <= 122);', '&& (ego.y <= 140);')
found = sum(text.count(t) for t in thresholds)
if found < 1:
    raise RuntimeError('Room 1 overlay depth threshold not found in GameState')
text = text.replace('&& (ego.y <= 115);', '&& (ego.y <= 140);')
text = text.replace('&& (ego.y <= 122);', '&& (ego.y <= 140);')
state_path.write_text(text)

print(
    'Room 1 tree overlay constrained to hand-traced wood envelopes; '
    f'meadow key false-positives removed; depth boundary Y<=140 ({found} site(s))'
)
