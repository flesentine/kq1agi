#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_object_move_bounds.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# 1) Keep MOVE-SPRITE authoring offsets in a sane range and ignore old accidental
# giant offsets. This specifically self-heals previously saved values such as
# +53,+80 that can move a 160x168 AGI sprite completely off screen.
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

old = '''                for (int f = 0; f < 5; f++) data.setSceneVisualOffsetField(out, f, Integer.parseInt(p[f]));
                out++;
'''
new = '''                for (int f = 0; f < 5; f++) data.setSceneVisualOffsetField(out, f, Integer.parseInt(p[f]));
                int savedDx = data.getSceneVisualOffsetField(out, 3);
                int savedDy = data.getSceneVisualOffsetField(out, 4);
                if (Math.abs(savedDx) > 40 || Math.abs(savedDy) > 40) {
                    // Legacy/debug accident: do not reactivate an off-screen sprite offset.
                    data.setSceneVisualOffsetField(out, 3, 0);
                    data.setSceneVisualOffsetField(out, 4, 0);
                }
                out++;
'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor visual-offset load anchor not found')
text = text.replace(old, new, 1)

old = '''        int nx = Math.max(-80, Math.min(80, data.getSceneVisualOffsetField(r, 3) + dx));
        int ny = Math.max(-80, Math.min(80, data.getSceneVisualOffsetField(r, 4) + dy));
'''
new = '''        int nx = Math.max(-40, Math.min(40, data.getSceneVisualOffsetField(r, 3) + dx));
        int ny = Math.max(-40, Math.min(40, data.getSceneVisualOffsetField(r, 4) + dy));
'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor move offset clamp anchor not found')
text = text.replace(old, new, 1)
editor.write_text(text)

# 2) Final render safety: even a valid saved offset may combine with a changing
# cel/water sink. Clamp the VISUAL draw location only; logical AGI x/y remain
# untouched, so game scripts/collision are unaffected.
animated = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
text = animated.read_text()
old = '''        int drawX = this.x + editorVisualOffsetX;
        int drawY = this.y + waterVisualSink + editorVisualOffsetY;
'''
new = '''        int drawX = Math.max(0, Math.min(160 - cellWidth, this.x + editorVisualOffsetX));
        int drawY = Math.max(cellHeight - 1, Math.min(167, this.y + waterVisualSink + editorVisualOffsetY));
'''
if text.count(old) != 1:
    raise RuntimeError('AnimatedObject visual draw position anchor not found')
animated.write_text(text.replace(old, new, 1))

# 3) Publish the same on-screen coordinates to MOVE mode/debug metadata so its
# yellow/cyan grab box and copied diagnostics match what is actually rendered.
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()
old = '''            int visualX = obj.x + objectVisualOffsetX(state, obj);
            int visualY = obj.y + objectVisualOffsetY(state, obj) + waterVisualSink(state, obj);
'''
new = '''            int visualX = Math.max(0, Math.min(160 - width, obj.x + objectVisualOffsetX(state, obj)));
            int visualY = Math.max(height - 1, Math.min(167,
                    obj.y + objectVisualOffsetY(state, obj) + waterVisualSink(state, obj)));
'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskRuntime published visual position anchor not found')
runtime.write_text(text.replace(old, new, 1))

print('Sprite move bounds fixed: stale >40px offsets self-heal and render/debug positions stay on-screen')
