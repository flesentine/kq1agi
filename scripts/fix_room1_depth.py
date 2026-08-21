#!/usr/bin/env python3
from pathlib import Path
import sys

from PIL import Image

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_room1_depth.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()


def row_runs(bits, width, y):
    """Return contiguous true runs on one row as (start, end) pairs."""
    runs = []
    x = 0
    base = y * width
    while x < width:
        if bits[base + x]:
            start = x
            while x < width and bits[base + x]:
                x += 1
            runs.append((start, x - 1))
        else:
            x += 1
    return runs


# ---------------------------------------------------------------------------
# 1. Suppress Room 1 water-only legacy animated objects.
# ---------------------------------------------------------------------------
game_state = root / 'core/src/main/java/com/agifans/agile/GameState.java'
text = game_state.read_text()

old = '''        for (AnimatedObject aniObj : this.animatedObjects) {
            if (aniObj.drawn && (aniObj.update == updating)) {
                objsToDraw.add(aniObj);
            }
        }
'''
new = '''        for (AnimatedObject aniObj : this.animatedObjects) {
            if (aniObj.drawn && (aniObj.update == updating)) {
                if (shouldSuppressForModernRoom(aniObj)) {
                    continue;
                }
                objsToDraw.add(aniObj);
            }
        }
'''
if text.count(old) != 1:
    raise RuntimeError('GameState animated-object list block not found')
text = text.replace(old, new)

marker = '''    public List<AnimatedObject> makeObjectDrawList(List<AnimatedObject> objsToDraw, boolean updating) {
'''
helper = '''    /**
     * Room-specific visual cleanup for the modern Room 1 artwork.
     *
     * The opening-room crocodiles are water-only AnimatedObjects. Keep their
     * AGI state/logic intact, but omit their legacy EGA cels from the rendered
     * object lists while the modern Room 1 background is in use.
     */
    private boolean shouldSuppressForModernRoom(AnimatedObject aniObj) {
        return "KQ1".equalsIgnoreCase(gameId)
                && (getVar(Defines.CURROOM) == 1)
                && (aniObj != ego)
                && aniObj.stayOnWater;
    }

'''
if text.count(marker) != 1:
    raise RuntimeError('GameState makeObjectDrawList marker not found')
text = text.replace(marker, helper + marker)
game_state.write_text(text)

# ---------------------------------------------------------------------------
# 2. Build the modern visual tree mask from the actual Room 1 painting, then
#    hand-tune the part of the trunk Graham can walk beside.
#
# Visual depth and physical collision are intentionally separate. The tree may
# cover Graham when he walks behind it, but only the tiny root footprint later
# in this file is physically solid.
# ---------------------------------------------------------------------------
background = root / 'assets/backgrounds/room_001_hires.png'
if not background.exists():
    raise RuntimeError(f'Modern Room 1 background not found: {background}')

with Image.open(background) as source:
    image = source.convert('RGB')

width, height = image.size
if (width, height) != (1586, 992):
    raise RuntimeError(f'Unexpected Room 1 background size: {(width, height)}')

pixels = image.load()
mask = Image.new('L', (width, height), 0)
mask_pixels = mask.load()

# Broad ROI around the modern tree. Colour tests remove most meadow/grass.
x0 = int(width * 0.695)
x1 = width
y0 = int(height * 0.035)
y1 = int(height * 0.79)

selected = 0
for y in range(y0, y1):
    for x in range(x0, x1):
        r, g, b = pixels[x, y]
        brightest = max(r, g, b)

        bark = (
            r >= (g * 0.92)
            and r >= (b * 1.12)
            and (r - b) >= 18
            and r >= 45
        )
        dark_bark = (
            brightest < 75
            and r >= (g * 0.78)
            and r >= b
            and (r + b) > 20
        )

        if bark or dark_bark:
            mask_pixels[x, y] = 255
            selected += 1

if not (25000 <= selected <= 140000):
    raise RuntimeError(f'Room 1 tree mask looks implausible: {selected} source pixels selected')

# Reduce to AGI's true 160x168 visual-priority plane.
small = mask.resize((160, 168), Image.Resampling.BOX)
small_pixels = small.load()

tree_bits = [False] * (160 * 168)
for y in range(168):
    for x in range(160):
        covered = small_pixels[x, y] >= 48

        # Guaranteed open meadow left of the lower tree.
        if (x < 126) and (y > 80):
            covered = False

        tree_bits[(y * 160) + x] = covered

# Hand-tune the interactive left edge of the trunk. This is where play testing
# showed Graham being cropped even though his sprite was still visibly left of
# the painted bark. Preserve the detected right edge, close only tiny 1-2 pixel
# holes inside bark, and pull the left occlusion edge inward by two AGI pixels.
for y in range(80, 123):
    runs = row_runs(tree_bits, 160, y)
    if not runs:
        continue

    # Merge only tiny gaps. Larger gaps are real fork/branch openings and stay open.
    merged = []
    cur_start, cur_end = runs[0]
    for start, end in runs[1:]:
        if start - cur_end - 1 <= 2:
            cur_end = end
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))

    # Clear the row and rebuild a deliberately conservative silhouette.
    base = y * 160
    for x in range(160):
        tree_bits[base + x] = False

    for run_index, (start, end) in enumerate(merged):
        tuned_start = start
        if run_index == 0:
            tuned_start = min(end, start + 2)
        for x in range(tuned_start, end + 1):
            tree_bits[base + x] = True

# A final hard guard against any accidental left-side grass fragments in the
# exact band where Graham was clipping in screenshots.
for y in range(80, 109):
    base = y * 160
    for x in range(0, 128):
        tree_bits[base + x] = False

tree_count = sum(1 for covered in tree_bits if covered)
if not (250 <= tree_count <= 4500):
    raise RuntimeError(f'Room 1 AGI tree mask looks implausible: {tree_count} pixels selected')

# Pack the visual mask into Java int words for O(1) lookup.
words = [0] * ((len(tree_bits) + 31) // 32)
for index, covered in enumerate(tree_bits):
    if covered:
        words[index >> 5] |= (1 << (index & 31))

word_lines = []
for start in range(0, len(words), 8):
    chunk = words[start:start + 8]
    word_lines.append(
        '        ' + ', '.join(f'0x{word & 0xFFFFFFFF:08X}' for word in chunk)
    )

modern_depth = root / 'core/src/main/java/com/agifans/agile/ModernRoomDepth.java'
modern_depth.write_text('''package com.agifans.agile;

/**
 * Hand-tuned visual priority and physical root collision for the modern Room 1 tree.
 *
 * The visual silhouette is generated from the painting and tuned at AGI pixel
 * resolution. Physical collision is a separate, small root footprint.
 */
public final class ModernRoomDepth {
    private static final int WIDTH = 160;
    private static final int HEIGHT = 168;
    private static final int DEFAULT_PRIORITY = 4;
    private static final int ROOM1_TREE_PRIORITY = 12;

    private static final int[] ROOM1_TREE_BITS = new int[] {
''' + ',\n'.join(word_lines) + '''
    };

    private ModernRoomDepth() {
    }

    private static boolean roomOne(String gameId, int room) {
        return "KQ1".equalsIgnoreCase(gameId) && room == 1;
    }

    private static boolean treeBitAt(int x, int y) {
        if (x < 0 || x >= WIDTH || y < 0 || y >= HEIGHT) {
            return false;
        }
        int index = (y * WIDTH) + x;
        return (ROOM1_TREE_BITS[index >>> 5] & (1 << (index & 31))) != 0;
    }

    /**
     * Returns -1 when Sierra's original visual priority should be used.
     * Otherwise returns the modern Room 1 visual priority.
     */
    public static int priorityFor(String gameId, int room, int x, int y) {
        if (!roomOne(gameId, room)) {
            return -1;
        }
        if (x < 0 || x >= WIDTH || y < 0 || y >= HEIGHT) {
            return DEFAULT_PRIORITY;
        }
        return treeBitAt(x, y) ? ROOM1_TREE_PRIORITY : DEFAULT_PRIORITY;
    }

    /**
     * Neutralise only old BLOCKING control pixels in the full old-tree corridor.
     *
     * This corridor must extend up the trunk because Sierra's invisible original
     * tree geometry can otherwise stop Graham while he is supposed to be walking
     * behind the new painted tree. Water (3) and special (2) controls are never
     * neutralised; the caller checks the original control value first.
     */
    public static boolean insideOldTreeControlCorridor(
            String gameId, int room, int x, int y) {
        return roomOne(gameId, room)
                && x >= 124 && x <= 151
                && y >= 78 && y <= 140;
    }

    /** Small manual root/base collision footprint. No vertical trunk collision. */
    private static boolean treeBasePoint(int x, int y) {
        int left;
        int right;

        switch (y) {
            case 125: left = 134; right = 145; break;
            case 126: left = 134; right = 146; break;
            case 127: left = 134; right = 146; break;
            case 128: left = 135; right = 146; break;
            case 129: left = 136; right = 146; break;
            case 130: left = 136; right = 145; break;
            case 131: left = 137; right = 145; break;
            case 132: left = 137; right = 145; break;
            case 133: left = 139; right = 144; break;
            default: return false;
        }

        return x >= left && x <= right;
    }

    /** True when Graham's baseline overlaps the physical root/base footprint. */
    public static boolean blocksEgoBaseline(
            String gameId, int room, int leftX, int rightX, int baselineY) {
        if (!roomOne(gameId, room)) {
            return false;
        }

        int left = Math.max(0, Math.min(leftX, rightX));
        int right = Math.min(WIDTH - 1, Math.max(leftX, rightX));
        for (int x = left; x <= right; x++) {
            if (treeBasePoint(x, baselineY)) {
                return true;
            }
        }
        return false;
    }
}
''')

# ---------------------------------------------------------------------------
# 3. Make dynamic actor drawing use the modern visual depth map instead of the
#    invisible original Room 1 picture priority geometry.
# ---------------------------------------------------------------------------
animated_object = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
text = animated_object.read_text()

draw_marker = '''    public void draw() {
'''
draw_pos = text.find(draw_marker)
if draw_pos < 0:
    raise RuntimeError('AnimatedObject dynamic draw() marker not found')

head = text[:draw_pos]
tail = text[draw_pos:]

old_priority = '''                    // Get the priority colour index for this position from the priority screen.
                    int priorityIndex = state.priorityPixels[priorityPos];

                    // If this AnimatedObject's priority is greater or equal to the priority screen value
                    // for this pixel's position, then we'll draw it.
                    if (this.priority >= priorityIndex) {
'''
new_priority = '''                    // Start with Sierra's original picture priority.
                    int priorityIndex = state.priorityPixels[priorityPos];

                    // A replacement painted room must not inherit invisible occluders from
                    // the old EGA picture. Use its generated visual-only depth map instead.
                    int modernPriority = ModernRoomDepth.priorityFor(
                            state.gameId,
                            state.getVar(Defines.CURROOM),
                            this.x + x,
                            aniObjTop + y);
                    if (modernPriority >= 0) {
                        priorityIndex = modernPriority;
                    }

                    // If this AnimatedObject's priority is greater or equal to the active
                    // visual priority for this pixel's position, then we'll draw it.
                    if (this.priority >= priorityIndex) {
'''
if tail.count(old_priority) != 1:
    raise RuntimeError(
        f'AnimatedObject dynamic priority block expected once, found {tail.count(old_priority)}'
    )
tail = tail.replace(old_priority, new_priority)
text = head + tail

# ---------------------------------------------------------------------------
# 4. Remove Sierra's old invisible TREE blocking controls across the old-tree
#    corridor, but only when the original control is actually a blocker (0/1).
#    Then apply the tiny modern root footprint. This is the important separation:
#    the trunk controls Z/occlusion, while only the roots control movement.
# ---------------------------------------------------------------------------
old_control = '''                // Get the priority screen priority value for this pixel of the base line.
                int priority = state.controlPixels[pixelPos];

                if (priority != 3) {
'''
new_control = '''                // Get Sierra's original control value for this baseline pixel.
                int priority = state.controlPixels[pixelPos];
                int baselineX = this.x + (pixelPos - startPixelPos);

                // Sierra's original Room 1 tree is in a different place from the modern
                // painting. For ego only, neutralise OLD blocking colours (0/1) throughout
                // that tree corridor so they cannot stop Graham high up the Y/depth axis.
                // Preserve special=2 and water=3 exactly as-is.
                if ((this.objectNumber == 0)
                        && (priority == 0 || priority == 1)
                        && ModernRoomDepth.insideOldTreeControlCorridor(
                                state.gameId,
                                state.getVar(Defines.CURROOM),
                                baselineX,
                                this.y)) {
                    priority = 4;
                }

                if (priority != 3) {
'''
if text.count(old_control) != 1:
    raise RuntimeError(
        f'AnimatedObject control-pixel block expected once, found {text.count(old_control)}'
    )
text = text.replace(old_control, new_control)

water_marker = '''            if (entirelyOnWater) {
'''
modern_collision = '''            // The modern tree is physically solid only at its small root/base
            // footprint. Graham may move freely behind the vertical trunk and branches.
            if ((this.objectNumber == 0) && canBeHere && ModernRoomDepth.blocksEgoBaseline(
                    state.gameId,
                    state.getVar(Defines.CURROOM),
                    this.x,
                    this.x + this.xSize() - 1,
                    this.y)) {
                canBeHere = false;
            }

'''
if text.count(water_marker) != 1:
    raise RuntimeError(
        f'AnimatedObject water-check marker expected once, found {text.count(water_marker)}'
    )
text = text.replace(water_marker, modern_collision + water_marker)
animated_object.write_text(text)

print(
    f'Room 1 manual tree tuning applied: {tree_count} visual tree pixels; '
    'old tree blockers neutralised in corridor; collision only at root footprint Y=125..133'
)
