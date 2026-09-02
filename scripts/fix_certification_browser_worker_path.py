#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_certification_browser_worker_path.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
worker = root / 'html/src/main/java/com/agifans/agile/worker/AgileWebWorker.java'
text = worker.read_text()
old = 'this.importScript("/opfs-saved-games.js");'
new = 'this.importScript("../opfs-saved-games.js");'

if new in text:
    print('Certification browser worker path already relative')
elif text.count(old) == 1:
    worker.write_text(text.replace(old, new, 1))
    print('Certification browser worker bootstrap path made relative')
else:
    raise RuntimeError('Could not find exactly one certification worker OPFS bootstrap import')
