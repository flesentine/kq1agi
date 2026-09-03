#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_phase1d.py /path/to/index.html')

path = Path(sys.argv[1])
html = path.read_text()
base = '<script type="module" src="certification/certification-panel.mjs"></script>'
phase1d = '<script type="module" src="certification/certification-phase1d.mjs"></script>'
if html.count(base) != 1:
    raise RuntimeError(f'Phase -1D base module anchor: expected 1 match, found {html.count(base)}')
if phase1d in html:
    raise RuntimeError('Phase -1D module is already present')
html = html.replace(base, base + '\n' + phase1d, 1)
for marker in ['id="phase1d-recording-bootstrap"', 'id="certify-replay-button"', phase1d]:
    if marker not in html:
        raise RuntimeError(f'Phase -1D browser marker missing: {marker}')
path.write_text(html)
print('Phase -1D replay module loaded after Phase -1C panel')
