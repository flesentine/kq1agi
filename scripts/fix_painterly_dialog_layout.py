#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_painterly_dialog_layout.py /path/to/agile-gdx')

# CLEAN_V4 moved the real fix into add_painterly_dialog_frame.py and replaced
# the source artwork with a pre-cleaned 160x41 hard-alpha asset. Keep this file
# as a harmless compatibility shim for older workflow references.
root = Path(sys.argv[1]).resolve()
text_graphics = root / 'core/src/main/java/com/agifans/agile/TextGraphics.java'
text = text_graphics.read_text()
if 'PAINTERLY_DIALOG_FRAME CLEAN_V4' not in text:
    raise RuntimeError('clean painterly dialog patch must run first')
print('Painterly dialog CLEAN_V4 layout already installed; no legacy alpha remap applied')
