#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_fall_scan_refresh.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()

# The browser is the thing waiting for these results, so let it repair a lost or
# stale room request itself. A negative value encodes an explicit request for the
# current room; the worker turns it positive when the scan is complete.
old_state = '''      const room = readDebugInt(values, 0) & 255;\n      const fallReady = readDebugInt(values, FALL_CONTROL_SEED_STATE) === room + 1;\n      const scriptReady = readDebugInt(values, SCRIPT_FALL_SEED_STATE) === room + 1;\n      return {\n'''
new_state = '''      const room = readDebugInt(values, 0) & 255;\n      const expectedSeed = room + 1;\n      let fallSeed = readDebugInt(values, FALL_CONTROL_SEED_STATE);\n      let scriptSeed = readDebugInt(values, SCRIPT_FALL_SEED_STATE);\n\n      // If initialization cleared the request, or this slot still belongs to a\n      // previous room, reissue it directly. Do not repeatedly rewrite an active\n      // request or a completed scan.\n      if (room > 0 && fallSeed !== expectedSeed && fallSeed !== -expectedSeed) {\n        Atomics.store(values, FALL_CONTROL_SEED_STATE, -expectedSeed);\n        fallSeed = -expectedSeed;\n      }\n      if (room > 0 && scriptSeed !== expectedSeed && scriptSeed !== -expectedSeed) {\n        Atomics.store(values, SCRIPT_FALL_SEED_STATE, -expectedSeed);\n        scriptSeed = -expectedSeed;\n      }\n\n      const fallReady = fallSeed === expectedSeed;\n      const scriptReady = scriptSeed === expectedSeed;\n      return {\n'''
count = text.count(old_state)
if count != 1:
    raise RuntimeError(f'FALL scan state block: expected 1, found {count}')
text = text.replace(old_state, new_state, 1)

old = "const BUILD_TAG = '20260828-fall-accessible-v1';"
new = "const BUILD_TAG = '20260828-fall-accessible-v3-handshake';"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise RuntimeError('FALL accessibility build tag not found for handshake refresh')

path.write_text(text)
print('FALL scan handshake repaired: browser reissues stale room requests and cache is busted')
