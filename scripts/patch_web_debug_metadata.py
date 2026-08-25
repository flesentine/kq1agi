#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_debug_metadata.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()

# Newer patch_web_debug_image_only.py already burns richer AGI metadata into the
# screenshot. Keep this older patch compatible with that output and retain the
# historical readAgiDebugLines symbol used by CI verification.
if 'function getAgiDebugLines()' in text:
    if 'function readAgiDebugLines()' not in text:
        anchor = '''  async function copyDebugCapture() {\n'''
        alias = '''  function readAgiDebugLines() {\n    return getAgiDebugLines();\n  }\n\n  async function copyDebugCapture() {\n'''
        if text.count(anchor) != 1:
            raise RuntimeError('copyDebugCapture anchor not found for metadata alias')
        text = text.replace(anchor, alias, 1)
        path.write_text(text)
    print('Debug capture metadata already present; compatibility alias retained')
    raise SystemExit(0)

helper_anchor = '''  async function copyDebugCapture() {\n'''
helper = r'''  function readAgiDebugLines() {
    try {
      const sab = window.__kq1agiVariableSAB;
      if (!sab || typeof SharedArrayBuffer === 'undefined' || !(sab instanceof SharedArrayBuffer)) {
        return ['AGI state: shared buffer unavailable'];
      }
      const a = new Int32Array(sab);
      const v = index => (a[index] || 0) & 0xff;
      const flag = index => a[256 + index] === 1;

      let ego = null;
      const count = Math.max(0, Math.min(16, a[3884] || 0));
      for (let i = 0; i < count; i++) {
        const base = 3885 + (i * 6);
        if ((a[base] || 0) === 0) {
          ego = {
            view: a[base + 1] || 0,
            x: a[base + 2] || 0,
            y: a[base + 3] || 0,
            w: a[base + 4] || 0,
            h: a[base + 5] || 0
          };
          break;
        }
      }

      const roomLine = 'AGI room=' + v(0) + ' prev=' + v(1)
          + ' score=' + v(3) + '/' + v(7)
          + ' dir=' + v(6) + ' egoEdge=' + v(2)
          + ' objHit=' + v(4) + ' objEdge=' + v(5);
      const egoLine = ego
          ? ('EGO view=' + ego.view + ' visual=(' + ego.x + ',' + ego.y + ') size=' + ego.w + 'x' + ego.h
              + ' onWater=' + flag(0) + ' hitSpecial=' + flag(3) + ' seeEgo=' + flag(1))
          : ('EGO not published onWater=' + flag(0) + ' hitSpecial=' + flag(3));
      const maskLine = 'MASK enabled=' + (a[519] === 1)
          + ' room=' + (a[520] || 0)
          + ' behind=' + (a[521] === 1)
          + ' edit=' + (a[522] === 1)
          + ' customWater=' + (a[523] === 1);
      return [roomLine, egoLine, maskLine];
    } catch (error) {
      return ['AGI state read failed: ' + error.message];
    }
  }

  async function copyDebugCapture() {
'''
if text.count(helper_anchor) != 1:
    raise RuntimeError('copyDebugCapture anchor not found')
text = text.replace(helper_anchor, helper, 1)

lines_anchor = '''    const lines = wrapDebugText(ctx, issue, debugSnapshot.width - padding * 2).slice(0, 3);\n    const footerHeight = padding * 2 + lineHeight * (lines.length + 3);\n'''
lines_repl = '''    const lines = wrapDebugText(ctx, issue, debugSnapshot.width - padding * 2).slice(0, 3);\n    const agiLines = readAgiDebugLines();\n    const footerHeight = padding * 2 + lineHeight * (lines.length + agiLines.length + 2);\n'''
if text.count(lines_anchor) != 1:
    raise RuntimeError('overlay line-count anchor not found')
text = text.replace(lines_anchor, lines_repl, 1)

meta_anchor = '''    out.font = '500 ' + Math.max(10, Math.round(fontSize * .7)) + 'px monospace';\n    out.fillStyle = '#d0d0d0';\n    out.fillText(location.href, padding, y);\n    y += Math.round(lineHeight * .85);\n    out.fillText(new Date().toISOString(), padding, y);\n'''
meta_repl = '''    y += Math.round(lineHeight * .25);\n    out.font = '600 ' + Math.max(10, Math.round(fontSize * .68)) + 'px monospace';\n    out.fillStyle = '#9fe7ff';\n    for (const line of agiLines) {\n      out.fillText(line, padding, y);\n      y += Math.round(lineHeight * .82);\n    }\n'''
if text.count(meta_anchor) != 1:
    raise RuntimeError('old URL/timestamp metadata block not found')
text = text.replace(meta_anchor, meta_repl, 1)

path.write_text(text)
print('Debug capture metadata added: room/ego/water/mask state stamped into the copied game screenshot')