#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: simplify_fall_legend.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


# The first accessible FALL legend was technically accurate but too dense for a
# narrow sidebar. Keep the pattern swatches, but describe them in plain language.
old_summary = '''    let html = '<span class="fall-access-title">FALL · AGI HITSPEC / control 2</span>'
      + '<span class="fall-access-status' + (empty ? ' fall-access-none' : '') + '">'
      + (empty ? 'NONE IN THIS ROOM · ' : '')
      + 'HITSPEC: ' + fallText + ' · DETECTED SCRIPT: ' + scriptText + '</span>';
'''
new_summary = '''    let html = '<span class="fall-access-title">FALL AREAS</span>'
      + '<span class="fall-access-status' + (empty ? ' fall-access-none' : '') + '">'
      + (empty
          ? ('NONE IN THIS ROOM · Editable: ' + fallText + ' · Scripted: ' + scriptText)
          : ('Editable: ' + fallText + ' · Scripted: ' + scriptText))
      + '</span>';
'''
one(old_summary, new_summary, 'FALL plain-language summary')

old_legend = '''    if (ready && !empty) {
      html += '<span class="fall-access-status">'
        + '<span class="fall-pattern-swatch fall-editable-pattern"></span>//// = editable HITSPEC '
        + '<span class="fall-pattern-swatch fall-script-pattern"></span>two-tone = exact detected trigger '
        + '<span class="fall-pattern-swatch fall-halo-pattern"></span>dotted = visibility halo only'
        + '</span>';
'''
new_legend = '''    if (ready && !empty) {
      html += '<span class="fall-access-status" style="margin-top:5px">'
        + '<span style="display:block;margin:2px 0"><span class="fall-pattern-swatch fall-editable-pattern"></span><strong>Editable</strong> — paint or erase</span>'
        + '<span style="display:block;margin:2px 0"><span class="fall-pattern-swatch fall-script-pattern"></span><strong>Scripted</strong> — game trigger</span>'
        + '<span style="display:block;margin:2px 0"><span class="fall-pattern-swatch fall-halo-pattern"></span><strong>Dotted edge</strong> — display only</span>'
        + '</span>';
'''
one(old_legend, new_legend, 'FALL plain-language legend')

old_tag = "const BUILD_TAG = '20260829-fall-accessible-v7-signed';"
new_tag = "const BUILD_TAG = '20260829-fall-accessible-v9-zero-counts';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('FALL legend build tag not found')

path.write_text(text)
print('FALL legend simplified: plain Editable / Scripted / Dotted edge labels with exact empty-room counts')
