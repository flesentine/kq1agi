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
old_count = text.count(old)
new_count = text.count(new)

if old_count == 0 and new_count == 1:
    print('Certification browser worker path already relative')
elif old_count == 1 and new_count == 0:
    worker.write_text(text.replace(old, new, 1))
    print('Certification browser worker bootstrap path made relative')
else:
    raise RuntimeError(
        'Expected exactly one certification worker OPFS bootstrap import in either '
        f'root-relative or relative form; found old={old_count}, new={new_count}'
    )
