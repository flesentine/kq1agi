#!/usr/bin/env python3
from collections import deque
from pathlib import Path
import sys

from PIL import Image

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_room1_depth.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()


def largest_connected_component(bits, width, height):
    """Keep only the largest 4-connected component in a boolean bitmap."""
    seen = [False] * (width * height)
    best = []

    for y in range(height):
        for x in range(width):
            start = (y * width) + x
            if not bits[start] or seen[start]:
                continue

            queue = deque([(x, y)])
            seen[start] = True
            component = []

            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))

                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    index = (ny * width) + nx
                    if bits[index] and not seen[index]:
                        seen[index] = True
                        queue.append((nx, ny))

            if len(component) > len(best):
                best = component

    cleaned = [False] * (width * height)
    for x, y in best:
        cleaned[(y * width) + x] = True
    return cleaned


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


def pack_bits(bits):
    words = [0] * ((len(bits) + 31) // 32)
    for index, covered in enumerate(bits):
        if covered:
            words[index >> 5] |= (1 << (index & 31))
    return words


def java_word_lines(words):
    lines = []
    for start in range(0, len(words), 8):
        chunk = words[start:start + 8]
        lines.append('        ' + ', '.join(f'0x{word & 0xFFFFFFFF:08X}' for word in chunk))
    return ',\n'.join(lines)


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
# 2. Build per-pixel modern visual and collision masks from the actual Room 1
#    painting.
#
# The visual mask contains only the painted tree silhouette. The collision mask
# is separate and uses only the lower/mid trunk, so canopy pixels do not block
# Graham. This lets the modern room replace both invisible AGI tree occlusion
# and the old tree's mismatched control-line collision while leaving every other
# AGI control region intact.
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

# Broad ROI around the modern tree. Colour tests below remove meadow/grass.
x0 = int(width * 0.695)
x1 = width
y0 = int(height * 0.035)
y1 = int(height * 0.79)

selected = 0
for y in range(y0, y1):
    for x in range(x0, x1):
        r, g, b = pixels[x, y]
        brightest = max(r, g, b)

        # Bark is orange/brown/grey-brown: red is close to or above green and
        # clearly above blue. The second clause keeps very dark bark/shadow.
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

# Reduce to AGI's true 160x168 priority/control plane.
small = mask.resize((160, 168), Image.Resampling.BOX)
small_pixels = small.load()

raw_tree_bits = [False] * (160 * 168)
for y in range(168):
    for x in range(160):
        covered = small_pixels[x, y] >= 48

        # Hard safety zone: open meadow immediately left of the trunk. The old
        # rectangle overlay crossed this area and caused the original clipping.
        if (x < 126) and (y > 80):
            covered = False

        raw_tree_bits[(y * 160) + x] = covered

# Keep only the real connected tree silhouette. This removes detached bark-like
# islands created by grass/shadow colours in the source painting.
tree_bits = largest_connected_component(raw_tree_bits, 160, 168)

# Hand-tuned cleanup for the specific bad left edge visible in play testing.
# In rows 80..108 the real trunk is the rightmost substantial run; detached
# runs to its left are false occluders and must never erase Graham.
for y in range(80, 109):
    runs = row_runs(tree_bits, 160, y)
    if len(runs) <= 1:
        continue

    right_start, right_end = runs[-1]
    if (right_end - right_start + 1) >= 6:
        base = y * 160
        for start, end in runs[:-1]:
            for x in range(start, end + 1):
                tree_bits[base + x] = False

tree_count = sum(1 for covered in tree_bits if covered)
if not (250 <= tree_count <= 4500):
    raise RuntimeError(f'Room 1 AGI tree mask looks implausible: {tree_count} pixels selected')

# Build a separate solid collision silhouette from only the lower/mid trunk.
# Filling each row between the left/right bark edges intentionally closes small
# texture holes: Graham should collide with the physical trunk, not slip through
# a dark painted crack. One AGI pixel of padding gives a natural stop point.
block_bits = [False] * (160 * 168)
for y in range(88, 131):
    xs = [x for x in range(128, 151) if tree_bits[(y * 160) + x]]
    if not xs:
        continue

    left = max(0, min(xs) - 1)
    right = min(159, max(xs) + 1)
    base = y * 160
    for x in range(left, right + 1):
        block_bits[base + x] = True

# Close one-row pinholes without widening the sides.
for y in range(89, 130):
    for x in range(128, 151):
        index = (y * 160) + x
        if (
            not block_bits[index]
            and block_bits[((y - 1) * 160) + x]
            and block_bits[((y + 1) * 160) + x]
        ):
            block_bits[index] = True

block_count = sum(1 for blocked in block_bits if blocked)
if not (250 <= block_count <= 1000):
    raise RuntimeError(f'Room 1 tree collision mask looks implausible: {block_count} pixels selected')

tree_word_lines = java_word_lines(pack_bits(tree_bits))
block_word_lines = java_word_lines(pack_bits(block_bits))

modern_depth = root / 'core/src/main/java/com/agifans/agile/ModernRoomDepth.java'
modern_depth.write_text('''package com.agifans.agile;

/**
 * Visual priority and collision replacement for rooms that use modern painted art.
 *
 * Generated at build time from the exact packaged room image. Room 1 keeps the
 * original AGI control screen everywhere except the narrow area occupied by the
 * repainted tree, where the modern trunk collision silhouette is authoritative.
 */
public final class ModernRoomDepth {
    private static final int WIDTH = 160;
    private static final int HEIGHT = 168;
    private static final int DEFAULT_PRIORITY = 4;
    private static final int ROOM1_TREE_PRIORITY = 12;

    private static final int[] ROOM1_TREE_BITS = new int[] {
''' + tree_word_lines + '''
    };

    private static final int[] ROOM1_TREE_BLOCK_BITS = new int[] {
''' + block_word_lines + '''
    };

    private ModernRoomDepth() {
    }

    private static boolean roomOne(String gameId, int room) {
        return "KQ1".equalsIgnoreCase(gameId) && room == 1;
    }

    private static boolean bitAt(int[] bits, int x, int y) {
        if (x < 0 || x >= WIDTH || y < 0 || y >= HEIGHT) {
            return false;
        }
        int index = (y * WIDTH) + x;
        return (bits[index >>> 5] & (1 << (index & 31))) != 0;
    }

    /**
     * Returns -1 when the original AGI visual priority should be used.
     * Otherwise returns the modern visual priority for this picture pixel.
     */
    public static int priorityFor(String gameId, int room, int x, int y) {
        if (!roomOne(gameId, room)) {
            return -1;
        }
        if (x < 0 || x >= WIDTH || y < 0 || y >= HEIGHT) {
            return DEFAULT_PRIORITY;
        }
        return bitAt(ROOM1_TREE_BITS, x, y) ? ROOM1_TREE_PRIORITY : DEFAULT_PRIORITY;
    }

    /**
     * The original KQ1 Room 1 control map blocks Graham against Sierra's old
     * tree geometry. In this narrow trunk zone, neutralise only those old
     * control pixels and let the painted-tree collision mask below decide.
     */
    public static boolean overridesOriginalControl(String gameId, int room, int x, int y) {
        return roomOne(gameId, room)
                && x >= 124 && x <= 151
                && y >= 86 && y <= 132;
    }

    /** True when any pixel of an object's AGI baseline overlaps the painted trunk. */
    public static boolean blocksBaseline(
            String gameId, int room, int leftX, int rightX, int baselineY) {
        if (!roomOne(gameId, room) || baselineY < 0 || baselineY >= HEIGHT) {
            return false;
        }

        int left = Math.max(0, Math.min(leftX, rightX));
        int right = Math.min(WIDTH - 1, Math.max(leftX, rightX));
        for (int x = left; x <= right; x++) {
            if (bitAt(ROOM1_TREE_BLOCK_BITS, x, baselineY)) {
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
                    // the old EGA picture. Use its generated visual depth map instead.
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
# 4. Replace only the old tree's mismatched control geometry with the modern
#    trunk collision mask. Water, exits, special control lines, blocks, and all
#    other room logic continue to use Sierra's original control pixels.
# ---------------------------------------------------------------------------
old_control = '''                // Get the priority screen priority value for this pixel of the base line.
                int priority = state.controlPixels[pixelPos];

                if (priority != 3) {
'''
new_control = '''                // Get Sierra's original control value for this baseline pixel.
                int priority = state.controlPixels[pixelPos];
                int baselineX = this.x + (pixelPos - startPixelPos);

                // The replacement painting moved the Room 1 tree slightly. Neutralise the
                // old tree control pixels only inside its narrow override zone; the modern
                // trunk mask is applied immediately after the baseline scan.
                if (ModernRoomDepth.overridesOriginalControl(
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
modern_collision = '''            // In the repainted tree zone, collide against the actual painted trunk
            // rather than Sierra's now-invisible tree control geometry.
            if (canBeHere && ModernRoomDepth.blocksBaseline(
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
    f'Room 1 modern depth/collision applied: {tree_count} visual tree pixels, '
    f'{block_count} trunk collision pixels, crocodiles suppressed'
)
