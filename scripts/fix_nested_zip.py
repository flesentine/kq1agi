#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_nested_zip.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
path = root / 'html/src/main/java/com/agifans/agile/gwt/GwtDialogHandler.java'
text = path.read_text()

old = '''                    for (int i=0; i < files.length(); i++) {\n                        String fileName = files.get(i);\n                        if (isGameFile(fileName)) {\n                            JSFile gameFile = jsZip.getFile(fileName);\n                            String fileNameLowerCase = fileName.toLowerCase();\n                            gameFilesMap.put(fileNameLowerCase, gameFile.asUint8Array().toByteArray());\n'''

new = '''                    for (int i=0; i < files.length(); i++) {\n                        String zipEntryName = files.get(i);\n                        String normalizedName = zipEntryName.replace('\\\\', '/');\n                        int lastSlash = normalizedName.lastIndexOf('/');\n                        String fileName = (lastSlash >= 0)? normalizedName.substring(lastSlash + 1) : normalizedName;\n                        if (isGameFile(fileName)) {\n                            JSFile gameFile = jsZip.getFile(zipEntryName);\n                            String fileNameLowerCase = fileName.toLowerCase();\n                            gameFilesMap.put(fileNameLowerCase, gameFile.asUint8Array().toByteArray());\n'''

if text.count(old) != 1:
    raise RuntimeError('Expected ZIP import loop was not found exactly once')

path.write_text(text.replace(old, new))

# This script already runs early in every browser build, so chain the gameplay
# rewind patch here without adding another workflow maintenance point.
import runpy
runpy.run_path(str(Path(__file__).with_name('add_shift_left_rewind.py')), run_name='__main__')

print('Patched AGILE ZIP importer to accept game files inside folders; Shift+Left rewind installed.')
