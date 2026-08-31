#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_danger_text_semantics.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
runtime = root / 'core/src/main/java/com/agifans/agile/SceneMaskRuntime.java'
text = runtime.read_text()

# Detector v4: nouns that merely describe scenery are not evidence that the IF
# is lethal. Room/castle logic commonly says "bridge", "moat", "alligator" or
# "current" in LOOK/description messages guarded by large posn() rectangles.
# Those generic words were turning harmless description regions into DANGER.
old = '''        return s.contains("fall") || s.contains("fell") || s.contains("drown")
                || s.contains("dead") || s.contains("died") || s.contains("death")
                || s.contains("killed") || s.contains("plunge") || s.contains("splash")
                || s.contains("bridge") || s.contains("moat") || s.contains("alligator")
                || s.contains("current") || s.contains("slip down") || s.contains("false move");
'''
new = '''        return s.contains("fallen") || s.contains("fell") || s.contains("drown")
                || s.contains("dead") || s.contains("died") || s.contains("death")
                || s.contains("killed") || s.contains("plunge") || s.contains("swept under")
                || s.contains("slip down") || s.contains("false move")
                || s.contains("end has come") || s.contains("misfortune strikes");
'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f'dangerText v4 anchor: expected 1 match, found {count}')
text = text.replace(old, new, 1)
runtime.write_text(text)

# Force a clean reseed. Saved detector-v3 masks may contain regions classified
# from the old generic scenery vocabulary, so accepting that cache would hide
# the semantic fix until users manually clear browser storage.
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()
replacements = [
    ('scriptDetectorVersion >= 3', 'scriptDetectorVersion >= 4'),
    ('prefs.putInteger(key("scriptFallDetectorVersion"), 3);',
     'prefs.putInteger(key("scriptFallDetectorVersion"), 4);'),
]
for old, new in replacements:
    count = text.count(old)
    if count < 1:
        raise RuntimeError(f'detector-v4 cache marker not found: {old}')
    text = text.replace(old, new)
editor.write_text(text)

print('DANGER detector v4 installed: scenery words no longer imply death; cached v3 masks are reseeded')
