#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_object_move_pin.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# MOVE SPRITE is an authoring tool, so the dropped position should stay exactly
# where the author put it. Relative offsets can appear to snap back when KQ1
# rewrites an object's logical x/y during a scripted death sequence. Reinterpret
# the shared placement records as absolute VISUAL target coordinates instead.

editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

# Start a clean preference namespace so old relative offsets are never mistaken
# for absolute target coordinates.
start = text.index('    private void loadVisualOffsets() {')
end = text.index('    private void saveVisualOffsets() {', start)
new_load = '''    private void loadVisualOffsets() {
        data.setSceneVisualOffsetCount(0);
        String saved = prefs.getString("visualPinsV1", "");
        if (saved == null || saved.length() == 0) return;
        String[] records = saved.split(";");
        int out = 0;
        for (String record : records) {
            if (out >= 32 || record == null || record.length() == 0) continue;
            String[] p = record.split(",");
            if (p.length != 5) continue;
            try {
                int targetX = Integer.parseInt(p[3]);
                int targetY = Integer.parseInt(p[4]);
                if (targetX < 0 || targetX >= WIDTH || targetY < 0 || targetY >= HEIGHT) continue;
                for (int f = 0; f < 5; f++) data.setSceneVisualOffsetField(out, f, Integer.parseInt(p[f]));
                out++;
            } catch (Exception ignored) {
            }
        }
        data.setSceneVisualOffsetCount(out);
    }

'''
text = text[:start] + new_load + text[end:]

start = text.index('    private void saveVisualOffsets() {')
end = text.index('    private int findVisualOffsetRecord(', start)
new_save = '''    private void saveVisualOffsets() {
        StringBuilder out = new StringBuilder();
        int count = Math.max(0, Math.min(32, data.getSceneVisualOffsetCount()));
        for (int i = 0; i < count; i++) {
            if (i > 0) out.append(';');
            for (int f = 0; f < 5; f++) {
                if (f > 0) out.append(',');
                out.append(data.getSceneVisualOffsetField(i, f));
            }
        }
        prefs.putString("visualPinsV1", out.toString());
        prefs.flush();
    }

'''
text = text[:start] + new_save + text[end:]

# Helper to read the worker-published visual position/bounds of a selected sprite.
anchor = '    private int ensureVisualOffsetRecord(int targetRoom, int objectNumber, int viewNumber) {'
idx = text.index(anchor)
helper = '''    private int publishedMoveField(int objectNumber, int viewNumber, int field, int fallback) {
        int count = Math.max(0, Math.min(16, data.getSceneMoveObjectCount()));
        for (int i = 0; i < count; i++) {
            if (data.getSceneMoveObjectField(i, 0) == objectNumber
                    && data.getSceneMoveObjectField(i, 1) == viewNumber) {
                return data.getSceneMoveObjectField(i, field);
            }
        }
        return fallback;
    }

'''
text = text[:idx] + helper + text[idx:]

# New records begin at the sprite's CURRENT rendered coordinates. From that point
# onward, fields 3/4 are absolute visual target X / baseline Y, not deltas.
start = text.index('    private int ensureVisualOffsetRecord(')
end = text.index('    private int selectedMoveDx()', start)
new_ensure = '''    private int ensureVisualOffsetRecord(int targetRoom, int objectNumber, int viewNumber) {
        int existing = findVisualOffsetRecord(targetRoom, objectNumber, viewNumber);
        if (existing >= 0) return existing;
        int count = Math.max(0, Math.min(32, data.getSceneVisualOffsetCount()));
        if (count >= 32) {
            notice("MOVE TABLE FULL");
            return -1;
        }
        int currentX = publishedMoveField(objectNumber, viewNumber, 2, 0);
        int currentY = publishedMoveField(objectNumber, viewNumber, 3, HEIGHT - 1);
        data.setSceneVisualOffsetField(count, 0, targetRoom);
        data.setSceneVisualOffsetField(count, 1, objectNumber);
        data.setSceneVisualOffsetField(count, 2, viewNumber);
        data.setSceneVisualOffsetField(count, 3, currentX);
        data.setSceneVisualOffsetField(count, 4, currentY);
        data.setSceneVisualOffsetCount(count + 1);
        return count;
    }

'''
text = text[:start] + new_ensure + text[end:]

# Move the absolute target itself. This means the sprite cannot jump back when
# the AGI logic changes its underlying logical x/y after the mouse is released.
start = text.index('    private void moveSelectedBy(')
end = text.index('    private void resetSelectedMove()', start)
new_move = '''    private void moveSelectedBy(int dx, int dy) {
        if (moveSelectedObject < 0 || moveSelectedView < 0) return;
        int r = ensureVisualOffsetRecord(room, moveSelectedObject, moveSelectedView);
        if (r < 0) return;
        int width = Math.max(1, publishedMoveField(moveSelectedObject, moveSelectedView, 4, 1));
        int height = Math.max(1, publishedMoveField(moveSelectedObject, moveSelectedView, 5, 1));
        int nx = Math.max(0, Math.min(WIDTH - width, data.getSceneVisualOffsetField(r, 3) + dx));
        int ny = Math.max(height - 1, Math.min(HEIGHT - 1, data.getSceneVisualOffsetField(r, 4) + dy));
        data.setSceneVisualOffsetField(r, 3, nx);
        data.setSceneVisualOffsetField(r, 4, ny);
        saveVisualOffsets();
    }

'''
text = text[:start] + new_move + text[end:]

# Reset means "unpin" rather than pinning the sprite to 0,0.
start = text.index('    private void resetSelectedMove() {')
end = text.index('    private boolean select', start)
new_reset = '''    private void resetSelectedMove() {
        int r = findVisualOffsetRecord(room, moveSelectedObject, moveSelectedView);
        if (r < 0) return;
        int count = Math.max(0, Math.min(32, data.getSceneVisualOffsetCount()));
        for (int i = r; i < count - 1; i++) {
            for (int f = 0; f < 5; f++) {
                data.setSceneVisualOffsetField(i, f, data.getSceneVisualOffsetField(i + 1, f));
            }
        }
        if (count > 0) {
            for (int f = 0; f < 5; f++) data.setSceneVisualOffsetField(count - 1, f, 0);
            data.setSceneVisualOffsetCount(count - 1);
        }
        saveVisualOffsets();
        notice("SPRITE UNPINNED");
    }

'''
text = text[:start] + new_reset + text[end:]

editor.write_text(text)

runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
start = text.index('    private static int visualOffset(')
end = text.index('    public static void publishMoveObjects(', start)
new_runtime = '''    private static int visualPin(GameState state, AnimatedObject obj, int field) {
        if (state == null || obj == null) return Integer.MIN_VALUE;
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
        return Integer.MIN_VALUE;
    }

    public static int objectVisualOffsetX(GameState state, AnimatedObject obj) {
        int targetX = visualPin(state, obj, 3);
        return targetX == Integer.MIN_VALUE ? 0 : targetX - obj.x;
    }

    public static int objectVisualOffsetY(GameState state, AnimatedObject obj) {
        int targetY = visualPin(state, obj, 4);
        if (targetY == Integer.MIN_VALUE) return 0;
        int naturalVisualY = obj.y + waterVisualSink(state, obj);
        return targetY - naturalVisualY;
    }

    public static int objectVisualPadding(GameState state, AnimatedObject obj) {
        if (state == null || obj == null) return 0;
        int targetX = visualPin(state, obj, 3);
        int targetY = visualPin(state, obj, 4);
        if (targetX == Integer.MIN_VALUE || targetY == Integer.MIN_VALUE) return 0;
        int naturalY = obj.y + waterVisualSink(state, obj);
        int padding = Math.max(Math.abs(targetX - obj.x), Math.abs(targetY - naturalY));
        return Math.min(160, padding + 2);
    }

'''
text = text[:start] + new_runtime + text[end:]
runtime.write_text(text)

print('MOVE SPRITE now uses absolute visual pins: drop position stays fixed even when AGI logic rewrites logical coordinates')
