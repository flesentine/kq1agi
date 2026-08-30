#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_scene_mask_reset_default.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()


def one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


# Track only reset-triggered Sierra reseeds. Initial room migration still uses the
# existing waitingForControlSeed flag normally.
one(
'''    private boolean waitingForControlSeed;\n''',
'''    private boolean waitingForControlSeed;\n    private boolean resetSeedPending;\n''',
'reset seed field'
)

# Never carry a reset handshake across a room transition.
one(
'''        room = current;\n        matteOffsetX = 0;\n''',
'''        room = current;\n        resetSeedPending = false;\n        matteOffsetX = 0;\n''',
'room-change reset state'
)

# If a reset reseed completes, it is now a stable redo/undo state.
one(
'''        waitingForControlSeed = false;\n        waterActive = true;\n        fallActive = true;\n''',
'''        waitingForControlSeed = false;\n        resetSeedPending = false;\n        waterActive = true;\n        fallActive = true;\n''',
'adopt reset seed completion'
)

# Add a whole-room reset immediately after the existing snapshot helper. Layers
# 0..4 are editable FRONT/BLOCK/BEHIND/WATER/FALL. Layer 5 is the detected
# scripted FALL/suppression plane and is intentionally preserved: RESET TO GAME
# must never delete Sierra's detected script-danger information.
anchor = '''    private void captureUndoSnapshot() {\n        copyAllMasks(masks, undoMasks);\n        undoValid = true;\n        redoValid = false;\n    }\n\n'''
helpers = r'''    private void captureUndoSnapshot() {
        copyAllMasks(masks, undoMasks);
        undoValid = true;
        redoValid = false;
    }

    private void clearEditableMaskLayer(int layer) {
        if (layer < 0 || layer > FALL) return;
        for (int y = 0; y < HEIGHT; y++) {
            for (int x = 0; x < WIDTH; x++) masks[layer][y][x] = false;
        }
        data.clearSceneMaskLayer(layer);
    }

    private void resetCurrentRoomToGameDefault() {
        ensureRoom();
        captureUndoSnapshot();

        // Cancel any older import before rebuilding this room's baseline.
        waitingForControlSeed = false;
        resetSeedPending = false;
        data.setSceneControlSeedState(room + 1);

        // Restore the built-in replacement-art baseline. Room 1 has the approved
        // foreground/behind matte and root collision seed; other rooms begin with
        // no replacement-art depth until authored.
        for (int layer = OCCLUDER; layer <= FALL; layer++) clearEditableMaskLayer(layer);
        if (room == 1) {
            decodeRuns(ROOM1_OCCLUDER_RUNS, masks[OCCLUDER]);
            decodeRuns(ROOM1_COLLISION_RUNS, masks[COLLISION]);
            decodeRuns(ROOM1_BEHIND_RUNS, masks[BEHIND]);
        }

        // BLOCK/WATER/FALL are then rebuilt from Sierra's real control picture.
        // Existing room-1 root collision pixels intentionally win where they
        // overlap, matching the normal first-load migration behavior.
        waterActive = true;
        fallActive = true;
        data.setSceneMaskWaterActive(true);
        data.setSceneMaskFallActive(true);
        syncAll();

        prefs.putBoolean(key("unifiedControlV1"), false);
        waitingForControlSeed = true;
        resetSeedPending = true;
        data.setSceneControlSeedState(-(room + 1));
        dirty = true;
        saveRoom();
        notice("RESET TO GAME DEFAULT - UNDO AVAILABLE");
    }

'''
one(anchor, helpers, 'reset helper anchor')

# Undo must be able to cancel the asynchronous Sierra reseed if the user clicks
# UNDO immediately after RESET TO GAME. Once cancelled, the restored snapshot is
# authoritative and cannot be overwritten by a late seed request.
undo_anchor = '''        copyAllMasks(masks, redoMasks);\n        copyAllMasks(undoMasks, masks);\n'''
undo_repl = '''        if (resetSeedPending) {\n            waitingForControlSeed = false;\n            resetSeedPending = false;\n            data.setSceneControlSeedState(room + 1);\n            prefs.putBoolean(key("unifiedControlV1"), true);\n        }\n        copyAllMasks(masks, redoMasks);\n        copyAllMasks(undoMasks, masks);\n'''
one(undo_anchor, undo_repl, 'undo reset-cancel hook')

# Browser RESET TO GAME dispatches D. Keep it adjacent to undo/redo commands so
# it remains a workspace command rather than a paint-layer shortcut.
key_anchor = '''        if (keycode == Input.Keys.Y) {\n            redoMaskEdit();\n            return true;\n        }\n'''
key_repl = '''        if (keycode == Input.Keys.Y) {\n            redoMaskEdit();\n            return true;\n        }\n        if (keycode == Input.Keys.D) {\n            resetCurrentRoomToGameDefault();\n            return true;\n        }\n'''
one(key_anchor, key_repl, 'reset command key')

editor.write_text(text)
print('Scene mask RESET TO GAME installed: current room returns to built-in/Sierra baseline as one undoable action')
