#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_mask_ui_sync.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

# The browser already owns the PAINT/TEST control and brush overlay. The old
# in-canvas PAINT button could toggle Java paint mode without the browser seeing
# that toggle, leaving the brush-size panel visible during test play. Remove that
# second entry point so Java and the browser UI cannot drift apart.
touch_old = '''    @Override
    public boolean touchDown(int screenX, int screenY, int pointer, int button) {
        int[] p = point(screenX, screenY);
        if (!paintMode) {
            // Always-visible top-right PAINT button. It deliberately lives inside
            // the 160x168 picture plane so hit testing stays correct on resized views.
            if (p != null && p[0] >= 132 && p[0] <= 159 && p[1] >= 0 && p[1] <= 13) {
                togglePaintMode();
                return true;
            }
            return false;
        }
'''
touch_new = '''    @Override
    public boolean touchDown(int screenX, int screenY, int pointer, int button) {
        int[] p = point(screenX, screenY);
        if (!paintMode) return false;
'''
if text.count(touch_old) != 1:
    raise RuntimeError('SceneMaskEditor in-canvas PAINT touch target not found')
text = text.replace(touch_old, touch_new)

render_old = '''        } else {
            // Visible mouse entry point so the Sierra parser never has to be used
            // to enter the editor. Hit area maps to mask x=132..159, y=0..13.
            batch.setColor(0f, 0f, 0f, 0.78f);
            batch.draw(white, 218, 178, 44, 13);
            batch.setColor(Color.WHITE);
            font.draw(batch, "PAINT", 224, 188);
        }
'''
render_new = '''        }

        // Browser PAINT/TEST control is authoritative. Keeping a second in-canvas
        // toggle here can desynchronise the fixed browser brush-size overlay.
'''
if text.count(render_old) != 1:
    raise RuntimeError('SceneMaskEditor in-canvas PAINT render block not found')
text = text.replace(render_old, render_new)

editor.write_text(text)

# ---------------------------------------------------------------------------
# Visual water sink. The painted WATER mask correctly moves the logical trigger,
# but AGI cels are baseline-anchored, so swim/drown art can look like it is lying
# on the bank when the replacement art has a lower shoreline. Sink only the
# rendered ego by 5 AGI pixels while the game itself says ONWATER. Logical Y,
# collision, room transitions, scripts, and the custom water trigger stay intact.
# ---------------------------------------------------------------------------
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
anchor = '''    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
helper = '''    public static int waterVisualSink(GameState state, AnimatedObject obj) {
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

        // Preserve logical draw order, but sink ego visually into custom water.
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
print('Scene mask UI sync fixed and water animation visually sunk 5 AGI pixels while ONWATER')
