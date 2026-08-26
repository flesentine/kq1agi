#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: smooth_rewind.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# Keep the currently displayed frame on screen while a hidden rewind snapshot is
# being deserialized. A normal Sierra restore intentionally clears the whole text
# screen first, but doing that several times per second during rewind produces a
# visible black flash. Rewind immediately rebuilds the picture afterwards, so the
# clear is unnecessary for this private no-dialog restore path.
saved_games = root / 'core/src/main/java/com/agifans/agile/SavedGames.java'
text = saved_games.read_text()
old = '''        // If we're sure that this saved game file is for this game, then continue.\n        state.init();\n        textGraphics.clearLines(0, 24, 0);\n'''
new = '''        // If we're sure that this saved game file is for this game, then continue.\n        boolean rewindRestore = forcedSavedGame != null\n                && REWIND_DESCRIPTION.equals(forcedSavedGame.description);\n        state.init();\n        // Normal restores blank the screen before reconstruction. During rewind that\n        // creates a distracting black flash, so leave the last complete frame visible\n        // until replayScriptEvents/showPicture publish the rewound frame.\n        if (!rewindRestore) {\n            textGraphics.clearLines(0, 24, 0);\n        }\n'''
if text.count(old) != 1:
    raise RuntimeError('SavedGames restore clear-screen anchor expected once, found %d' % text.count(old))
text = text.replace(old, new, 1)
saved_games.write_text(text)

# Continuous hold originally restored a full AGI state about 6.7 times/second.
# Even without the black clear, that is needlessly aggressive for one-second
# snapshots and can expose intermediate shared-buffer updates. Three steps/second
# still feels responsive while substantially reducing visible redraw churn.
interpreter = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
text = interpreter.read_text()
old = '    private static final long REWIND_HOLD_STEP_MS = 150L;\n'
new = '    private static final long REWIND_HOLD_STEP_MS = 325L;\n'
if text.count(old) != 1:
    raise RuntimeError('Interpreter rewind cadence anchor expected once, found %d' % text.count(old))
text = text.replace(old, new, 1)
interpreter.write_text(text)

print('Rewind smoothed: no black pre-clear and hold cadence reduced to ~3 restores/sec')
