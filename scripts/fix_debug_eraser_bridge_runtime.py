#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_debug_eraser_bridge_runtime.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()


def replace_one(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    path.write_text(text.replace(old, new, 1))


# ERASE in the browser workspace used to rely on a synthetic E KeyboardEvent.
# Chrome/GWT can swallow those events even though the browser sidebar toggles,
# leaving SceneMaskEditor in paint mode. Give ERASE its own one-shot shared slot,
# matching the reliable direct bridges already used by VIEW/OUTLINE/OVERLAY.
variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
replace_one(
    variable_data,
    '''    default int getSceneMaskOpacityBridge() { return 0; }\n    default void setSceneMaskOpacityBridge(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
    '''    default int getSceneMaskOpacityBridge() { return 0; }\n    default void setSceneMaskOpacityBridge(int value) { }\n    default int getSceneMaskEraserBridge() { return 0; }\n    default void setSceneMaskEraserBridge(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
    'VariableData eraser bridge API',
)

gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()
old_const = '    private static final int SCENE_MASK_OPACITY_BRIDGE = 5827;\n'
new_const = old_const + '    private static final int SCENE_MASK_ERASER_BRIDGE = 5828;\n'
if text.count(old_const) != 1:
    raise RuntimeError('GwtVariableData eraser bridge constant anchor not found')
text = text.replace(old_const, new_const, 1)

capacity = 'Defines.NUMVARS + Defines.NUMFLAGS + 5316'
if text.count(capacity) != 2:
    raise RuntimeError(f'GwtVariableData eraser capacity markers: expected 2, found {text.count(capacity)}')
text = text.replace(capacity, 'Defines.NUMVARS + Defines.NUMFLAGS + 5317')

old_methods = '''    @Override\n    public void setSceneMaskOpacityBridge(int value) {\n        variableArray.set(SCENE_MASK_OPACITY_BRIDGE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
new_methods = '''    @Override\n    public void setSceneMaskOpacityBridge(int value) {\n        variableArray.set(SCENE_MASK_OPACITY_BRIDGE, value);\n    }\n\n    @Override\n    public int getSceneMaskEraserBridge() {\n        return variableArray.get(SCENE_MASK_ERASER_BRIDGE);\n    }\n\n    @Override\n    public void setSceneMaskEraserBridge(int value) {\n        variableArray.set(SCENE_MASK_ERASER_BRIDGE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
if text.count(old_methods) != 1:
    raise RuntimeError('GwtVariableData eraser bridge method anchor not found')
text = text.replace(old_methods, new_methods, 1)
gwt.write_text(text)

editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()
old_sync_tail = '''        int encodedOpacity = data.getSceneMaskOpacityBridge();\n        if (encodedOpacity >= 25 && encodedOpacity <= 100) {\n            overlayOpacityPercent = encodedOpacity;\n        }\n    }\n\n    private boolean optionEraseHeld() {\n'''
new_sync_tail = '''        int encodedOpacity = data.getSceneMaskOpacityBridge();\n        if (encodedOpacity >= 25 && encodedOpacity <= 100) {\n            overlayOpacityPercent = encodedOpacity;\n        }\n\n        int encodedEraser = data.getSceneMaskEraserBridge();\n        if (encodedEraser == 100 || encodedEraser == 101) {\n            eraser = encodedEraser == 101;\n            // One-shot command: do not pin the Java state forever, so a real\n            // physical E key can still toggle the editor normally afterward.\n            data.setSceneMaskEraserBridge(0);\n        }\n    }\n\n    private boolean optionEraseHeld() {\n'''
if text.count(old_sync_tail) != 1:
    raise RuntimeError('SceneMaskEditor eraser bridge sync anchor not found')
editor.write_text(text.replace(old_sync_tail, new_sync_tail, 1))

print('Debug ERASE direct bridge installed: browser command slot 5828 drives SceneMaskEditor eraser state')
