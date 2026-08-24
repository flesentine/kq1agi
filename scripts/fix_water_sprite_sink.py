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
# The previous dynamic scorer considered the full width of the swim/drown cel.
# Those cels are much wider than walking Graham, so near a bridge or narrow bank
# the land beside the water could incorrectly pull the sprite upward. This version
# tracks the local painted shoreline under Graham's CENTER instead, then places the
# visual baseline a fixed immersion depth below that shoreline. A small center-band
# score refines the result without letting the wide splash art bias the placement.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
anchor = '''    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
helper = '''    private static final int WATER_VISUAL_MIN_SINK = 18;
    private static final int WATER_VISUAL_IMMERSION = 24;
    private static final int WATER_VISUAL_MAX_SINK = 36;

    /**
     * Visual-only downward offset for ego while custom WATER says he is swimming.
     *
     * Find the top edge of the painted WATER region at the center of Graham, then
     * place the swim/drown cel baseline about 24 AGI pixels below that local water
     * surface. We intentionally use only a narrow center band: the drowning splash
     * cel is much wider than walking Graham and may overlap bridge/bank pixels that
     * should not pull the animation upward. Logical AGI coordinates never change.
     */
    public static int waterVisualSink(GameState state, AnimatedObject obj) {
        if (obj == null || obj.objectNumber != 0 || !editorOwnsRoom(state)) return 0;
        VariableData data = state.getVariableData();
        if (!data.getSceneMaskWaterActive() || !state.getFlag(Defines.ONWATER)) return 0;

        int width = Math.max(1, obj.xSize());
        int height = Math.max(1, obj.ySize());
        int centerX = obj.x + (width / 2);
        int bandHalf = Math.max(1, Math.min(3, width / 4));
        int logicalY = obj.y;

        // Walk upward from ego's logical baseline until the narrow center band is
        // no longer water. The first water row below that is the local shoreline.
        int surfaceY = logicalY;
        while (surfaceY > 0) {
            boolean waterAbove = false;
            int probeY = surfaceY - 1;
            for (int x = centerX - bandHalf; x <= centerX + bandHalf; x++) {
                if (x >= 0 && x < 160 && data.getSceneMaskBit(WATER, x, probeY)) {
                    waterAbove = true;
                    break;
                }
            }
            if (!waterAbove) break;
            surfaceY--;
        }

        int preferredSink = (surfaceY + WATER_VISUAL_IMMERSION) - logicalY;
        if (preferredSink < WATER_VISUAL_MIN_SINK) preferredSink = WATER_VISUAL_MIN_SINK;
        if (preferredSink > WATER_VISUAL_MAX_SINK) preferredSink = WATER_VISUAL_MAX_SINK;

        int bestSink = preferredSink;
        int bestScore = Integer.MIN_VALUE;
        int from = Math.max(WATER_VISUAL_MIN_SINK, preferredSink - 5);
        int to = Math.min(WATER_VISUAL_MAX_SINK, preferredSink + 5);

        for (int sink = from; sink <= to; sink++) {
            int bottom = logicalY + sink;
            int top = bottom - height + 1;
            int lowerHalfTop = Math.max(top, bottom - Math.max(2, height / 2));
            int score = 0;

            // Only score the middle of the cel. This keeps a wide splash from
            // being repelled by legitimate land/bridge pixels at its left/right.
            for (int y = lowerHalfTop; y <= bottom; y++) {
                if (y < 0 || y >= 168) continue;
                for (int x = centerX - bandHalf; x <= centerX + bandHalf; x++) {
                    if (x < 0 || x >= 160) continue;
                    score += data.getSceneMaskBit(WATER, x, y) ? 5 : -6;
                }
            }

            // Strongly prefer the visible baseline itself to be well inside water.
            if (bottom >= 0 && bottom < 168) {
                for (int x = centerX - bandHalf; x <= centerX + bandHalf; x++) {
                    if (x < 0 || x >= 160) continue;
                    score += data.getSceneMaskBit(WATER, x, bottom) ? 14 : -18;
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
print('Water animation shoreline alignment installed: center-band painted WATER surface chooses 18-36px sink; logical position unchanged')
