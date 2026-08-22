#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: adjust_room1_seed_alignment.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

# The AI silhouette itself lined up well, but its generated white mask extended
# lower than the painted tree. That made the inferred behind/collision zones sit
# too low (the blue footprint landed on the bridge). Keep the red/front mask
# untouched and move only the helper geometry upward.
def shift_runs(match, delta):
    name = match.group(1)
    runs = match.group(2)
    shifted = []
    for row in runs.split(';'):
        y_text, spans = row.split(':', 1)
        y = int(y_text) + delta
        if 0 <= y < 168:
            shifted.append(f'{y}:{spans}')
    return f'private static final String {name} = "' + ';'.join(shifted) + '";'

pattern = re.compile(r'private static final String (ROOM1_(?:BEHIND|COLLISION)_RUNS) = "([^"]*)";')
seen = {m.group(1) for m in pattern.finditer(text)}
if seen != {'ROOM1_BEHIND_RUNS', 'ROOM1_COLLISION_RUNS'}:
    raise RuntimeError(f'Room 1 helper mask constants not found: {seen}')

# Behind zone: 8 AGI rows upward. Collision/root footprint: 12 rows upward.
def repl(match):
    delta = -8 if match.group(1) == 'ROOM1_BEHIND_RUNS' else -12
    return shift_runs(match, delta)

text = pattern.sub(repl, text)

old = 'Gdx.app.getPreferences("agi-scene-mask-editor-v2")'
new = 'Gdx.app.getPreferences("agi-scene-mask-editor-v3")'
if text.count(old) != 1:
    raise RuntimeError('Expected v2 scene-mask preference namespace not found')
text = text.replace(old, new)

editor.write_text(text)
print('Room 1 depth helpers realigned: red unchanged, green -8 rows, blue -12 rows, prefs v3')
