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
# The previous shoreline detector treated ANY cyan pixel in a center row as water.
# On diagonal creek edges that could follow a thin sliver of water too far upward,
# making the computed shoreline too high and keeping the drowning/swim cel on the
# bank. This version requires a MAJORITY of the center band to be water and gives
# the animation a little more immersion below that local painted surface.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
anchor = '''    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
helper = '''    private static final int WATER_VISUAL_MIN_SINK = 24;
    private static final int WATER_VISUAL_IMMERSION = 30;
    private static final int WATER_VISUAL_MAX_SINK = 44;

    /**
     * Visual-only downward offset for ego while custom WATER says he is swimming.
     *
     * Find the top edge of the painted WATER region underneath Graham's center,
     * requiring most of a narrow center band to be water. Requiring a majority is
     * important on diagonal banks: one stray cyan pixel must not drag the detected
     * shoreline upward. The swim/drown baseline is then placed about 30 AGI pixels
     * below that local surface. Logical AGI coordinates never change.
     */
    public static int waterVisualSink(GameState state, AnimatedObject obj) {
        if (obj == null || obj.objectNumber != 0 || !editorOwnsRoom(state)) return 0;
        VariableData data = state.getVariableData();
        if (!data.getSceneMaskWaterActive() || !state.getFlag(Defines.ONWATER)) return 0;

        int width = Math.max(1, obj.xSize());
        int height = Math.max(1, obj.ySize());
        int centerX = obj.x + (width / 2);
        int bandHalf = Math.max(1, Math.min(2, width / 4));
        int logicalY = obj.y;

        // Walk upward while a MAJORITY of the narrow center band is still water.
        // This rejects little diagonal water slivers that previously made the
        // detected surface several rows too high near the bridge/bank.
        int surfaceY = logicalY;
        while (surfaceY > 0) {
            int probeY = surfaceY - 1;
            int validCount = 0;
            int waterCount = 0;
            for (int x = centerX - bandHalf; x <= centerX + bandHalf; x++) {
                if (x < 0 || x >= 160) continue;
                validCount++;
                if (data.getSceneMaskBit(WATER, x, probeY)) waterCount++;
            }
            boolean mostlyWaterAbove = validCount > 0 && (waterCount * 2 > validCount);
            if (!mostlyWaterAbove) break;
            surfaceY--;
        }

        int preferredSink = (surfaceY + WATER_VISUAL_IMMERSION) - logicalY;
        if (preferredSink < WATER_VISUAL_MIN_SINK) preferredSink = WATER_VISUAL_MIN_SINK;
        if (preferredSink > WATER_VISUAL_MAX_SINK) preferredSink = WATER_VISUAL_MAX_SINK;

        int bestSink = preferredSink;
        int bestScore = Integer.MIN_VALUE;
        int from = Math.max(WATER_VISUAL_MIN_SINK, preferredSink - 6);
        int to = Math.min(WATER_VISUAL_MAX_SINK, preferredSink + 6);

        for (int sink = from; sink <= to; sink++) {
            int bottom = logicalY + sink;
            int top = bottom - height + 1;
            int lowerHalfTop = Math.max(top, bottom - Math.max(2, height / 2));
            int score = 0;

            // Score only the center of the cel. The wide drowning splash is allowed
            // to overlap bridge/bank pixels at its edges; the body itself should be
            // convincingly inside the painted water.
            for (int y = lowerHalfTop; y <= bottom; y++) {
                if (y < 0 || y >= 168) continue;
                for (int x = centerX - bandHalf; x <= centerX + bandHalf; x++) {
                    if (x < 0 || x >= 160) continue;
                    score += data.getSceneMaskBit(WATER, x, y) ? 6 : -7;
                }
            }

            // Strongly prefer the visible baseline and the row just above it to
            // both sit in water, which removes the remaining hovering-on-bank look.
            for (int y = bottom - 1; y <= bottom; y++) {
                if (y < 0 || y >= 168) continue;
                for (int x = centerX - bandHalf; x <= centerX + bandHalf; x++) {
                    if (x < 0 || x >= 160) continue;
                    score += data.getSceneMaskBit(WATER, x, y) ? 18 : -22;
                }
            }

            // Keep the result close to the shoreline-derived immersion depth.
            score -= Math.abs(sink - preferredSink) * 2;

            if (score > bestScore) {
                bestScore = score;
                bestSink = sink;
            }
        }

        return bestSink;
    }

    /** Extra repaint room so every possible shoreline-aligned cel is cleared. */
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
# It covers both the current shoreline-aligned sink and any previous sunk frame
# when Graham has just stepped back onto land.
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
print('Water animation alignment installed: majority-water shoreline plus 24-44px visual sink; logical position unchanged')
