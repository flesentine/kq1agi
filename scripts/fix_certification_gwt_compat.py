#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_certification_gwt_compat.py /path/to/instrumented-agile-gdx')

root = Path(sys.argv[1]).resolve()
store = root / 'html/src/main/java/com/agifans/agile/gwt/CertificationSavedGameStore.java'
if not store.exists():
    raise RuntimeError(f'missing generated certification save store: {store}')

text = store.read_text()
old = '''        game.savedGameData = (source.savedGameData == null ? new byte[0] : source.savedGameData.clone());\n'''
new = '''        if (source.savedGameData == null) {\n            game.savedGameData = new byte[0];\n        } else {\n            game.savedGameData = new byte[source.savedGameData.length];\n            if (source.savedGameData.length > 0) {\n                System.arraycopy(source.savedGameData, 0, game.savedGameData, 0, source.savedGameData.length);\n            }\n        }\n'''
if text.count(old) != 1:
    raise RuntimeError(f'GWT byte-array copy fix: expected 1 clone site, found {text.count(old)}')
store.write_text(text.replace(old, new, 1))
print('Certification GWT compatibility applied: byte-array copies use System.arraycopy')
