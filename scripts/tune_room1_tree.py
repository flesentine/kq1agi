#!/usr/bin/env python3
from pathlib import Path
import sys

from PIL import Image, ImageFilter

if len(sys.argv) != 2:
    raise SystemExit('usage: tune_room1_tree.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# ---------------------------------------------------------------------------
# Room 1 tree: real foreground overlay, not a priority-mask approximation.
#
# The modern room painting remains the base image. Graham is rendered whole by
# AGILE. When his baseline is behind the tree, we draw a transparent texture
# containing the actual painted tree over the completed AGI frame. When he is in
# front, that overlay pass is omitted. Collision is a separate closed footprint.
# ---------------------------------------------------------------------------
background = root / 'assets/backgrounds/room_001_hires.png'
if not background.exists():
    raise RuntimeError(f'Modern Room 1 background not found: {background}')

with Image.open(background) as source_image:
    source = source_image.convert('RGB')

width, height = source.size
if (width, height) != (1586, 992):
    raise RuntimeError(f'Unexpected Room 1 background size: {(width, height)}')

pixels = source.load()
seed = Image.new('L', (width, height), 0)
seed_pixels = seed.load()

# Strict wood key. This intentionally avoids the dark green grass/shadow pixels
# that made the old priority mask eat pieces of Graham on the tree's left side.
x0 = int(width * 0.69)
x1 = width
y0 = int(height * 0.02)
y1 = int(height * 0.86)

selected = 0
for y in range(y0, y1):
    for x in range(x0, x1):
        r, g, b = pixels[x, y]
        wood = (
            r >= (g * 0.94)
            and r >= (b * 1.16)
            and (r - b) >= 20
            and r >= 50
        )
        if wood:
            seed_pixels[x, y] = 255
            selected += 1

if not (18000 <= selected <= 110000):
    raise RuntimeError(f'Room 1 tree key looks implausible: {selected} source pixels selected')

# Grow the strict key by a few source pixels to catch antialiased bark edges.
mask = seed.filter(ImageFilter.MaxFilter(5))
mask_pixels = mask.load()

def source_x(agi_x):
    return max(0, min(width - 1, round((agi_x / 160.0) * width)))

def agi_y(source_y):
    return max(0, min(167, int((source_y / float(height)) * 168)))

# Make the trunk body a continuous silhouette. We still take the outline from
# the real keyed painting, but fill inside it so bark highlights/shadows cannot
# create holes through Graham. Limit edge jumps row-to-row to reject grass noise.
corridor_left = source_x(122)
corridor_right = source_x(156)
max_jump = max(2, width // 400)
previous_left = None
previous_right = None

for y in range(height):
    ay = agi_y(y)
    if ay < 88 or ay > 142:
        continue

    xs = [
        x for x in range(corridor_left, corridor_right + 1)
        if seed_pixels[x, y] > 0
    ]
    if not xs:
        continue

    left = min(xs)
    right = max(xs)

    if previous_left is not None:
        left = max(previous_left - max_jump, min(previous_left + max_jump, left))
        right = max(previous_right - max_jump, min(previous_right + max_jump, right))

    if right <= left:
        continue

    for x in range(corridor_left, corridor_right + 1):
        mask_pixels[x, y] = 0
    for x in range(left, right + 1):
        mask_pixels[x, y] = 255

    previous_left = left
    previous_right = right

# Keep only the right-side tree area. There is no legitimate foreground tree
# overlay to the left of this point in Room 1.
for y in range(height):
    for x in range(0, source_x(108)):
        mask_pixels[x, y] = 0

# Build a full-size transparent overlay using the exact painted pixels.
overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
overlay_pixels = overlay.load()
for y in range(height):
    for x in range(x0, width):
        alpha = mask_pixels[x, y]
        if alpha:
            r, g, b = pixels[x, y]
            overlay_pixels[x, y] = (r, g, b, alpha)

overlay_path = root / 'assets/backgrounds/room_001_tree_overlay.png'
overlay.save(overlay_path, format='PNG', optimize=True)

# Derive a closed collision footprint from the keyed trunk near the ground.
# This is intentionally independent of the visual overlay. Rows 123..139 form
# the solid object body: back, front, left and right approaches all collide.
small = mask.resize((160, 168), Image.Resampling.BOX)
small_pixels = small.load()
collision_rows = {}
fallback_left, fallback_right = 132, 152

for y in range(123, 140):
    xs = [
        x for x in range(120, 159)
        if small_pixels[x, y] >= 24
    ]
    if xs:
        left = max(0, min(xs) - 1)
        right = min(159, max(xs) + 1)
        # Refuse implausible single-row spikes from the key.
        left = max(124, min(145, left))
        right = max(left + 6, min(156, right))
        collision_rows[y] = (left, right)
        fallback_left, fallback_right = left, right
    else:
        collision_rows[y] = (fallback_left, fallback_right)

cases = '\n'.join(
    f'            case {y}: return x >= {left} && x <= {right};'
    for y, (left, right) in collision_rows.items()
)

# ---------------------------------------------------------------------------
# Replace the generated ModernRoomDepth with a much simpler model:
# - Room 1 actor pixels always draw whole (priority 4).
# - Sierra's old invisible tree blockers are neutralised in the old corridor.
# - The modern tree uses a separate closed collision body.
# ---------------------------------------------------------------------------
modern_depth = root / 'core/src/main/java/com/agifans/agile/ModernRoomDepth.java'
modern_depth.write_text(f'''package com.agifans.agile;

/**
 * Modern Room 1 tree behaviour.
 *
 * Visual occlusion is handled by a real transparent tree overlay in GameScreen,
 * not by clipping individual AGI sprite pixels against a synthetic priority map.
 * Collision is a separate closed footprint around the trunk.
 */
public final class ModernRoomDepth {{
    private static final int DEFAULT_PRIORITY = 4;

    private ModernRoomDepth() {{
    }}

    private static boolean roomOne(String gameId, int room) {{
        return "KQ1".equalsIgnoreCase(gameId) && room == 1;
    }}

    /**
     * In modern Room 1, never clip an actor against Sierra's invisible original
     * picture priorities. The foreground tree is composited later as a texture.
     */
    public static int priorityFor(String gameId, int room, int x, int y) {{
        return roomOne(gameId, room) ? DEFAULT_PRIORITY : -1;
    }}

    /**
     * Sierra's old tree/control geometry does not line up with the new painting.
     * The caller only neutralises blocking colours 0/1; water and specials remain.
     */
    public static boolean insideOldTreeControlCorridor(
            String gameId, int room, int x, int y) {{
        return roomOne(gameId, room)
                && x >= 120 && x <= 156
                && y >= 72 && y <= 145;
    }}

    /**
     * Closed physical body around the modern tree trunk. This blocks side, back
     * and front approaches while still allowing Graham to travel behind the tree.
     */
    private static boolean treeBasePoint(int x, int y) {{
        switch (y) {{
{cases}
            default: return false;
        }}
    }}

    public static boolean blocksEgoBaseline(
            String gameId, int room, int leftX, int rightX, int baselineY) {{
        if (!roomOne(gameId, room)) {{
            return false;
        }}

        int left = Math.max(0, Math.min(leftX, rightX));
        int right = Math.min(159, Math.max(leftX, rightX));
        for (int x = left; x <= right; x++) {{
            if (treeBasePoint(x, baselineY)) {{
                return true;
            }}
        }}
        return false;
    }}
}}
''')

# ---------------------------------------------------------------------------
# Shared UI/worker flag: the worker knows Graham's real AGI baseline; GameScreen
# on the UI thread needs one boolean telling it whether to draw the tree overlay.
# ---------------------------------------------------------------------------
variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
text = variable_data.read_text()
marker = '''    boolean getInTick();
    
}'''
replacement = '''    boolean getInTick();

    /**
     * Optional renderer hint shared by platform implementations. The browser
     * build uses it to composite modern foreground artwork after AGI actors.
     */
    default boolean getModernRoomOverlay() {
        return false;
    }

    default void setModernRoomOverlay(boolean value) {
        // Optional platform hook.
    }
    
}'''
if text.count(marker) != 1:
    raise RuntimeError('VariableData tail marker not found')
variable_data.write_text(text.replace(marker, replacement))

gwt_variable = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt_variable.read_text()

text = text.replace(
    '    private static final int IN_TICK = 517;\n',
    '    private static final int IN_TICK = 517;\n'
    '    private static final int MODERN_ROOM_OVERLAY = 518;\n'
)
if text.count('Defines.NUMVARS + Defines.NUMFLAGS + 6') != 2:
    raise RuntimeError('GwtVariableData shared-array capacity sites not found')
text = text.replace(
    'Defines.NUMVARS + Defines.NUMFLAGS + 6',
    'Defines.NUMVARS + Defines.NUMFLAGS + 7'
)

tail = '''    @Override
    public boolean getInTick() {
        return (variableArray.get(IN_TICK) == TRUE);
    }

    /**
     * Gets the SharedArrayBuffer used internally by the variable array.
'''
new_tail = '''    @Override
    public boolean getInTick() {
        return (variableArray.get(IN_TICK) == TRUE);
    }

    @Override
    public boolean getModernRoomOverlay() {
        return (variableArray.get(MODERN_ROOM_OVERLAY) == TRUE);
    }

    @Override
    public void setModernRoomOverlay(boolean value) {
        variableArray.set(MODERN_ROOM_OVERLAY, value ? TRUE : FALSE);
    }

    /**
     * Gets the SharedArrayBuffer used internally by the variable array.
'''
if text.count(tail) != 1:
    raise RuntimeError('GwtVariableData getInTick tail not found')
gwt_variable.write_text(text.replace(tail, new_tail))

# Publish the overlay flag immediately before objects are redrawn each frame.
game_state = root / 'core/src/main/java/com/agifans/agile/GameState.java'
text = game_state.read_text()
old = '''    public void drawObjects() {
        // If no list specified, then draw stopped list then update list.
        drawObjects(makeStoppedObjectList());
        drawObjects(makeUpdateObjectList());
    }
'''
new = '''    public void drawObjects() {
        // Room 1 foreground tree: Graham is behind it until his baseline reaches
        // the solid trunk body. The UI thread composites the real painted tree
        // texture after AGI actors only while this flag is true.
        boolean modernTreeOverlay =
                "KQ1".equalsIgnoreCase(gameId)
                && (getVar(Defines.CURROOM) == 1)
                && pictureVisible
                && (ego != null)
                && ego.drawn
                && (ego.y <= 122);
        variableData.setModernRoomOverlay(modernTreeOverlay);

        // If no list specified, then draw stopped list then update list.
        drawObjects(makeStoppedObjectList());
        drawObjects(makeUpdateObjectList());
    }
'''
if text.count(old) != 1:
    raise RuntimeError('GameState drawObjects() block not found')
game_state.write_text(text.replace(old, new))

# ---------------------------------------------------------------------------
# Tiny foreground texture cache.
# ---------------------------------------------------------------------------
room_overlays = root / 'core/src/main/java/com/agifans/agile/RoomOverlays.java'
room_overlays.write_text(r'''package com.agifans.agile;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.graphics.Texture;

/** Loads foreground art that must sometimes be composited over AGI actors. */
public final class RoomOverlays {
    private static Texture room1Tree;
    private static boolean room1TreeChecked;

    private RoomOverlays() {
    }

    public static Texture getTreeOverlay(int room) {
        if (room != 1) {
            return null;
        }
        if (room1Tree != null) {
            return room1Tree;
        }
        if (room1TreeChecked) {
            return null;
        }

        room1TreeChecked = true;
        FileHandle file = Gdx.files.internal("backgrounds/room_001_tree_overlay.png");
        if (!file.exists()) {
            return null;
        }

        room1Tree = new Texture(file);
        room1Tree.setFilter(Texture.TextureFilter.Linear, Texture.TextureFilter.Linear);
        return room1Tree;
    }
}
''')

# ---------------------------------------------------------------------------
# Render order:
#   painted room -> complete alpha-masked AGI frame -> real tree overlay (behind)
#
# The AGI frame is never pixel-clipped by the tree anymore.
# ---------------------------------------------------------------------------
game_screen = root / 'core/src/main/java/com/agifans/agile/GameScreen.java'
text = game_screen.read_text()
old = '''        batch.begin();
        batch.draw(
                getDrawScreen(),
                0, 0, ADJUSTED_WIDTH, ADJUSTED_HEIGHT,
                0, 0, AGI_SCREEN_WIDTH, AGI_SCREEN_HEIGHT,
                false, false);
        batch.end();
'''
new = '''        batch.begin();
        batch.draw(
                getDrawScreen(),
                0, 0, ADJUSTED_WIDTH, ADJUSTED_HEIGHT,
                0, 0, AGI_SCREEN_WIDTH, AGI_SCREEN_HEIGHT,
                false, false);
        batch.end();

        // Composite the ACTUAL painted Room 1 tree after the complete AGI frame
        // when Graham is behind it. No sprite cropping or synthetic depth mask.
        int currentRoom = agileRunner.getVariableData().getVar(Defines.CURROOM);
        Texture roomOverlay = RoomOverlays.getTreeOverlay(currentRoom);
        if ((roomOverlay != null) && agileRunner.getVariableData().getModernRoomOverlay()) {
            batch.enableBlending();
            batch.begin();
            batch.setColor(c.r, c.g, c.b, 1f);
            batch.draw(
                    roomOverlay,
                    0, 24, ADJUSTED_WIDTH, 168,
                    0, 0, roomOverlay.getWidth(), roomOverlay.getHeight(),
                    false, false);
            batch.end();
        }
'''
if text.count(old) != 1:
    raise RuntimeError('GameScreen AGI foreground draw block not found')
game_screen.write_text(text.replace(old, new))

print(
    f'Room 1 tree overlay generated ({selected} keyed source pixels); '
    f'closed collision rows={collision_rows}; visual priority clipping disabled'
)
