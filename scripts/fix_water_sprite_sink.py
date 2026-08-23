#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_water_sprite_sink.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
anchor = '''    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
helper = '''    /**
     * Visual-only sink used for the ego while the game already considers him on water.
     * This keeps the swim/drown cel visually in the painted water without changing the
     * logical baseline used by AGI movement, collision, room edges, or scripts.
     */
    public static int waterVisualSink(GameState state, AnimatedObject obj) {
        if (obj == null || obj.objectNumber != 0 || !editorOwnsRoom(state)) return 0;
        VariableData data = state.getVariableData();
        if (!data.getSceneMaskWaterActive() || !state.getFlag(Defines.ONWATER)) return 0;
        return 5;
    }

    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
if text.count(anchor) != 1:
    raise RuntimeError('SceneMaskRuntime blocksEgoMovement anchor not found')
runtime.write_text(text.replace(anchor, helper))

game_state = root / 'core/src/main/java/com/agifans/agile/GameState.java'
text = game_state.read_text()

draw_old = '''    public void drawObjects(List<AnimatedObject> objectDrawList) {
        SceneMaskRuntime.updateOccluderFlag(this);

        // Draw the AnimatedObjects to screen in priority order.
        for (AnimatedObject aniObj : objectDrawList) {
            aniObj.draw();
        }
    }
'''
draw_new = '''    public void drawObjects(List<AnimatedObject> objectDrawList) {
        SceneMaskRuntime.updateOccluderFlag(this);

        // Draw in logical priority order, but visually sink ego a few pixels once
        // AGI says he is on the custom WATER layer. His actual game Y never changes.
        for (AnimatedObject aniObj : objectDrawList) {
            int waterSink = SceneMaskRuntime.waterVisualSink(this, aniObj);
            if (waterSink != 0) aniObj.y += waterSink;
            try {
                aniObj.draw();
            } finally {
                if (waterSink != 0) aniObj.y -= waterSink;
            }
        }
    }
'''
if text.count(draw_old) != 1:
    raise RuntimeError('GameState drawObjects(List) block not found')
text = text.replace(draw_old, draw_new)

show_old = '''        for (AnimatedObject aniObj : objectShowList)
        {
            aniObj.show(pixelData);

            // Check if the AnimatedObject moved this cycle and if it did then set the flags accordingly. The
'''
show_new = '''        for (AnimatedObject aniObj : objectShowList)
        {
            int waterSink = SceneMaskRuntime.waterVisualSink(this, aniObj);
            if (waterSink != 0) aniObj.y += waterSink;
            try {
                aniObj.show(pixelData);
            } finally {
                if (waterSink != 0) aniObj.y -= waterSink;
            }

            // Check if the AnimatedObject moved this cycle and if it did then set the flags accordingly. The
'''
if text.count(show_old) != 1:
    raise RuntimeError('GameState showObjects loop anchor not found')
text = text.replace(show_old, show_new)

game_state.write_text(text)
print('Water animation visual sink installed: ego draws 5 AGI pixels lower while ONWATER; logic position unchanged')
