#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_background_mask.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
path = root / 'core/src/main/java/com/agifans/agile/Commands.java'
text = path.read_text()

capture = (
    '                        pixelData.captureBackground(\n'
    '                                state.visualPixels, (8 * state.pictureRow) * 320, state.visualPixels.length);\n'
)

# add.to.pic and add.to.pic.v permanently alter the room picture. When a modern room
# background is active, those pixels are scenery, not animated foreground objects, so
# fold them into the background mask immediately after the AGI priority map is updated.
pattern = re.compile(
    r'(case 12[23]: // add\.to\.pic(?:\.v)?\n'
    r'.*?\n\s+splitPriorityPixels\(\);\n)'
    r'(\s+picObj\.show\(pixelData\);)',
    re.DOTALL,
)

def add_capture(match):
    block = match.group(1)
    indent_match = re.search(r'(?m)^(\s+)splitPriorityPixels\(\);\s*$', block)
    if not indent_match:
        raise RuntimeError('Could not determine add.to.pic indentation')
    indent = indent_match.group(1)
    local_capture = (
        indent + 'pixelData.captureBackground(\n'
        + indent + '        state.visualPixels, (8 * state.pictureRow) * 320, state.visualPixels.length);\n'
    )
    return block + local_capture + match.group(2)

text, count = pattern.subn(add_capture, text)
if count != 2:
    raise RuntimeError(f'Expected to patch add.to.pic and add.to.pic.v, patched {count}')

# Saved-game replay has its own ADD_TO_PIC path and must rebuild the same mask.
replay_pattern = re.compile(
    r'(case ADD_TO_PIC:\n.*?picObj\.addToPicture\(.*?\);\n\s+splitPriorityPixels\(\);\n)',
    re.DOTALL,
)

matches = list(replay_pattern.finditer(text))
if len(matches) != 1:
    raise RuntimeError(f'Expected one replay ADD_TO_PIC block, found {len(matches)}')
match = matches[0]
block = match.group(1)
indent_match = re.search(r'(?m)^(\s+)splitPriorityPixels\(\);\s*$', block)
if not indent_match:
    raise RuntimeError('Could not determine replay ADD_TO_PIC indentation')
indent = indent_match.group(1)
replay_capture = (
    indent + 'pixelData.captureBackground(\n'
    + indent + '        state.visualPixels, (8 * state.pictureRow) * 320, state.visualPixels.length);\n'
)
replacement = block + replay_capture
text = text[:match.start()] + replacement + text[match.end():]

path.write_text(text)
print('Background mask now absorbs add.to.pic scenery')
