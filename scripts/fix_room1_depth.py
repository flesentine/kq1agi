#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_room1_depth.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# ---------------------------------------------------------------------------
# 1. Temporarily suppress Room 1 water-only animated objects.
#
# In King's Quest I the crocodiles in the opening room are water-bound AGI
# animated objects. Filtering them at the object-list level is safer than a
# screen-coordinate mask: ego is explicitly excluded and the interpreter can
# continue updating the objects logically without painting their old EGA cels
# over the modern room art.
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
     * object lists while a modern Room 1 background is in use.
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
# 2. Draw selected pieces of the same high-resolution background again after
#    the AGI actor layer. This provides a conservative foreground/depth pass
#    without requiring a second large transparent PNG asset.
#
# Coordinates below are in the 1586x992 modern master image. The helper maps
# them to AGI's displayed 264x168 picture rectangle. They intentionally cover
# only obvious foreground geometry: the tree trunk/root mass and the front lip
# of the bridge.
# ---------------------------------------------------------------------------
game_screen = root / 'core/src/main/java/com/agifans/agile/GameScreen.java'
text = game_screen.read_text()

old_room = '''        Texture roomBackground = RoomBackgrounds.getTexture(
                agileRunner.getVariableData().getVar(Defines.CURROOM));
'''
new_room = '''        int currentRoom = agileRunner.getVariableData().getVar(Defines.CURROOM);
        Texture roomBackground = RoomBackgrounds.getTexture(currentRoom);
'''
if text.count(old_room) != 1:
    raise RuntimeError('GameScreen room-background lookup block not found')
text = text.replace(old_room, new_room)

pattern = re.compile(
    r'''(        batch\.begin\(\);\n'''
    r'''        batch\.draw\(\n'''
    r'''                getDrawScreen\(\),\n'''
    r'''                0, 0, ADJUSTED_WIDTH, ADJUSTED_HEIGHT,\n'''
    r'''                0, 0, AGI_SCREEN_WIDTH, AGI_SCREEN_HEIGHT,\n'''
    r'''                false, false\);\n)'''
    r'''(        batch\.end\(\);)'''
)
match = pattern.search(text)
if not match:
    raise RuntimeError('GameScreen AGI screen draw block not found')
replacement = match.group(1) + '''
        // A small Room 1 foreground pass restores believable occlusion where
        // the modern painting differs slightly from Sierra's original priority
        // geometry. Re-use the same background texture; no second image asset
        // or additional browser download is required.
        if ((currentRoom == 1) && (roomBackground != null)) {
            drawRoomOneForegroundDepth(batch, roomBackground);
        }
''' + match.group(2)
text = text[:match.start()] + replacement + text[match.end():]

method_marker = '''    private void draw(float delta) {
'''
methods = '''    /** Draws only the modern Room 1 pixels that should sit in front of ego. */
    private void drawRoomOneForegroundDepth(SpriteBatch batch, Texture texture) {
        // Right-side tree. Use several narrow crops that hug the forked trunk
        // instead of one broad rectangle, so the open meadow remains visible.
        drawRoomCrop(batch, texture, 1165, 250, 75, 285);
        drawRoomCrop(batch, texture, 1205, 455, 95, 320);
        drawRoomCrop(batch, texture, 1285, 180, 90, 430);
        drawRoomCrop(batch, texture, 1240, 605, 125, 195);

        // Front/lower lip of the wooden bridge. These thin stepped crops follow
        // the near edge without repainting the whole bridge deck over Graham.
        drawRoomCrop(batch, texture, 915, 875, 145, 55);
        drawRoomCrop(batch, texture, 1035, 900, 155, 55);
        drawRoomCrop(batch, texture, 1170, 900, 155, 60);
        drawRoomCrop(batch, texture, 1305, 865, 115, 55);
    }

    /**
     * Re-draw one source rectangle from a modern room image in exactly the
     * same place it occupies in the 264x168 AGI picture area.
     */
    private void drawRoomCrop(SpriteBatch batch, Texture texture,
            int srcX, int srcY, int srcWidth, int srcHeight) {
        float xScale = ADJUSTED_WIDTH / (float)texture.getWidth();
        float yScale = 168f / (float)texture.getHeight();
        float x = srcX * xScale;
        float y = 24f + ((texture.getHeight() - (srcY + srcHeight)) * yScale);
        float width = srcWidth * xScale;
        float height = srcHeight * yScale;

        batch.draw(
                texture,
                x, y, width, height,
                srcX, srcY, srcWidth, srcHeight,
                false, false);
    }

'''
if text.count(method_marker) != 1:
    raise RuntimeError('GameScreen draw method marker not found')
text = text.replace(method_marker, methods + method_marker)
game_screen.write_text(text)

print('Room 1 depth pass and crocodile suppression applied successfully')
