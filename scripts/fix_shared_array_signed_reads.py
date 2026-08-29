#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_shared_array_signed_reads.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
path = root / 'html/src/main/java/com/agifans/agile/gwt/SharedArray.java'
text = path.read_text()

# SharedArray stores Java ints in a Uint32Array. Positive values round-trip fine,
# but negative Java sentinels (for example Room 1 seed request = -2) otherwise
# come back to compiled GWT as 4294967294. That makes Java comparisons against
# -2 fail on the worker even though the browser's Int32Array view correctly shows
# -2. Force the atomic load through JavaScript's signed 32-bit coercion so the
# SharedArray behaves like a Java int[] on both sides.
old = '        return Atomics.load(this.storage, index);\n'
new = '        return Atomics.load(this.storage, index) | 0;\n'
if text.count(old) != 1:
    raise RuntimeError(f'SharedArray atomic get anchor: expected 1, found {text.count(old)}')
path.write_text(text.replace(old, new, 1))

print('SharedArray signed reads fixed: negative seed sentinels now round-trip as Java int values')
