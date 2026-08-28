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


# The browser and SceneMaskEditor share one Int32 SharedArrayBuffer. Keep the
# whole DISPLAY row authoritative through dedicated slots instead of relying on
# synthetic KeyboardEvents that browsers/GWT can swallow.
variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
replace_one(
    variable_data,
    '''    default int getSceneScriptDangerSeedState() { return 0; }\n    default void setSceneScriptDangerSeedState(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
    '''    default int getSceneScriptDangerSeedState() { return 0; }\n    default void setSceneScriptDangerSeedState(int value) { }\n    default int getSceneMaskViewBridge() { return 0; }\n    default void setSceneMaskViewBridge(int value) { }\n    default int getSceneMaskOutlineBridge() { return 0; }\n    default void setSceneMaskOutlineBridge(int value) { }\n    default int getSceneMaskOpacityBridge() { return 0; }\n    default void setSceneMaskOpacityBridge(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
    'VariableData debug display bridge API',
)

gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()
old_const = '    private static final int SCENE_SCRIPT_DANGER_SEED_STATE = 5824;\n'
new_const = old_const + (
    '    private static final int SCENE_MASK_VIEW_BRIDGE = 5825;\n'
    '    private static final int SCENE_MASK_OUTLINE_BRIDGE = 5826;\n'
    '    private static final int SCENE_MASK_OPACITY_BRIDGE = 5827;\n'
)
if text.count(old_const) != 1:
    raise RuntimeError('GwtVariableData debug display bridge constant anchor not found')
text = text.replace(old_const, new_const, 1)

capacity = 'Defines.NUMVARS + Defines.NUMFLAGS + 5313'
if text.count(capacity) != 2:
    raise RuntimeError(f'GwtVariableData capacity markers: expected 2, found {text.count(capacity)}')
text = text.replace(capacity, 'Defines.NUMVARS + Defines.NUMFLAGS + 5316')

old_methods = '''    @Override\n    public void setSceneScriptDangerSeedState(int value) {\n        variableArray.set(SCENE_SCRIPT_DANGER_SEED_STATE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
new_methods = '''    @Override\n    public void setSceneScriptDangerSeedState(int value) {\n        variableArray.set(SCENE_SCRIPT_DANGER_SEED_STATE, value);\n    }\n\n    @Override\n    public int getSceneMaskViewBridge() {\n        return variableArray.get(SCENE_MASK_VIEW_BRIDGE);\n    }\n\n    @Override\n    public void setSceneMaskViewBridge(int value) {\n        variableArray.set(SCENE_MASK_VIEW_BRIDGE, value);\n    }\n\n    @Override\n    public int getSceneMaskOutlineBridge() {\n        return variableArray.get(SCENE_MASK_OUTLINE_BRIDGE);\n    }\n\n    @Override\n    public void setSceneMaskOutlineBridge(int value) {\n        variableArray.set(SCENE_MASK_OUTLINE_BRIDGE, value);\n    }\n\n    @Override\n    public int getSceneMaskOpacityBridge() {\n        return variableArray.get(SCENE_MASK_OPACITY_BRIDGE);\n    }\n\n    @Override\n    public void setSceneMaskOpacityBridge(int value) {\n        variableArray.set(SCENE_MASK_OPACITY_BRIDGE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
if text.count(old_methods) != 1:
    raise RuntimeError('GwtVariableData debug display bridge method anchor not found')
text = text.replace(old_methods, new_methods, 1)
gwt.write_text(text)

editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()
helper_anchor = '''    private boolean optionEraseHeld() {\n'''
helper = '''    private void syncDebugDisplayBridge() {\n        int encodedVisibility = data.getSceneMaskViewBridge();\n        if (encodedVisibility >= 100 && encodedVisibility <= 131) {\n            // 100 + five visibility bits. Apply every frame so SOLO / ALL / NONE\n            // remain absolute even after unrelated editor input.\n            int bits = encodedVisibility - 100;\n            int editableLayers = Math.min(5, layerVisible.length);\n            for (int layer = 0; layer < editableLayers; layer++) {\n                layerVisible[layer] = (bits & (1 << layer)) != 0;\n            }\n        }\n\n        int encodedOutline = data.getSceneMaskOutlineBridge();\n        if (encodedOutline == 100 || encodedOutline == 101) {\n            outlineMode = encodedOutline == 101;\n        }\n\n        int encodedOpacity = data.getSceneMaskOpacityBridge();\n        if (encodedOpacity >= 25 && encodedOpacity <= 100) {\n            overlayOpacityPercent = encodedOpacity;\n        }\n    }\n\n    private boolean optionEraseHeld() {\n'''
if text.count(helper_anchor) != 1:
    raise RuntimeError('SceneMaskEditor debug display bridge helper anchor not found')
text = text.replace(helper_anchor, helper, 1)

render_anchor = '''    public void render(SpriteBatch batch) {\n'''
render_repl = '''    public void render(SpriteBatch batch) {\n        syncDebugDisplayBridge();\n'''
if text.count(render_anchor) != 1:
    raise RuntimeError('SceneMaskEditor render bridge anchor not found')
text = text.replace(render_anchor, render_repl, 1)
editor.write_text(text)

print('Debug display direct bridge installed: visibility 5825, outline 5826, opacity 5827')
