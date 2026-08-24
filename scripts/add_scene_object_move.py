#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scene_object_move.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
text = variable_data.read_text()
anchor = '''    default void clearSceneMaskLayer(int layer) { }
'''
repl = '''    default void clearSceneMaskLayer(int layer) { }

    // Sprite-placement authoring. The worker publishes visible object bounds;
    // the UI writes up to 32 persisted visual offset records.
    default int getSceneMoveObjectCount() { return 0; }
    default void setSceneMoveObjectCount(int value) { }
    default int getSceneMoveObjectField(int record, int field) { return 0; }
    default void setSceneMoveObjectField(int record, int field, int value) { }
    default int getSceneVisualOffsetCount() { return 0; }
    default void setSceneVisualOffsetCount(int value) { }
    default int getSceneVisualOffsetField(int record, int field) { return 0; }
    default void setSceneVisualOffsetField(int record, int field, int value) { }
'''
if text.count(anchor) != 1:
    raise RuntimeError('VariableData scene-mask tail anchor not found')
variable_data.write_text(text.replace(anchor, repl))

gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()
const_anchor = '''    private static final int SCENE_MASK_LAYERS = 4;
'''
const_repl = '''    private static final int SCENE_MASK_LAYERS = 4;

    private static final int SCENE_MOVE_OBJECT_COUNT = 3884;
    private static final int SCENE_MOVE_OBJECTS = 3885;
    private static final int SCENE_MOVE_OBJECT_MAX = 16;
    private static final int SCENE_MOVE_OBJECT_FIELDS = 6;

    private static final int SCENE_VISUAL_OFFSET_COUNT = 3981;
    private static final int SCENE_VISUAL_OFFSETS = 3982;
    private static final int SCENE_VISUAL_OFFSET_MAX = 32;
    private static final int SCENE_VISUAL_OFFSET_FIELDS = 5;
'''
if text.count(const_anchor) != 1:
    raise RuntimeError('GwtVariableData scene mask layer constant not found')
text = text.replace(const_anchor, const_repl)

if text.count('Defines.NUMVARS + Defines.NUMFLAGS + 3372') != 2:
    raise RuntimeError('GwtVariableData scene-mask capacity markers not found')
text = text.replace('Defines.NUMVARS + Defines.NUMFLAGS + 3372',
                    'Defines.NUMVARS + Defines.NUMFLAGS + 3630')

method_anchor = '''    /**
     * Gets the SharedArrayBuffer used internally by the variable array.
'''
methods = '''    @Override
    public int getSceneMoveObjectCount() {
        return variableArray.get(SCENE_MOVE_OBJECT_COUNT);
    }

    @Override
    public void setSceneMoveObjectCount(int value) {
        variableArray.set(SCENE_MOVE_OBJECT_COUNT, Math.max(0, Math.min(SCENE_MOVE_OBJECT_MAX, value)));
    }

    private int sceneMoveObjectIndex(int record, int field) {
        if (record < 0 || record >= SCENE_MOVE_OBJECT_MAX || field < 0 || field >= SCENE_MOVE_OBJECT_FIELDS) return -1;
        return SCENE_MOVE_OBJECTS + (record * SCENE_MOVE_OBJECT_FIELDS) + field;
    }

    @Override
    public int getSceneMoveObjectField(int record, int field) {
        int index = sceneMoveObjectIndex(record, field);
        return index < 0 ? 0 : variableArray.get(index);
    }

    @Override
    public void setSceneMoveObjectField(int record, int field, int value) {
        int index = sceneMoveObjectIndex(record, field);
        if (index >= 0) variableArray.set(index, value);
    }

    @Override
    public int getSceneVisualOffsetCount() {
        return variableArray.get(SCENE_VISUAL_OFFSET_COUNT);
    }

    @Override
    public void setSceneVisualOffsetCount(int value) {
        variableArray.set(SCENE_VISUAL_OFFSET_COUNT, Math.max(0, Math.min(SCENE_VISUAL_OFFSET_MAX, value)));
    }

    private int sceneVisualOffsetIndex(int record, int field) {
        if (record < 0 || record >= SCENE_VISUAL_OFFSET_MAX || field < 0 || field >= SCENE_VISUAL_OFFSET_FIELDS) return -1;
        return SCENE_VISUAL_OFFSETS + (record * SCENE_VISUAL_OFFSET_FIELDS) + field;
    }

    @Override
    public int getSceneVisualOffsetField(int record, int field) {
        int index = sceneVisualOffsetIndex(record, field);
        return index < 0 ? 0 : variableArray.get(index);
    }

    @Override
    public void setSceneVisualOffsetField(int record, int field, int value) {
        int index = sceneVisualOffsetIndex(record, field);
        if (index >= 0) variableArray.set(index, value);
    }

    /**
     * Gets the SharedArrayBuffer used internally by the variable array.
'''
if text.count(method_anchor) != 1:
    raise RuntimeError('GwtVariableData SharedArrayBuffer method anchor not found')
gwt.write_text(text.replace(method_anchor, methods))

runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
runtime_anchor = '''    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
runtime_helpers = '''    private static final int VISUAL_OFFSET_MAX = 32;

    private static int visualOffset(GameState state, AnimatedObject obj, int field) {
        if (state == null || obj == null) return 0;
        VariableData data = state.getVariableData();
        int room = state.getVar(Defines.CURROOM);
        int count = Math.max(0, Math.min(VISUAL_OFFSET_MAX, data.getSceneVisualOffsetCount()));
        for (int i = 0; i < count; i++) {
            if (data.getSceneVisualOffsetField(i, 0) == room
                    && data.getSceneVisualOffsetField(i, 1) == obj.objectNumber
                    && data.getSceneVisualOffsetField(i, 2) == obj.currentView) {
                return data.getSceneVisualOffsetField(i, field);
            }
        }
        return 0;
    }

    public static int objectVisualOffsetX(GameState state, AnimatedObject obj) {
        return visualOffset(state, obj, 3);
    }

    public static int objectVisualOffsetY(GameState state, AnimatedObject obj) {
        return visualOffset(state, obj, 4);
    }

    public static int objectVisualPadding(GameState state, AnimatedObject obj) {
        if (state == null || obj == null) return 0;
        VariableData data = state.getVariableData();
        int room = state.getVar(Defines.CURROOM);
        int count = Math.max(0, Math.min(VISUAL_OFFSET_MAX, data.getSceneVisualOffsetCount()));
        int padding = 0;
        for (int i = 0; i < count; i++) {
            if (data.getSceneVisualOffsetField(i, 0) == room
                    && data.getSceneVisualOffsetField(i, 1) == obj.objectNumber) {
                padding = Math.max(padding, Math.abs(data.getSceneVisualOffsetField(i, 3)));
                padding = Math.max(padding, Math.abs(data.getSceneVisualOffsetField(i, 4)));
            }
        }
        return Math.min(80, padding + 2);
    }

    public static void publishMoveObjects(GameState state) {
        VariableData data = state.getVariableData();
        data.setSceneMoveObjectCount(0);
        if (!editorOwnsRoom(state) || state.animatedObjects == null) return;

        int out = 0;
        for (AnimatedObject obj : state.animatedObjects) {
            if (obj == null || !obj.drawn || out >= 16) continue;
            int width = Math.max(1, obj.xSize());
            int height = Math.max(1, obj.ySize());
            int visualX = obj.x + objectVisualOffsetX(state, obj);
            int visualY = obj.y + objectVisualOffsetY(state, obj) + waterVisualSink(state, obj);

            data.setSceneMoveObjectField(out, 0, obj.objectNumber);
            data.setSceneMoveObjectField(out, 1, obj.currentView);
            data.setSceneMoveObjectField(out, 2, visualX);
            data.setSceneMoveObjectField(out, 3, visualY);
            data.setSceneMoveObjectField(out, 4, width);
            data.setSceneMoveObjectField(out, 5, height);
            out++;
        }
        data.setSceneMoveObjectCount(out);
    }

    public static boolean blocksEgoMovement(GameState state, int leftX, int rightX, int y) {
'''
if text.count(runtime_anchor) != 1:
    raise RuntimeError('SceneMaskRuntime movement anchor not found')
runtime.write_text(text.replace(runtime_anchor, runtime_helpers))

game_state = root / 'core/src/main/java/com/agifans/agile/GameState.java'
text = game_state.read_text()
publish_anchor = '''        SceneMaskRuntime.updateOccluderFlag(this);

        // Draw the AnimatedObjects to screen in priority order.
'''
publish_repl = '''        SceneMaskRuntime.updateOccluderFlag(this);
        SceneMaskRuntime.publishMoveObjects(this);

        // Draw the AnimatedObjects to screen in priority order.
'''
if text.count(publish_anchor) != 1:
    raise RuntimeError('GameState scene-mask publish anchor not found')
game_state.write_text(text.replace(publish_anchor, publish_repl))

animated = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
text = animated.read_text()
draw_anchor = '''        int waterVisualSink = SceneMaskRuntime.waterVisualSink(state, this);
        int drawY = this.y + waterVisualSink;
        int aniObjTop = ((drawY - cellHeight) + 1);
        int screenPos = (aniObjTop * 320) + (this.x * 2);
        int screenLineAdd = 320 - (cellWidth << 1);

        // Calculate starting position within the priority screen.
        int priorityPos = (aniObjTop * 160) + this.x;
'''
draw_repl = '''        int waterVisualSink = SceneMaskRuntime.waterVisualSink(state, this);
        int editorVisualOffsetX = SceneMaskRuntime.objectVisualOffsetX(state, this);
        int editorVisualOffsetY = SceneMaskRuntime.objectVisualOffsetY(state, this);
        int drawX = this.x + editorVisualOffsetX;
        int drawY = this.y + waterVisualSink + editorVisualOffsetY;
        int aniObjTop = ((drawY - cellHeight) + 1);
        int screenPos = (aniObjTop * 320) + (drawX * 2);
        int screenLineAdd = 320 - (cellWidth << 1);

        // Calculate starting position within the priority screen.
        int priorityPos = (aniObjTop * 160) + drawX;
'''
if text.count(draw_anchor) != 1:
    raise RuntimeError('AnimatedObject water render anchor not found')
text = text.replace(draw_anchor, draw_repl)

save_anchor = '''        this.saveArea.x = this.x;
        // SaveArea follows the render position only so background restoration matches.
'''
save_repl = '''        this.saveArea.x = (short)drawX;
        // SaveArea follows the render position only so background restoration matches.
'''
if text.count(save_anchor) != 1:
    raise RuntimeError('AnimatedObject SaveArea X anchor not found')
text = text.replace(save_anchor, save_repl)

draw_pos = text.index('int editorVisualOffsetX = SceneMaskRuntime.objectVisualOffsetX')
bounds = '((this.x + x) >= 0) && ((this.x + x) < 160)'
tail = text[draw_pos:]
if bounds not in tail:
    raise RuntimeError('AnimatedObject normal draw X bounds not found after visual offset patch')
tail = tail.replace(bounds, '((drawX + x) >= 0) && ((drawX + x) < 160)', 1)
text = text[:draw_pos] + tail

show_anchor = '''            int leftmostX = Math.min(prevX, this.x);
            int rightmostX = Math.max(prevX + prevCelWidth, this.x + this.xSize()) - 1;
            int topmostY = Math.min(prevY - prevCelHeight, this.y - this.ySize()) + 1;
            int waterVisualPadding = SceneMaskRuntime.waterVisualPadding(state, this);
            int bottommostY = Math.max(prevY, this.y) + waterVisualPadding;
'''
show_repl = '''            int editorVisualPadding = SceneMaskRuntime.objectVisualPadding(state, this);
            int leftmostX = Math.max(0, Math.min(prevX, this.x) - editorVisualPadding);
            int rightmostX = Math.min(159, Math.max(prevX + prevCelWidth, this.x + this.xSize()) - 1 + editorVisualPadding);
            int topmostY = Math.max(0, Math.min(prevY - prevCelHeight, this.y - this.ySize()) + 1 - editorVisualPadding);
            int waterVisualPadding = SceneMaskRuntime.waterVisualPadding(state, this);
            int bottommostY = Math.min(167, Math.max(prevY, this.y) + waterVisualPadding + editorVisualPadding);
'''
if text.count(show_anchor) != 1:
    raise RuntimeError('AnimatedObject show repaint anchor not found')
animated.write_text(text.replace(show_anchor, show_repl))

editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

field_anchor = '''    private boolean waterActive;
'''
field_repl = '''    private boolean waterActive;
    private boolean moveMode;
    private boolean movingObject;
    private int moveSelectedObject = -1;
    private int moveSelectedView = -1;
    private int moveLastX;
    private int moveLastY;
'''
if text.count(field_anchor) != 1:
    raise RuntimeError('SceneMaskEditor water field anchor not found')
text = text.replace(field_anchor, field_repl)

prefs_anchor = '''        this.prefs = Gdx.app.getPreferences("agi-scene-mask-editor-v3");
'''
prefs_repl = '''        this.prefs = Gdx.app.getPreferences("agi-scene-mask-editor-v3");
        loadVisualOffsets();
'''
if text.count(prefs_anchor) != 1:
    raise RuntimeError('SceneMaskEditor v3 preferences anchor not found')
text = text.replace(prefs_anchor, prefs_repl)

helper_anchor = '''    private void activateWaterMask() {
'''
helpers = '''    private void loadVisualOffsets() {
        data.setSceneVisualOffsetCount(0);
        String saved = prefs.getString("visualOffsets", "");
        if (saved == null || saved.length() == 0) return;
        String[] records = saved.split(";");
        int out = 0;
        for (String record : records) {
            if (out >= 32 || record == null || record.length() == 0) continue;
            String[] p = record.split(",");
            if (p.length != 5) continue;
            try {
                for (int f = 0; f < 5; f++) data.setSceneVisualOffsetField(out, f, Integer.parseInt(p[f]));
                out++;
            } catch (Exception ignored) {
            }
        }
        data.setSceneVisualOffsetCount(out);
    }

    private void saveVisualOffsets() {
        StringBuilder out = new StringBuilder();
        int count = Math.max(0, Math.min(32, data.getSceneVisualOffsetCount()));
        for (int i = 0; i < count; i++) {
            if (i > 0) out.append(';');
            for (int f = 0; f < 5; f++) {
                if (f > 0) out.append(',');
                out.append(data.getSceneVisualOffsetField(i, f));
            }
        }
        prefs.putString("visualOffsets", out.toString());
        prefs.flush();
    }

    private int findVisualOffsetRecord(int targetRoom, int objectNumber, int viewNumber) {
        int count = Math.max(0, Math.min(32, data.getSceneVisualOffsetCount()));
        for (int i = 0; i < count; i++) {
            if (data.getSceneVisualOffsetField(i, 0) == targetRoom
                    && data.getSceneVisualOffsetField(i, 1) == objectNumber
                    && data.getSceneVisualOffsetField(i, 2) == viewNumber) return i;
        }
        return -1;
    }

    private int ensureVisualOffsetRecord(int targetRoom, int objectNumber, int viewNumber) {
        int existing = findVisualOffsetRecord(targetRoom, objectNumber, viewNumber);
        if (existing >= 0) return existing;
        int count = Math.max(0, Math.min(32, data.getSceneVisualOffsetCount()));
        if (count >= 32) {
            notice("MOVE TABLE FULL");
            return -1;
        }
        data.setSceneVisualOffsetField(count, 0, targetRoom);
        data.setSceneVisualOffsetField(count, 1, objectNumber);
        data.setSceneVisualOffsetField(count, 2, viewNumber);
        data.setSceneVisualOffsetField(count, 3, 0);
        data.setSceneVisualOffsetField(count, 4, 0);
        data.setSceneVisualOffsetCount(count + 1);
        return count;
    }

    private int selectedMoveDx() {
        int r = findVisualOffsetRecord(room, moveSelectedObject, moveSelectedView);
        return r < 0 ? 0 : data.getSceneVisualOffsetField(r, 3);
    }

    private int selectedMoveDy() {
        int r = findVisualOffsetRecord(room, moveSelectedObject, moveSelectedView);
        return r < 0 ? 0 : data.getSceneVisualOffsetField(r, 4);
    }

    private void moveSelectedBy(int dx, int dy) {
        if (moveSelectedObject < 0 || moveSelectedView < 0) return;
        int r = ensureVisualOffsetRecord(room, moveSelectedObject, moveSelectedView);
        if (r < 0) return;
        int nx = Math.max(-80, Math.min(80, data.getSceneVisualOffsetField(r, 3) + dx));
        int ny = Math.max(-80, Math.min(80, data.getSceneVisualOffsetField(r, 4) + dy));
        data.setSceneVisualOffsetField(r, 3, nx);
        data.setSceneVisualOffsetField(r, 4, ny);
        saveVisualOffsets();
        notice("OBJ " + moveSelectedObject + " VIEW " + moveSelectedView + " X=" + nx + " Y=" + ny);
    }

    private void resetSelectedMove() {
        int r = findVisualOffsetRecord(room, moveSelectedObject, moveSelectedView);
        if (r < 0) return;
        data.setSceneVisualOffsetField(r, 3, 0);
        data.setSceneVisualOffsetField(r, 4, 0);
        saveVisualOffsets();
        notice("OBJECT OFFSET RESET");
    }

    private boolean selectMoveObjectAt(int px, int py) {
        int count = Math.max(0, Math.min(16, data.getSceneMoveObjectCount()));
        int best = -1;
        int bestBaseline = -9999;
        for (int i = 0; i < count; i++) {
            int x = data.getSceneMoveObjectField(i, 2);
            int baselineY = data.getSceneMoveObjectField(i, 3);
            int width = Math.max(1, data.getSceneMoveObjectField(i, 4));
            int height = Math.max(1, data.getSceneMoveObjectField(i, 5));
            int top = baselineY - height + 1;
            if (px >= x && px < x + width && py >= top && py <= baselineY && baselineY >= bestBaseline) {
                best = i;
                bestBaseline = baselineY;
            }
        }
        if (best < 0) {
            moveSelectedObject = -1;
            moveSelectedView = -1;
            notice("NO SPRITE HERE");
            return false;
        }
        moveSelectedObject = data.getSceneMoveObjectField(best, 0);
        moveSelectedView = data.getSceneMoveObjectField(best, 1);
        notice("MOVE OBJ " + moveSelectedObject + " VIEW " + moveSelectedView);
        return true;
    }

    private void activateWaterMask() {
'''
if text.count(helper_anchor) != 1:
    raise RuntimeError('SceneMaskEditor water helper anchor not found')
text = text.replace(helper_anchor, helpers)

nudge_anchor = '''        int nudge = (Gdx.input.isKeyPressed(Input.Keys.SHIFT_LEFT)
                || Gdx.input.isKeyPressed(Input.Keys.SHIFT_RIGHT)) ? 4 : 1;
'''
nudge_repl = '''        int nudge = (Gdx.input.isKeyPressed(Input.Keys.SHIFT_LEFT)
                || Gdx.input.isKeyPressed(Input.Keys.SHIFT_RIGHT)) ? 4 : 1;
        if (moveMode && moveSelectedObject >= 0) {
            if (keycode == Input.Keys.LEFT) { moveSelectedBy(-nudge, 0); return true; }
            if (keycode == Input.Keys.RIGHT) { moveSelectedBy(nudge, 0); return true; }
            if (keycode == Input.Keys.UP) { moveSelectedBy(0, -nudge); return true; }
            if (keycode == Input.Keys.DOWN) { moveSelectedBy(0, nudge); return true; }
            if (keycode == Input.Keys.BACKSPACE || keycode == Input.Keys.FORWARD_DEL) {
                resetSelectedMove();
                return true;
            }
        }
'''
if text.count(nudge_anchor) != 1:
    raise RuntimeError('SceneMaskEditor nudge anchor not found')
text = text.replace(nudge_anchor, nudge_repl)

mode_anchor = '''        if (keycode == Input.Keys.NUM_1) { mode = OCCLUDER; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_2) { mode = COLLISION; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_3) { mode = BEHIND; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_4) { mode = WATER; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
'''
mode_repl = '''        if (keycode == Input.Keys.NUM_1) { moveMode = false; mode = OCCLUDER; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_2) { moveMode = false; mode = COLLISION; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_3) { moveMode = false; mode = BEHIND; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_4) { moveMode = false; mode = WATER; eraser = false; lineAnchorX = -1; lineAnchorY = -1; }
        else if (keycode == Input.Keys.NUM_5) {
            moveMode = true;
            eraser = false;
            lineAnchorX = -1;
            lineAnchorY = -1;
            notice("MOVE MODE - CLICK A SPRITE");
            return true;
        }
'''
if text.count(mode_anchor) != 1:
    raise RuntimeError('SceneMaskEditor layer key block not found')
text = text.replace(mode_anchor, mode_repl)

touch_anchor = '''        if (p == null) return true;
        rightErase = (button == Input.Buttons.RIGHT);
'''
touch_repl = '''        if (p == null) return true;
        if (moveMode) {
            movingObject = selectMoveObjectAt(p[0], p[1]);
            moveLastX = p[0];
            moveLastY = p[1];
            return true;
        }
        rightErase = (button == Input.Buttons.RIGHT);
'''
if text.count(touch_anchor) != 1:
    raise RuntimeError('SceneMaskEditor touchDown anchor not found')
text = text.replace(touch_anchor, touch_repl)

drag_anchor = '''        int[] p = point(screenX, screenY);
        if (p == null) return true;
        paint(p[0], p[1], rightErase || optionEraseHeld());
'''
drag_repl = '''        int[] p = point(screenX, screenY);
        if (p == null) return true;
        if (moveMode && movingObject && moveSelectedObject >= 0) {
            int dx = p[0] - moveLastX;
            int dy = p[1] - moveLastY;
            if (dx != 0 || dy != 0) moveSelectedBy(dx, dy);
            moveLastX = p[0];
            moveLastY = p[1];
            return true;
        }
        paint(p[0], p[1], rightErase || optionEraseHeld());
'''
if text.count(drag_anchor) != 1:
    raise RuntimeError('SceneMaskEditor touchDragged anchor not found')
text = text.replace(drag_anchor, drag_repl)

up_anchor = '''        rightErase = false;
        draggingBrushSlider = false;
        panning = false;
        saveRoom();
'''
up_repl = '''        rightErase = false;
        draggingBrushSlider = false;
        panning = false;
        movingObject = false;
        saveRoom();
        saveVisualOffsets();
'''
if text.count(up_anchor) != 1:
    raise RuntimeError('SceneMaskEditor touchUp anchor not found')
text = text.replace(up_anchor, up_repl)

render_helper_anchor = '''    private void drawForegroundRuns(SpriteBatch batch, Texture background) {
'''
render_helper = '''    private void drawMoveSelection(SpriteBatch batch) {
        if (!moveMode || moveSelectedObject < 0) return;
        int count = Math.max(0, Math.min(16, data.getSceneMoveObjectCount()));
        for (int i = 0; i < count; i++) {
            if (data.getSceneMoveObjectField(i, 0) != moveSelectedObject
                    || data.getSceneMoveObjectField(i, 1) != moveSelectedView) continue;
            int x = data.getSceneMoveObjectField(i, 2);
            int baselineY = data.getSceneMoveObjectField(i, 3);
            int width = Math.max(1, data.getSceneMoveObjectField(i, 4));
            int height = Math.max(1, data.getSceneMoveObjectField(i, 5));
            float sx = x * (264f / WIDTH);
            float sw = width * (264f / WIDTH);
            float bottom = 24f + (167 - baselineY);
            float sh = height;
            batch.setColor(1f, 0.95f, 0.1f, 0.95f);
            batch.draw(white, sx, bottom, sw, 1f);
            batch.draw(white, sx, bottom + sh - 1f, sw, 1f);
            batch.draw(white, sx, bottom, 1f, sh);
            batch.draw(white, sx + sw - 1f, bottom, 1f, sh);
            batch.setColor(Color.WHITE);
            return;
        }
    }

    private void drawForegroundRuns(SpriteBatch batch, Texture background) {
'''
if text.count(render_helper_anchor) != 1:
    raise RuntimeError('SceneMaskEditor foreground render helper anchor not found')
text = text.replace(render_helper_anchor, render_helper)

rgb_water = '''            if (layerVisible[OCCLUDER]) drawMaskRuns(batch, masks[OCCLUDER], new Color(1f, 0.12f, 0.08f, 0.45f));
            if (layerVisible[COLLISION]) drawMaskRuns(batch, masks[COLLISION], new Color(0.08f, 0.35f, 1f, 0.50f));
            if (layerVisible[BEHIND]) drawMaskRuns(batch, masks[BEHIND], new Color(0.10f, 1f, 0.25f, 0.35f));
            if (layerVisible[WATER]) drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.42f));
'''
rgb_water_repl = '''            if (!moveMode) {
                if (layerVisible[OCCLUDER]) drawMaskRuns(batch, masks[OCCLUDER], new Color(1f, 0.12f, 0.08f, 0.45f));
                if (layerVisible[COLLISION]) drawMaskRuns(batch, masks[COLLISION], new Color(0.08f, 0.35f, 1f, 0.50f));
                if (layerVisible[BEHIND]) drawMaskRuns(batch, masks[BEHIND], new Color(0.10f, 1f, 0.25f, 0.35f));
                if (layerVisible[WATER]) drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.42f));
            }
            drawMoveSelection(batch);
'''
if text.count(rgb_water) != 1:
    raise RuntimeError('SceneMaskEditor mask render block not found')
text = text.replace(rgb_water, rgb_water_repl)

mode_name_anchor = '''            String baseMode = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : mode == BEHIND ? "BEHIND" : "WATER";
            String modeName = eraser ? ("ERASE " + baseMode) : baseMode;
'''
mode_name_repl = '''            String baseMode = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : mode == BEHIND ? "BEHIND" : "WATER";
            String modeName = moveMode ? "MOVE" : (eraser ? ("ERASE " + baseMode) : baseMode);
'''
if text.count(mode_name_anchor) != 1:
    raise RuntimeError('SceneMaskEditor mode label anchor not found')
text = text.replace(mode_name_anchor, mode_name_repl)

hud_anchor = '''            font.draw(batch, "1 front 2 block 3 behind 4 water | Shift-line | Option erase | R/G/B/W hide",
                    6, 184);
'''
hud_repl = '''            font.draw(batch, moveMode
                            ? "MOVE: click+drag sprite | arrows nudge | Shift=4px | Backspace reset | 1-4 paint"
                            : "1 front 2 block 3 behind 4 water 5 MOVE | Shift-line | Option erase | R/G/B/W hide",
                    6, 184);
'''
if text.count(hud_anchor) != 1:
    raise RuntimeError('SceneMaskEditor WATER HUD anchor not found')
text = text.replace(hud_anchor, hud_repl)

hud1_anchor = '''            font.draw(batch, "MASK PAINT room " + room + " mode=" + modeName + " brush=" + brush + " zoom=" + zoom + "x  xy=" + matteOffsetX + "," + matteOffsetY,
                    6, 195);
'''
hud1_repl = '''            String moveStatus = moveMode && moveSelectedObject >= 0
                    ? (" obj=" + moveSelectedObject + " view=" + moveSelectedView
                            + " off=" + selectedMoveDx() + "," + selectedMoveDy())
                    : "";
            font.draw(batch, "MASK EDIT room " + room + " mode=" + modeName + " brush=" + brush + " zoom=" + zoom + "x" + moveStatus,
                    6, 195);
'''
if text.count(hud1_anchor) != 1:
    raise RuntimeError('SceneMaskEditor first HUD line not found')
text = text.replace(hud1_anchor, hud1_repl)

editor.write_text(text)
print('Sprite move editor installed: 5=move, click-drag visible AGI sprites, per room/object/view visual offsets persisted')
