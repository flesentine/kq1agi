#!/usr/bin/env python3
from pathlib import Path
import sys

from PIL import Image

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_room1_depth.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

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
# 2. Build the per-pixel modern VISUAL priority map from the actual Room 1 art.
#
# IMPORTANT: visual depth and physical collision are deliberately separate.
# The tree can cover Graham while he walks behind it, but its tall trunk and
# branches must never act as a collision wall. Only the small root/base footprint
# defined later is physical.
#
# This returns to the last-known-good visual behaviour from commit 0769c946:
# no connected-component surgery and no broad hand-edited trunk removal.
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

# Reduce to AGI's true 160x168 priority plane. BOX averaging preserves the
# painted edge without the huge rectangular foreground regions used earlier.
small = mask.resize((160, 168), Image.Resampling.BOX)
small_pixels = small.load()

tree_bits = [False] * (160 * 168)
tree_count = 0
for y in range(168):
    for x in range(160):
        covered = small_pixels[x, y] >= 48

        # Open meadow immediately left of the lower tree must never become an
        # occluder. This is the safety rule from the last version that tested
        # substantially better on both sides of the tree.
        if (x < 126) and (y > 80):
            covered = False

        if covered:
            tree_bits[(y * 160) + x] = True
            tree_count += 1

if not (250 <= tree_count <= 4500):
    raise RuntimeError(f'Room 1 AGI tree mask looks implausible: {tree_count} pixels selected')

# Pack the boolean mask into Java int words for O(1) lookup in the interpreter.
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
 * Visual priority plus a small physical footprint for the modern Room 1 tree.
 *
 * The visual mask is generated from the painting. Physical collision is NOT the
 * full trunk: it is only the root/base footprint near the ground, so Graham can
 * freely walk behind the tree at smaller Y values.
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
     * The old painted tree's control geometry is replaced only near the roots.
     * Do NOT override control pixels up the vertical trunk: that was the bug that
     * trapped Graham too high on the Y/depth axis.
     */
    public static boolean overridesOriginalTreeBaseControl(
            String gameId, int room, int x, int y) {
        return roomOne(gameId, room)
                && x >= 126 && x <= 153
                && y >= 124 && y <= 140;
    }

    /**
     * Pixel-accurate enough physical footprint for the tree BASE only.
     *
     * These row extents follow the roots in the modern painting. The bottommost
     * blocked row is 135, so walking upward from the foreground naturally stops
     * with Graham's baseline at about Y=136. At Y=102 (the regression screenshot)
     * there is intentionally no collision at all: Graham is behind the tree there.
     */
    private static boolean treeBasePoint(int x, int y) {
        int left;
        int right;

        switch (y) {
            case 127: left = 137; right = 144; break;
            case 128: left = 135; right = 146; break;
            case 129: left = 134; right = 147; break;
            case 130: left = 133; right = 148; break;
            case 131: left = 132; right = 149; break;
            case 132: left = 132; right = 149; break;
            case 133: left = 132; right = 149; break;
            case 134: left = 133; right = 148; break;
            case 135: left = 135; right = 146; break;
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
# 4. Replace only the OLD TREE BASE collision geometry for ego.
#
# The previous attempt replaced a tall Y=86..132 region and used the trunk itself
# as collision. That made Graham get stuck while he was visually behind the tree.
# Here we neutralise Sierra's old tree block only near ground level and apply a
# small modern root footprint instead. All other objects and control lines are
# unchanged.
# ---------------------------------------------------------------------------
old_control = '''                // Get the priority screen priority value for this pixel of the base line.
                int priority = state.controlPixels[pixelPos];

                if (priority != 3) {
'''
new_control = '''                // Get Sierra's original control value for this baseline pixel.
                int priority = state.controlPixels[pixelPos];
                int baselineX = this.x + (pixelPos - startPixelPos);

                // Only ego gets the modern Room 1 tree-base collision replacement.
                if ((this.objectNumber == 0) && ModernRoomDepth.overridesOriginalTreeBaseControl(
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
modern_collision = '''            // Physical collision is only the modern painted tree's root/base
            // footprint. At smaller Y values Graham is behind the tree and must move freely.
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
    f'Room 1 modern depth/base collision applied: {tree_count} visual tree pixels; '
    'collision only at root footprint Y=127..135; crocodiles suppressed'
)
