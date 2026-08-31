#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_danger_composite_runtime.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()


def one(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    path.write_text(text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# 1) Recover scripted death/fall zones that the original detector discarded.
# ---------------------------------------------------------------------------
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()

# A Sierra death handler often ends with new.room(99). The old detector rejected
# every IF containing a room change, even if that same IF explicitly printed a
# fall/death message. That is why the castle bridge could kill Graham while the
# scripted FALL counter still said 0 px.
old = '        return !roomChange && (text || (programControl && motion));\n'
new = '        return text || (!roomChange && programControl && motion);\n'
if text.count(old) != 1:
    raise RuntimeError(f'dangerIf room-change rule: expected 1 match, found {text.count(old)}')
text = text.replace(old, new, 1)

old = '''        return s.contains("fall") || s.contains("fell") || s.contains("drown")
                || s.contains("dead") || s.contains("died") || s.contains("death")
                || s.contains("killed") || s.contains("plunge") || s.contains("splash")
                || s.contains("bridge");
'''
new = '''        return s.contains("fall") || s.contains("fell") || s.contains("drown")
                || s.contains("dead") || s.contains("died") || s.contains("death")
                || s.contains("killed") || s.contains("plunge") || s.contains("splash")
                || s.contains("bridge") || s.contains("moat") || s.contains("alligator")
                || s.contains("current") || s.contains("slip down") || s.contains("false move");
'''
if text.count(old) != 1:
    raise RuntimeError('dangerText vocabulary anchor not found')
text = text.replace(old, new, 1)
runtime.write_text(text)


# ---------------------------------------------------------------------------
# 2) Direct browser -> SceneMaskEditor DANGER command.
#    7/8/9 are already SOLO/ALL/NONE, so do not steal a keyboard shortcut and
#    do not rely on synthetic key events. Slot 5830 follows the workspace bridge.
# ---------------------------------------------------------------------------
variable_data = root / 'core/src/main/java/com/agifans/agile/VariableData.java'
one(
    variable_data,
    '''    default int getSceneMaskWorkspaceBridge() { return 0; }\n    default void setSceneMaskWorkspaceBridge(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
    '''    default int getSceneMaskWorkspaceBridge() { return 0; }\n    default void setSceneMaskWorkspaceBridge(int value) { }\n    default int getSceneMaskDangerViewBridge() { return 0; }\n    default void setSceneMaskDangerViewBridge(int value) { }\n    default boolean getSceneMaskBit(int layer, int x, int y) { return false; }\n''',
    'VariableData DANGER bridge API',
)

gwt = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
text = gwt.read_text()
old = '    private static final int SCENE_MASK_WORKSPACE_BRIDGE = 5829;\n'
new = old + '    private static final int SCENE_MASK_DANGER_VIEW_BRIDGE = 5830;\n'
if text.count(old) != 1:
    raise RuntimeError('GwtVariableData DANGER constant anchor not found')
text = text.replace(old, new, 1)
capacity = 'Defines.NUMVARS + Defines.NUMFLAGS + 5318'
if text.count(capacity) != 2:
    raise RuntimeError(f'GwtVariableData DANGER capacity markers: expected 2, found {text.count(capacity)}')
text = text.replace(capacity, 'Defines.NUMVARS + Defines.NUMFLAGS + 5319')
old = '''    @Override\n    public void setSceneMaskWorkspaceBridge(int value) {\n        variableArray.set(SCENE_MASK_WORKSPACE_BRIDGE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
new = '''    @Override\n    public void setSceneMaskWorkspaceBridge(int value) {\n        variableArray.set(SCENE_MASK_WORKSPACE_BRIDGE, value);\n    }\n\n    @Override\n    public int getSceneMaskDangerViewBridge() {\n        return variableArray.get(SCENE_MASK_DANGER_VIEW_BRIDGE);\n    }\n\n    @Override\n    public void setSceneMaskDangerViewBridge(int value) {\n        variableArray.set(SCENE_MASK_DANGER_VIEW_BRIDGE, value);\n    }\n\n    private int sceneMaskIndex(int layer, int x, int y) {\n'''
if text.count(old) != 1:
    raise RuntimeError('GwtVariableData DANGER methods anchor not found')
text = text.replace(old, new, 1)
gwt.write_text(text)


# ---------------------------------------------------------------------------
# 3) Editor state + detector-version migration.
# ---------------------------------------------------------------------------
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()
old = '    private boolean outlineMode;\n'
new = '    private boolean outlineMode;\n    private boolean dangerView;\n'
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor DANGER field anchor not found')
text = text.replace(old, new, 1)

# Existing browsers have a valid-length, but detector-v1, empty SCRIPT_FALL mask
# cached for Room 1. Version it so the improved scan runs once instead of keeping
# that stale "Scripted: 0 px" forever. Future user erases remain persistent.
old = '''        boolean scriptSaved = savedScriptFall.length() == HEIGHT * 40;
        waitingForScriptDangerSeed = !scriptSaved;
        data.setSceneScriptDangerSeedState(scriptSaved ? room + 1 : -(room + 1));
'''
new = '''        int scriptDetectorVersion = prefs.getInteger(key("scriptFallDetectorVersion"), 0);
        boolean scriptSaved = savedScriptFall.length() == HEIGHT * 40 && scriptDetectorVersion >= 2;
        if (!scriptSaved) {
            for (int y = 0; y < HEIGHT; y++) for (int x = 0; x < WIDTH; x++)
                masks[SCRIPT_FALL][y][x] = false;
        }
        waitingForScriptDangerSeed = !scriptSaved;
        data.setSceneScriptDangerSeedState(scriptSaved ? room + 1 : -(room + 1));
'''
if text.count(old) != 1:
    raise RuntimeError('SCRIPT_FALL detector-version load anchor not found')
text = text.replace(old, new, 1)

old = '''        waitingForScriptDangerSeed = false;
        dirty = true;
        saveRoom();
        notice("SCRIPTED FALL ZONES IMPORTED");
'''
new = '''        waitingForScriptDangerSeed = false;
        prefs.putInteger(key("scriptFallDetectorVersion"), 2);
        dirty = true;
        saveRoom();
        notice("SCRIPTED DANGER ZONES IMPORTED");
'''
if text.count(old) != 1:
    raise RuntimeError('SCRIPT_FALL detector-version save anchor not found')
text = text.replace(old, new, 1)

# Browser DANGER is absolute state. Turning it on makes the editor inspect-only;
# turning it off returns to normal paint interaction. Normal layer selection also
# clears this state so keyboard and mouse workflows cannot get stuck read-only.
helper_anchor = '''    private void syncDebugDisplayBridge() {
'''
helper = '''    private void setDangerView(boolean enabled) {
        if (dangerView == enabled) return;
        dangerView = enabled;
        if (enabled) {
            inspectMode = true;
            moveMode = false;
            eraser = false;
            movingObject = false;
            rightErase = false;
            notice("DANGER VIEW - READ ONLY");
        } else {
            inspectMode = false;
            notice("DANGER VIEW OFF");
        }
    }

    private void syncDebugDisplayBridge() {
'''
if text.count(helper_anchor) != 1:
    raise RuntimeError('SceneMaskEditor display bridge helper anchor not found')
text = text.replace(helper_anchor, helper, 1)

old = '''        int encodedOpacity = data.getSceneMaskOpacityBridge();
        if (encodedOpacity >= 25 && encodedOpacity <= 100) {
            overlayOpacityPercent = encodedOpacity;
        }
    }
'''
new = '''        int encodedOpacity = data.getSceneMaskOpacityBridge();
        if (encodedOpacity >= 25 && encodedOpacity <= 100) {
            overlayOpacityPercent = encodedOpacity;
        }

        int encodedDanger = data.getSceneMaskDangerViewBridge();
        if (encodedDanger == 100 || encodedDanger == 101) {
            setDangerView(encodedDanger == 101);
            data.setSceneMaskDangerViewBridge(0);
        }
    }
'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor DANGER bridge consume anchor not found')
text = text.replace(old, new, 1)

for mode in ('OCCLUDER', 'COLLISION', 'BEHIND', 'WATER', 'FALL'):
    old = f'inspectMode = false; moveMode = false; mode = {mode};'
    new = f'dangerView = false; inspectMode = false; moveMode = false; mode = {mode};'
    if text.count(old) != 1:
        raise RuntimeError(f'SceneMaskEditor {mode} DANGER-exit anchor: found {text.count(old)}')
    text = text.replace(old, new, 1)

old = '''        if (keycode == Input.Keys.I) {
            inspectMode = !inspectMode;
'''
new = '''        if (keycode == Input.Keys.I) {
            dangerView = false;
            inspectMode = !inspectMode;
'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor INSPECT DANGER-exit anchor not found')
text = text.replace(old, new, 1)

old = '''        else if (keycode == Input.Keys.NUM_6) {
            inspectMode = false;
            moveMode = true;
'''
new = '''        else if (keycode == Input.Keys.NUM_6) {
            dangerView = false;
            inspectMode = false;
            moveMode = true;
'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor SPRITES DANGER-exit anchor not found')
text = text.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 4) Read-only DANGER renderer.
#    Cyan = current WATER control, striped yellow = editable FALL/HITSPEC,
#    black/white dotted+exact marks = recovered Sierra scripted fall/death zones.
#    The important bridge fix is the recovered scripted trigger, so DANGER no
#    longer depends on WATER extending visually onto the bridge surface.
# ---------------------------------------------------------------------------
for old, new, label in [
    ('            if (layerVisible[OCCLUDER]) drawMaskRuns(batch, masks[OCCLUDER], new Color(1f, 0.12f, 0.08f, 0.45f));\n',
     '            if (!dangerView && layerVisible[OCCLUDER]) drawMaskRuns(batch, masks[OCCLUDER], new Color(1f, 0.12f, 0.08f, 0.45f));\n', 'FRONT draw'),
    ('            if (layerVisible[COLLISION]) drawMaskRuns(batch, masks[COLLISION], new Color(0.08f, 0.35f, 1f, 0.50f));\n',
     '            if (!dangerView && layerVisible[COLLISION]) drawMaskRuns(batch, masks[COLLISION], new Color(0.08f, 0.35f, 1f, 0.50f));\n', 'BLOCK draw'),
    ('            if (layerVisible[BEHIND]) drawMaskRuns(batch, masks[BEHIND], new Color(0.10f, 1f, 0.25f, 0.35f));\n',
     '            if (!dangerView && layerVisible[BEHIND]) drawMaskRuns(batch, masks[BEHIND], new Color(0.10f, 1f, 0.25f, 0.35f));\n', 'BEHIND draw'),
    ('            if (layerVisible[WATER]) drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.42f));\n',
     '            if (!dangerView && layerVisible[WATER]) drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.42f));\n', 'WATER draw'),
]:
    if text.count(old) != 1:
        raise RuntimeError(f'SceneMaskEditor {label} anchor: found {text.count(old)}')
    text = text.replace(old, new, 1)

old = '''            if (layerVisible[FALL]) {
                rebuildScriptFallDisplay();
                drawAccessibleEditableFall(batch);
                // Script markers render last so editable FALL can never bury them.
                drawAccessibleScriptFall(batch);
            }
'''
new = '''            if (!dangerView && layerVisible[FALL]) {
                rebuildScriptFallDisplay();
                drawAccessibleEditableFall(batch);
                // Script markers render last so editable FALL can never bury them.
                drawAccessibleScriptFall(batch);
            }
            if (dangerView) {
                // WATER is a hazard source, but the recovered scripted marks are what
                // reveal bridge/death positions that do not coincide with water pixels.
                drawMaskRuns(batch, masks[WATER], new Color(0.08f, 0.92f, 1f, 0.50f));
                rebuildScriptFallDisplay();
                drawAccessibleEditableFall(batch);
                drawAccessibleScriptFall(batch);
            }
'''
if text.count(old) != 1:
    raise RuntimeError('SceneMaskEditor accessible FALL render anchor not found')
text = text.replace(old, new, 1)

editor.write_text(text)
print('Composite DANGER installed: detector-v2 recovers room-changing death scripts; direct bridge 5830 shows WATER + editable FALL + scripted death/fall read-only')
