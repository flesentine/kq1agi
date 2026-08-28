#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_debug_view_bridge_runtime.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()


def replace_one(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    path.write_text(text.replace(old, new, 1))


# The browser and SceneMaskEditor already share one Int32 SharedArrayBuffer. Give
# the VIEW controls one dedicated slot so SOLO / ALL / NONE do not depend on
# synthetic KeyboardEvents reaching libGDX.
variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
replace_one(
    variable_data,
    '''    default int getSceneScriptDangerSeedState() { return 0; }\n    default void setSceneScriptDangerSeedState(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
    '''    default int getSceneScriptDangerSeedState() { return 0; }\n    default void setSceneScriptDangerSeedState(int value) { }\n    default int getSceneMaskViewBridge() { return 0; }\n    default void setSceneMaskViewBridge(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
    'VariableData view bridge API',
)

gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()
old_const = '    private static final int SCENE_SCRIPT_DANGER_SEED_STATE = 5824;\n'
new_const = old_const + '    private static final int SCENE_MASK_VIEW_BRIDGE = 5825;\n'
if text.count(old_const) != 1:
    raise RuntimeError('GwtVariableData view bridge constant anchor not found')
text = text.replace(old_const, new_const, 1)

capacity = 'Defines.NUMVARS + Defines.NUMFLAGS + 5313'
if text.count(capacity) != 2:
    raise RuntimeError(f'GwtVariableData capacity markers: expected 2, found {text.count(capacity)}')
text = text.replace(capacity, 'Defines.NUMVARS + Defines.NUMFLAGS + 5314')

old_methods = '''    @Override\n    public void setSceneScriptDangerSeedState(int value) {\n        variableArray.set(SCENE_SCRIPT_DANGER_SEED_STATE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
new_methods = '''    @Override\n    public void setSceneScriptDangerSeedState(int value) {\n        variableArray.set(SCENE_SCRIPT_DANGER_SEED_STATE, value);\n    }\n\n    @Override\n    public int getSceneMaskViewBridge() {\n        return variableArray.get(SCENE_MASK_VIEW_BRIDGE);\n    }\n\n    @Override\n    public void setSceneMaskViewBridge(int value) {\n        variableArray.set(SCENE_MASK_VIEW_BRIDGE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
if text.count(old_methods) != 1:
    raise RuntimeError('GwtVariableData view bridge method anchor not found')
text = text.replace(old_methods, new_methods, 1)
gwt.write_text(text)

editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()
helper_anchor = '''    private boolean optionEraseHeld() {\n'''
helper = '''    private void syncOverlayVisibilityBridge() {\n        int encoded = data.getSceneMaskViewBridge();\n        if (encoded < 100 || encoded > 131) return;\n\n        // 100 + five visibility bits. This is intentionally applied every frame,\n        // so a SOLO selection remains absolute even after other editor shortcuts.\n        int bits = encoded - 100;\n        int editableLayers = Math.min(5, layerVisible.length);\n        for (int layer = 0; layer < editableLayers; layer++) {\n            layerVisible[layer] = (bits & (1 << layer)) != 0;\n        }\n    }\n\n    private boolean optionEraseHeld() {\n'''
if text.count(helper_anchor) != 1:
    raise RuntimeError('SceneMaskEditor view bridge helper anchor not found')
text = text.replace(helper_anchor, helper, 1)

render_anchor = '''    public void render(SpriteBatch batch) {\n'''
render_repl = '''    public void render(SpriteBatch batch) {\n        syncOverlayVisibilityBridge();\n'''
if text.count(render_anchor) != 1:
    raise RuntimeError('SceneMaskEditor render bridge anchor not found')
text = text.replace(render_anchor, render_repl, 1)
editor.write_text(text)

print('Debug view direct bridge installed: shared slot 5825 drives absolute overlay visibility every frame')
