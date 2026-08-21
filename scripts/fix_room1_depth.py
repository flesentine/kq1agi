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
# 2. Build a per-pixel modern visual-priority map from the actual Room 1 art.
#
# The previous implementation re-drew rectangular crops of the background on
# top of Graham. Those rectangles necessarily contained grass/meadow pixels, so
# Graham could be cut in half even when no tree pixel was present.
#
# Here we derive a 160x168 mask that contains only bark/trunk pixels from the
# modern right-side tree. Normal room pixels get visual priority 4 (actors draw
# over them). Tree pixels get priority 12, which restores AGI-style baseline
# depth: actors behind the tree are hidden by its painted pixels, while actors
# in front draw over it.
#
# This map is visual only. AGI's original control screen remains untouched for
# walking, water, blocking, room exits, scripts, and all game logic.
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

# Reduce to AGI's 160x168 priority plane. BOX averaging keeps small bark gaps
# from turning into giant rectangular occluders.
small = mask.resize((160, 168), Image.Resampling.BOX)
small_pixels = small.load()

tree_bits = [False] * (160 * 168)
tree_count = 0
for y in range(168):
    for x in range(160):
        covered = small_pixels[x, y] >= 48

        # Hard safety zone: this is open meadow immediately left of the tree.
        # The prior rectangle overlay crossed this area and produced the exact
        # "Graham cut in half with no tree" failure.
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
 * Visual-only priority replacement for rooms that use modern painted art.
 *
 * Generated at build time from the exact packaged room image. It deliberately
 * does not alter AGI control pixels or game logic.
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

    /**
     * Returns -1 when the original AGI visual priority should be used.
     * Otherwise returns the modern visual priority for this picture pixel.
     */
    public static int priorityFor(String gameId, int room, int x, int y) {
        if (!"KQ1".equalsIgnoreCase(gameId) || room != 1) {
            return -1;
        }
        if (x < 0 || x >= WIDTH || y < 0 || y >= HEIGHT) {
            return DEFAULT_PRIORITY;
        }

        int index = (y * WIDTH) + x;
        boolean tree = (ROOM1_TREE_BITS[index >>> 5] & (1 << (index & 31))) != 0;
        return tree ? ROOM1_TREE_PRIORITY : DEFAULT_PRIORITY;
    }
}
''')

# ---------------------------------------------------------------------------
# 3. Make dynamic actor drawing use the modern visual depth map instead of the
#    invisible original Room 1 picture priority geometry.
#
# Object sorting still provides actor-vs-actor ordering. state.priorityPixels
# is still updated/restored exactly as AGILE expects, so game state is not
# rewritten. Only the "may this sprite pixel be visible?" test is replaced.
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
animated_object.write_text(head + tail)

print(
    f'Room 1 modern depth applied: {tree_count} AGI tree pixels, '
    'legacy rectangle overlay removed, crocodiles suppressed'
)
