#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_background_mask.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
path = root / 'core/src/main/java/com/agifans/agile/Commands.java'
text = path.read_text()


def add_capture_after_split(block: str, label: str) -> str:
    matches = list(re.finditer(r'(?m)^(\s+)splitPriorityPixels\(\);\s*$', block))
    if len(matches) != 1:
        raise RuntimeError(f'{label}: expected exactly one splitPriorityPixels call, found {len(matches)}')
    match = matches[0]
    indent = match.group(1)
    capture = (
        '\n' + indent + 'pixelData.captureBackground(\n'
        + indent + '        state.visualPixels, (8 * state.pictureRow) * 320, state.visualPixels.length);'
    )
    return block[:match.end()] + capture + block[match.end():]


# add.to.pic and add.to.pic.v permanently alter the room picture. When a modern room
# background is active, those pixels are scenery, not animated foreground objects, so
# fold them into the background mask immediately after the AGI priority map is updated.
for opcode in (122, 123):
    pattern = re.compile(
        rf'(case {opcode}: // add\.to\.pic(?:\.v)?\n.*?)(\n\s*break;)',
        re.DOTALL,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f'opcode {opcode}: expected one case block, found {len(matches)}')
    match = matches[0]
    patched_block = add_capture_after_split(match.group(1), f'opcode {opcode}')
    text = text[:match.start()] + patched_block + match.group(2) + text[match.end():]

# Saved-game replay has its own ADD_TO_PIC path and must rebuild the same mask.
replay_pattern = re.compile(
    r'(case ADD_TO_PIC:\n.*?picObj\.addToPicture\(.*?\);\n.*?splitPriorityPixels\(\);)(\n\s*\}\n\s*break;)',
    re.DOTALL,
)
matches = list(replay_pattern.finditer(text))
if len(matches) != 1:
    raise RuntimeError(f'Expected one replay ADD_TO_PIC block, found {len(matches)}')
match = matches[0]
patched_block = add_capture_after_split(match.group(1), 'replay ADD_TO_PIC')
text = text[:match.start()] + patched_block + match.group(2) + text[match.end():]

path.write_text(text)
print('Background mask now absorbs add.to.pic scenery')
