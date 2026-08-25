#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_debug_image_only.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()

# COPY DEBUG should capture exactly what is currently on screen. It must not
# silently switch into mask-edit mode before taking the snapshot.
open_old = '''  function openCopyDebugFromButton() {
    if (!paintUiActive) {
      sendF2();
      setPaintUiActive(true);
      if (paintUiActive) applyBrushSize(brushSize);
      setTimeout(openDebugCapture, 120);
      return;
    }
    openDebugCapture();
  }
'''
open_new = '''  function openCopyDebugFromButton() {
    openDebugCapture();
  }
'''
if text.count(open_old) != 1:
    raise RuntimeError('COPY DEBUG capture-mode anchor not found')
text = text.replace(open_old, open_new, 1)

# Add a compact snapshot of live AGI state. GwtVariableData exposes the same
# SharedArrayBuffer used by the interpreter worker, so this is the state from the
# exact frame being captured rather than guessed browser-side values.
copy_anchor = '''  async function copyDebugCapture() {
'''
state_helper = r'''  function getAgiDebugLines() {
    try {
      const sab = window.__kq1agiVariableSAB;
      if (!sab) return ['AGI state: unavailable'];
      const a = new Int32Array(sab);
      const v = index => (a[index] || 0) & 255;
      const flag = index => a[256 + index] ? 1 : 0;
      const lines = [
        'AGI room=' + v(0) + ' prev=' + v(1) + ' score=' + v(3) +
          ' dir=' + v(6) + ' egoEdge=' + v(2) + ' objHit=' + v(4) + ' objEdge=' + v(5),
        'flags ONWATER=' + flag(0) + ' SEE_EGO=' + flag(1) + ' HITSPEC=' + flag(3) +
          ' ticks=' + (a[512] || 0),
        'mask enabled=' + (a[519] ? 1 : 0) + ' room=' + (a[520] || 0) +
          ' edit=' + (a[522] ? 1 : 0) + ' customWater=' + (a[523] ? 1 : 0)
      ];

      const moveCount = Math.max(0, Math.min(16, a[3884] || 0));
      let egoView = -1;
      for (let i = 0; i < moveCount; i++) {
        const base = 3885 + i * 6;
        if ((a[base] || 0) !== 0) continue;
        egoView = a[base + 1] || 0;
        const x = a[base + 2] || 0;
        const y = a[base + 3] || 0;
        const w = a[base + 4] || 0;
        const h = a[base + 5] || 0;
        lines.push('ego obj=0 view=' + egoView + ' visualXY=' + x + ',' + y + ' size=' + w + 'x' + h);
        break;
      }

      const offsetCount = Math.max(0, Math.min(32, a[3981] || 0));
      for (let i = 0; i < offsetCount; i++) {
        const base = 3982 + i * 5;
        if ((a[base] || 0) !== v(0) || (a[base + 1] || 0) !== 0) continue;
        if (egoView >= 0 && (a[base + 2] || 0) !== egoView) continue;
        lines.push('ego visualOffset=' + (a[base + 3] || 0) + ',' + (a[base + 4] || 0));
        break;
      }
      return lines.slice(0, 5);
    } catch (error) {
      return ['AGI state error: ' + error.message];
    }
  }

  async function copyDebugCapture() {
'''
if text.count(copy_anchor) != 1:
    raise RuntimeError('copyDebugCapture function anchor not found')
text = text.replace(copy_anchor, state_helper, 1)

# The final clipboard payload is image/png only. The issue and useful AGI state
# are burned into the screenshot itself, so pasting into ChatGPT produces one
# self-contained image.
meta_old = '''    const meta = 'KQ1 DEBUG — ' + issue + '\\n' + location.href + '\\n' + new Date().toISOString();
'''
if text.count(meta_old) != 1:
    raise RuntimeError('debug metadata anchor not found')
text = text.replace(meta_old, '', 1)

lines_old = '''    const lines = wrapDebugText(ctx, issue, debugSnapshot.width - padding * 2).slice(0, 3);
    const footerHeight = padding * 2 + lineHeight * (lines.length + 3);
'''
lines_new = '''    const lines = wrapDebugText(ctx, issue, debugSnapshot.width - padding * 2).slice(0, 3);
    const agiLines = getAgiDebugLines();
    const metaFontSize = Math.max(10, Math.round(fontSize * .62));
    const metaLineHeight = Math.round(metaFontSize * 1.25);
    const footerHeight = padding * 2 + lineHeight * (lines.length + 1) + metaLineHeight * (agiLines.length + 1);
'''
if text.count(lines_old) != 1:
    raise RuntimeError('debug overlay height anchor not found')
text = text.replace(lines_old, lines_new, 1)

# Replace the old URL/timestamp drawing with the live AGI state. This keeps the
# screenshot diagnostic while still being a single pasteable image.
meta_draw_old = '''    out.font = '500 ' + Math.max(10, Math.round(fontSize * .7)) + 'px monospace';
    out.fillStyle = '#d0d0d0';
    out.fillText(location.href, padding, y);
    y += Math.round(lineHeight * .85);
    out.fillText(new Date().toISOString(), padding, y);
'''
meta_draw_new = '''    y += Math.round(metaLineHeight * .25);
    out.font = '600 ' + metaFontSize + 'px monospace';
    out.fillStyle = '#8fe8ff';
    for (const line of agiLines) {
      out.fillText(line, padding, y);
      y += metaLineHeight;
    }
'''
if text.count(meta_draw_old) != 1:
    raise RuntimeError('debug URL/timestamp drawing anchor not found')
text = text.replace(meta_draw_old, meta_draw_new, 1)

clipboard_old = '''    const png = await canvasToBlob(output);
    let copied = false;
    if (navigator.clipboard && window.ClipboardItem) {
      try {
        const item = new ClipboardItem({
          'image/png': png,
          'text/plain': new Blob([meta], { type: 'text/plain' })
        });
        await navigator.clipboard.write([item]);
        copied = true;
      } catch (multiError) {
        try {
          await navigator.clipboard.write([new ClipboardItem({ 'image/png': png })]);
          copied = true;
        } catch (imageError) {
          console.warn('Image clipboard copy failed', imageError);
        }
      }
    }
    if (!copied && navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(meta);
      debugToast.textContent = 'SCREENSHOT COPY BLOCKED — ISSUE TEXT COPIED';
    } else {
      debugToast.textContent = 'DEBUG CAPTURE COPIED — PASTE IT HERE';
    }
'''
clipboard_new = '''    const png = await canvasToBlob(output);
    if (!navigator.clipboard || !window.ClipboardItem) {
      throw new Error('This browser does not allow copying PNG images to the clipboard.');
    }
    await navigator.clipboard.write([
      new ClipboardItem({ 'image/png': png })
    ]);
    debugToast.textContent = 'IMAGE COPIED';
'''
if text.count(clipboard_old) != 1:
    raise RuntimeError('debug mixed clipboard payload anchor not found')
text = text.replace(clipboard_old, clipboard_new, 1)

text = text.replace('COPY IMAGE + TEXT', 'COPY IMAGE')
text = text.replace('Your note is stamped directly onto the screenshot. Enter = copy · Esc = cancel.',
                    'Your note and AGI state are drawn directly on the screenshot. Enter = copy image · Esc = cancel.')
text = text.replace('DEBUG CAPTURE COPIED — PASTE IT HERE', 'IMAGE COPIED')
text = text.replace('Capture the game with debug text stamped onto the image',
                    'Capture one game image with your debug note and AGI state overlaid')

path.write_text(text)
print('Debug capture: current game frame + typed issue + live AGI state burned into one PNG')