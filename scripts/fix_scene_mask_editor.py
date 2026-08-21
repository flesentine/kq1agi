#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_mask_editor.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# Keep normal AGI blocking controls everywhere except the existing hand-tuned
# Room 1 legacy-tree corridor. The blue editor mask is ADDITIONAL collision; it
# must not make castle walls and room boundaries disappear.
animated = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
text = animated.read_text()
editor_control = '''                // If the live editor owns this room, its blue collision plane is
                // authoritative. Otherwise retain the older Room 1 compatibility fix.
                if ((this.objectNumber == 0)
                        && (priority == 0 || priority == 1)
                        && SceneMaskRuntime.editorOwnsRoom(state)) {
                    priority = 4;
                } else if ((this.objectNumber == 0)
                        && (priority == 0 || priority == 1)
                        && ModernRoomDepth.insideOldTreeControlCorridor(
                                state.gameId,
                                state.getVar(Defines.CURROOM),
                                baselineX,
                                this.y)) {
                    priority = 4;
                }
'''
room1_control = '''                // Preserve Sierra's normal room controls. Only the known legacy
                // Room 1 tree corridor is neutralised; the live blue editor mask is
                // then enforced separately at the proposed movement coordinate.
                if ((this.objectNumber == 0)
                        && (priority == 0 || priority == 1)
                        && ModernRoomDepth.insideOldTreeControlCorridor(
                                state.gameId,
                                state.getVar(Defines.CURROOM),
                                baselineX,
                                this.y)) {
                    priority = 4;
                }
'''
if text.count(editor_control) != 1:
    raise RuntimeError('Scene editor global control override not found')
animated.write_text(text.replace(editor_control, room1_control))

# Make E erase the currently selected layer (front/block/behind) rather than
# always erasing the foreground layer, and use backtick as the editor toggle so
# ordinary typed M characters still reach the AGI parser.
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()
text = text.replace('    private static final int ERASER = 3;\n', '')
text = text.replace('    private int mode = OCCLUDER;\n    private int brush = 2;\n',
                    '    private int mode = OCCLUDER;\n    private int brush = 2;\n    private boolean eraser;\n')
old_paint = '''        if (mode == ERASER) erase = true;
        int layer = (mode == ERASER ? OCCLUDER : mode);
        // Eraser removes the selected last non-eraser layer; E toggles back to
        // occluder by default, while right-click erases the currently selected layer.
        if (mode == ERASER) layer = OCCLUDER;
        int radius = Math.max(1, brush);
'''
new_paint = '''        erase = erase || eraser;
        int layer = mode;
        int radius = Math.max(1, brush);
'''
if text.count(old_paint) != 1:
    raise RuntimeError('SceneMaskEditor old eraser paint block not found')
text = text.replace(old_paint, new_paint)
text = text.replace('''    private int selectedLayer() {
        return mode == ERASER ? OCCLUDER : mode;
    }
''', '''    private int selectedLayer() {
        return mode;
    }
''')
text = text.replace('''        if (keycode == Input.Keys.NUM_1) mode = OCCLUDER;
        else if (keycode == Input.Keys.NUM_2) mode = COLLISION;
        else if (keycode == Input.Keys.NUM_3) mode = BEHIND;
        else if (keycode == Input.Keys.E) mode = (mode == ERASER ? OCCLUDER : ERASER);
''', '''        if (keycode == Input.Keys.NUM_1) { mode = OCCLUDER; eraser = false; }
        else if (keycode == Input.Keys.NUM_2) { mode = COLLISION; eraser = false; }
        else if (keycode == Input.Keys.NUM_3) { mode = BEHIND; eraser = false; }
        else if (keycode == Input.Keys.E) eraser = !eraser;
''')
old_mode = '            String modeName = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : mode == BEHIND ? "BEHIND" : "ERASE";\n'
new_mode = '            String baseMode = mode == OCCLUDER ? "FRONT" : mode == COLLISION ? "BLOCK" : "BEHIND";\n            String modeName = eraser ? ("ERASE " + baseMode) : baseMode;\n'
if text.count(old_mode) != 1:
    raise RuntimeError('SceneMaskEditor HUD mode line not found')
text = text.replace(old_mode, new_mode)

# AGILE has its own com.agifans.agile.Character class in this package, so an
# unqualified Character resolves to that class rather than java.lang.Character.
# Qualify these helpers explicitly so the generated editor compiles.
if text.count('Character.forDigit(value, 16)') != 1:
    raise RuntimeError('SceneMaskEditor Character.forDigit call not found')
if text.count('Character.digit(text.charAt(p++), 16)') != 1:
    raise RuntimeError('SceneMaskEditor Character.digit call not found')
text = text.replace('Character.forDigit(value, 16)', 'java.lang.Character.forDigit(value, 16)')
text = text.replace('Character.digit(text.charAt(p++), 16)', 'java.lang.Character.digit(text.charAt(p++), 16)')

text = text.replace('M toggles paint mode.', '` toggles paint mode.')
text = text.replace('if (keycode == Input.Keys.M) {', 'if (keycode == Input.Keys.GRAVE) {')
text = text.replace('"M test | 1 front | 2 block | 3 behind | E erase | [ ] size | C clear | X copy"',
                    '"` test | 1 front | 2 block | 3 behind | E erase | [ ] size | C clear | X copy"')
editor.write_text(text)

print('Scene mask editor refined: normal room controls preserved; java.lang.Character qualified; backtick toggles editor; eraser targets selected layer')
