#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_fall_scan_refresh.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()
old = "const BUILD_TAG = '20260828-fall-accessible-v1';"
new = "const BUILD_TAG = '20260828-fall-accessible-v2-scan';"

if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise RuntimeError('FALL accessibility build tag not found for scan refresh')

path.write_text(text)
print('FALL scan runtime cache-busted')
