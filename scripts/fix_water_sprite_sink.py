#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_water_sprite_sink.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# Keep the logical AGI baseline untouched. Only the pixels used to render ego are
# moved downward while ONWATER, so collision, room edges, scripts and the custom
# cyan WATER trigger continue to use Graham's real coordinates.
#
# A single global offset looked acceptable in one part of the room but failed
# around narrow/diagonal water near the bridge. Instead, evaluate several visual
# sink positions against the player's painted WATER mask and choose the position
# that places the sprite rectangle most convincingly inside the local water.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
anchor = '''    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
helper = '''    private static final int WATER_VISUAL_MIN_SINK = 10;
    private static final int WATER_VISUAL_PREFERRED_SINK = 14;
    private static final int WATER_VISUAL_MAX_SINK = 24;

    /**
     * Visual-only downward offset for ego while custom WATER says he is swimming.
     *
     * The cyan WATER mask is also our best description of the replacement art's
     * local shoreline. Test a small range of candidate draw positions and choose
     * the one whose sprite-sized rectangle overlaps the most painted water. This
     * adapts automatically to sloped/narrow banks instead of using one room-wide
     * magic number. Logical AGI coordinates are never changed.
     */
    public static int waterVisualSink(GameState state, AnimatedObject obj) {
        if (obj == null || obj.objectNumber != 0 || !editorOwnsRoom(state)) return 0;
        VariableData data = state.getVariableData();
        if (!data.getSceneMaskWaterActive() || !state.getFlag(Defines.ONWATER)) return 0;

        int width = Math.max(1, obj.xSize());
        int height = Math.max(1, obj.ySize());
        int left = obj.x;
        int right = left + width - 1;
        int logicalY = obj.y;

        int bestSink = WATER_VISUAL_PREFERRED_SINK;
        int bestScore = Integer.MIN_VALUE;

        for (int sink = WATER_VISUAL_MIN_SINK; sink <= WATER_VISUAL_MAX_SINK; sink++) {
            int top = logicalY + sink - height + 1;
            int bottom = logicalY + sink;
            int score = 0;

            // Score the full sprite rectangle. Water is rewarded more strongly
            // than land is penalised because transparent pixels are included in
            // the rectangle and should not make the heuristic too brittle.
            for (int y = top; y <= bottom; y++) {
                if (y < 0 || y >= 168) continue;
                for (int x = left; x <= right; x++) {
                    if (x < 0 || x >= 160) continue;
                    score += data.getSceneMaskBit(WATER, x, y) ? 4 : -2;
                }
            }

            // The lower two rows are where the swim/drown cel visually meets the
            // water. Give them extra weight so the sprite cannot hover on a bank.
            for (int y = Math.max(top, bottom - 1); y <= bottom; y++) {
                if (y < 0 || y >= 168) continue;
                for (int x = left; x <= right; x++) {
                    if (x < 0 || x >= 160) continue;
                    score += data.getSceneMaskBit(WATER, x, y) ? 7 : -8;
                }
            }

            // If coverage ties, prefer roughly 14px of immersion rather than
            // always snapping to the shallowest candidate.
            score -= Math.abs(sink - WATER_VISUAL_PREFERRED_SINK);

            if (score > bestScore) {
                bestScore = score;
                bestSink = sink;
            }
        }

        return bestSink;
    }

    /** Extra repaint room so every possible dynamically-sunk cel is cleared. */
    public static int waterVisualPadding(GameState state, AnimatedObject obj) {
        if (obj == null || obj.objectNumber != 0 || !editorOwnsRoom(state)) return 0;
        return state.getVariableData().getSceneMaskWaterActive() ? WATER_VISUAL_MAX_SINK : 0;
    }

    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
if text.count(anchor) != 1:
    raise RuntimeError('SceneMaskRuntime blocksEgoMovement anchor not found')
runtime.write_text(text.replace(anchor, helper))

animated = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
text = animated.read_text()

# Patch only the normal animated-object draw path (not add.to.pic). The source
# pixels and SaveArea are both based on drawY so restoration stays exact.
draw_anchor = '''        // Calculate starting screen offset. AGI pixels are 2x1 within the picture area.
        int aniObjTop = ((this.y - cellHeight) + 1);
        int screenPos = (aniObjTop * 320) + (this.x * 2);
        int screenLineAdd = 320 - (cellWidth << 1);

        // Calculate starting position within the priority screen.
        int priorityPos = (aniObjTop * 160) + this.x;
'''
draw_repl = '''        // Calculate starting screen offset. AGI pixels are 2x1 within the picture area.
        int waterVisualSink = SceneMaskRuntime.waterVisualSink(state, this);
        int drawY = this.y + waterVisualSink;
        int aniObjTop = ((drawY - cellHeight) + 1);
        int screenPos = (aniObjTop * 320) + (this.x * 2);
        int screenLineAdd = 320 - (cellWidth << 1);

        // Calculate starting position within the priority screen.
        int priorityPos = (aniObjTop * 160) + this.x;
'''
if text.count(draw_anchor) != 1:
    raise RuntimeError('AnimatedObject normal draw screen-offset anchor not found')
text = text.replace(draw_anchor, draw_repl)

save_anchor = '''        this.saveArea.x = this.x;
        this.saveArea.y = this.y;
        this.saveArea.width = cellWidth;
'''
save_repl = '''        this.saveArea.x = this.x;
        this.saveArea.y = (short)drawY;
        this.saveArea.width = cellWidth;
'''
if text.count(save_anchor) != 1:
    raise RuntimeError('AnimatedObject SaveArea draw anchor not found')
text = text.replace(save_anchor, save_repl)

# show() copies a taller rectangle for ego whenever a custom water mask exists.
# It covers both the current dynamic sink and any previous sunk frame when Graham
# has just stepped back onto land.
show_anchor = '''            int topmostY = Math.min(prevY - prevCelHeight, this.y - this.ySize()) + 1;
            int bottommostY = Math.max(prevY, this.y);
'''
show_repl = '''            int topmostY = Math.min(prevY - prevCelHeight, this.y - this.ySize()) + 1;
            int waterVisualPadding = SceneMaskRuntime.waterVisualPadding(state, this);
            int bottommostY = Math.max(prevY, this.y) + waterVisualPadding;
'''
if text.count(show_anchor) != 1:
    raise RuntimeError('AnimatedObject show bounds anchor not found')
text = text.replace(show_anchor, show_repl)

animated.write_text(text)
print('Dynamic water animation alignment installed: local painted WATER coverage chooses 10-24px visual sink; logical position unchanged')
