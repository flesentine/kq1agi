#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_water_sprite_sink.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# Keep the logical AGI baseline untouched. Only the pixels used to render ego are
# moved downward while the actual horizontal swim/drown cel is being displayed.
#
# Important: ONWATER becomes true slightly before KQ1 swaps Graham from his normal
# walking cel to the water animation. The old patch applied the sink as soon as the
# flag changed, so the normal walking Graham visibly jumped downward for a frame and
# then snapped again when the wide swim/drown cel arrived. Gate the visual sink by
# cel shape so normal standing/walking Graham is NEVER shifted; only the character's
# distinctly horizontal water cels get the replacement-art alignment.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
anchor = '''    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
helper = '''    private static final int WATER_VISUAL_MIN_SINK = 24;
    private static final int WATER_VISUAL_IMMERSION = 30;
    private static final int WATER_VISUAL_MAX_SINK = 44;

    /**
     * KQ1's water cels are wide/horizontal, while normal walking Graham is narrow
     * and tall. ONWATER can turn on before the view change, so this guard prevents
     * the normal walking cel from being visually sunk during that transition.
     */
    private static boolean isWaterAnimationCel(AnimatedObject obj) {
        if (obj == null) return false;
        int width = Math.max(1, obj.xSize());
        int height = Math.max(1, obj.ySize());
        return width >= 8 && width >= height;
    }

    /**
     * Visual-only downward offset for ego while the custom WATER mask is active and
     * KQ1 is actually displaying a horizontal swim/drown cel. Graham's logical AGI
     * coordinates are never changed.
     */
    public static int waterVisualSink(GameState state, AnimatedObject obj) {
        if (obj == null || obj.objectNumber != 0 || !editorOwnsRoom(state)) return 0;
        VariableData data = state.getVariableData();
        if (!data.getSceneMaskWaterActive() || !state.getFlag(Defines.ONWATER)) return 0;
        if (!isWaterAnimationCel(obj)) return 0;

        int width = Math.max(1, obj.xSize());
        int height = Math.max(1, obj.ySize());
        int centerX = obj.x + (width / 2);
        int bandHalf = Math.max(1, Math.min(2, width / 4));
        int logicalY = obj.y;

        // Walk upward while a MAJORITY of the narrow center band is still water.
        // This rejects little diagonal water slivers near the bridge/bank.
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
            // both sit in water, which removes the hovering-on-bank look.
            for (int y = bottom - 1; y <= bottom; y++) {
                if (y < 0 || y >= 168) continue;
                for (int x = centerX - bandHalf; x <= centerX + bandHalf; x++) {
                    if (x < 0 || x >= 160) continue;
                    score += data.getSceneMaskBit(WATER, x, y) ? 18 : -22;
                }
            }

            score -= Math.abs(sink - preferredSink) * 2;

            if (score > bestScore) {
                bestScore = score;
                bestSink = sink;
            }
        }

        return bestSink;
    }

    /** Extra repaint room for a previously sunk water cel when the view changes. */
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

# Patch only the normal animated-object DRAW path. drawY is a local render-only
# coordinate; this.y is never assigned or altered by this patch.
draw_anchor = '''        // Calculate starting screen offset. AGI pixels are 2x1 within the picture area.
        int aniObjTop = ((this.y - cellHeight) + 1);
        int screenPos = (aniObjTop * 320) + (this.x * 2);
        int screenLineAdd = 320 - (cellWidth << 1);

        // Calculate starting position within the priority screen.
        int priorityPos = (aniObjTop * 160) + this.x;
'''
draw_repl = '''        // Calculate starting screen offset. AGI pixels are 2x1 within the picture area.
        // drawY is VISUAL ONLY. Never modify this.y for water alignment.
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
        // SaveArea follows the render position only so background restoration matches.
        // The AnimatedObject's actual this.y remains the original logical baseline.
        this.saveArea.y = (short)drawY;
        this.saveArea.width = cellWidth;
'''
if text.count(save_anchor) != 1:
    raise RuntimeError('AnimatedObject SaveArea draw anchor not found')
text = text.replace(save_anchor, save_repl)

# show() copies a taller rectangle for ego whenever a custom water mask exists.
# This clears a previously sunk water frame cleanly when KQ1 switches views.
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
print('Water rendering installed: sink is render-only and gated to horizontal swim/drown cels; walking Graham never moves')
