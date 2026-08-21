#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_scene_mask_java_character.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
editor = root / 'core/src/main/java/com/agifans/agile/SceneMaskEditor.java'
text = editor.read_text()

old_for_digit = 'Character.forDigit(value, 16)'
old_digit = 'Character.digit(text.charAt(p++), 16)'

if text.count(old_for_digit) != 1:
    raise RuntimeError('Expected one Character.forDigit call in SceneMaskEditor')
if text.count(old_digit) != 1:
    raise RuntimeError('Expected one Character.digit call in SceneMaskEditor')

# AGILE already has com.agifans.agile.Character in this package, so unqualified
# Character resolves to the game class rather than java.lang.Character.
text = text.replace(old_for_digit, 'java.lang.Character.forDigit(value, 16)')
text = text.replace(old_digit, 'java.lang.Character.digit(text.charAt(p++), 16)')
editor.write_text(text)

print('Qualified java.lang.Character calls in SceneMaskEditor')
