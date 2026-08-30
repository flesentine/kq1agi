#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_debug_test_bridge_runtime.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()


def replace_one(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    path.write_text(text.replace(old, new, 1))


# Browser DEBUG/TEST used to depend on synthetic F2 KeyboardEvents. Chrome/GWT
# can swallow those events, which lets the browser dock close while the Java
# SceneMaskEditor remains in paint mode and keeps Graham frozen. Give workspace
# entry/exit a direct one-shot SharedArrayBuffer command just like ERASE.
variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
replace_one(
    variable_data,
    '''    default int getSceneMaskEraserBridge() { return 0; }\n    default void setSceneMaskEraserBridge(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
    '''    default int getSceneMaskEraserBridge() { return 0; }\n    default void setSceneMaskEraserBridge(int value) { }\n    default int getSceneMaskWorkspaceBridge() { return 0; }\n    default void setSceneMaskWorkspaceBridge(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
    'VariableData workspace bridge API',
)

gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()
old_const = '    private static final int SCENE_MASK_ERASER_BRIDGE = 5828;\n'
new_const = old_const + '    private static final int SCENE_MASK_WORKSPACE_BRIDGE = 5829;\n'
if text.count(old_const) != 1:
    raise RuntimeError('GwtVariableData workspace bridge constant anchor not found')
text = text.replace(old_const, new_const, 1)

capacity = 'Defines.NUMVARS + Defines.NUMFLAGS + 5317'
if text.count(capacity) != 2:
    raise RuntimeError(f'GwtVariableData workspace capacity markers: expected 2, found {text.count(capacity)}')
text = text.replace(capacity, 'Defines.NUMVARS + Defines.NUMFLAGS + 5318')

old_methods = '''    @Override\n    public void setSceneMaskEraserBridge(int value) {\n        variableArray.set(SCENE_MASK_ERASER_BRIDGE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
new_methods = '''    @Override\n    public void setSceneMaskEraserBridge(int value) {\n        variableArray.set(SCENE_MASK_ERASER_BRIDGE, value);\n    }\n\n    @Override\n    public int getSceneMaskWorkspaceBridge() {\n        return variableArray.get(SCENE_MASK_WORKSPACE_BRIDGE);\n    }\n\n    @Override\n    public void setSceneMaskWorkspaceBridge(int value) {\n        variableArray.set(SCENE_MASK_WORKSPACE_BRIDGE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
if text.count(old_methods) != 1:
    raise RuntimeError('GwtVariableData workspace bridge method anchor not found')
text = text.replace(old_methods, new_methods, 1)
gwt.write_text(text)

editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()
old_tail = '''        int encodedEraser = data.getSceneMaskEraserBridge();\n        if (encodedEraser == 100 || encodedEraser == 101) {\n            eraser = encodedEraser == 101;\n            // One-shot command: do not pin the Java state forever, so a real\n            // physical E key can still toggle the editor normally afterward.\n            data.setSceneMaskEraserBridge(0);\n        }\n    }\n\n    private boolean optionEraseHeld() {\n'''
new_tail = '''        int encodedEraser = data.getSceneMaskEraserBridge();\n        if (encodedEraser == 100 || encodedEraser == 101) {\n            eraser = encodedEraser == 101;\n            // One-shot command: do not pin the Java state forever, so a real\n            // physical E key can still toggle the editor normally afterward.\n            data.setSceneMaskEraserBridge(0);\n        }\n\n        int encodedWorkspace = data.getSceneMaskWorkspaceBridge();\n        if (encodedWorkspace == 100 || encodedWorkspace == 101) {\n            boolean requestedPaintMode = encodedWorkspace == 101;\n            if (requestedPaintMode != paintMode) {\n                if (requestedPaintMode) {\n                    ensureRoom();\n                    paintMode = true;\n                    data.setSceneMaskRoom(room);\n                    data.setSceneMaskEnabled(true);\n                    prefs.putBoolean(key(\"active\"), true);\n                    data.setSceneMaskPaintMode(true);\n                    notice(\"PAINT MODE ON\");\n                } else {\n                    // Save while paintMode is still true so even an otherwise\n                    // clean room persists the current active/editor metadata.\n                    saveRoom();\n                    paintMode = false;\n                    data.setSceneMaskPaintMode(false);\n                    rightErase = false;\n                    inspectMode = false;\n                    moveMode = false;\n                    eraser = false;\n                    notice(\"TEST MODE - MASKS LIVE\");\n                }\n            }\n            // One-shot command. Physical F2 remains usable afterward.\n            data.setSceneMaskWorkspaceBridge(0);\n        }\n    }\n\n    private boolean optionEraseHeld() {\n'''
if text.count(old_tail) != 1:
    raise RuntimeError('SceneMaskEditor workspace bridge sync anchor not found')
editor.write_text(text.replace(old_tail, new_tail, 1))

print('DEBUG/TEST direct bridge installed: browser slot 5829 reliably enters and exits SceneMaskEditor paint mode')
