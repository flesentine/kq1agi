#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_water_sprite_sink.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# Keep the logical AGI baseline untouched. Only the pixels used to render ego are
# moved downward while ONWATER, so collision, room edges, scripts and the custom
# cyan WATER trigger continue to use Graham's real coordinates.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
anchor = '''    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
helper = '''    private static final int WATER_VISUAL_SINK = 10;

    /** Visual-only downward offset for ego while custom WATER says he is swimming. */
    public static int waterVisualSink(GameState state, AnimatedObject obj) {
        if (obj == null || obj.objectNumber != 0 || !editorOwnsRoom(state)) return 0;
        VariableData data = state.getVariableData();
        if (!data.getSceneMaskWaterActive() || !state.getFlag(Defines.ONWATER)) return 0;
        return WATER_VISUAL_SINK;
    }

    /** Extra repaint room so a previously sunk cel is completely cleared on exit. */
    public static int waterVisualPadding(GameState state, AnimatedObject obj) {
        if (obj == null || obj.objectNumber != 0 || !editorOwnsRoom(state)) return 0;
        return state.getVariableData().getSceneMaskWaterActive() ? WATER_VISUAL_SINK : 0;
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

# show() copies a slightly taller rectangle for ego whenever a custom water mask
# exists. This safely covers both the current sunk cel and the restored area from
# the previous sunk frame when Graham has just stepped back onto land.
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
print('Water animation visual sink installed: ego renders 10 AGI pixels lower while ONWATER; logical position unchanged')
