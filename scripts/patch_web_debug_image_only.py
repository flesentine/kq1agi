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

# The final clipboard payload is image/png only. The issue is burned into the
# screenshot itself, so pasting into ChatGPT produces one self-contained image.
meta_old = '''    const meta = 'KQ1 DEBUG — ' + issue + '\\n' + location.href + '\\n' + new Date().toISOString();
'''
if text.count(meta_old) != 1:
    raise RuntimeError('debug metadata anchor not found')
text = text.replace(meta_old, '', 1)

# Keep the overlay compact: just ISSUE + what the user typed. No URL/timestamp.
height_old = '''    const footerHeight = padding * 2 + lineHeight * (lines.length + 3);
'''
height_new = '''    const footerHeight = padding * 2 + lineHeight * (lines.length + 1);
'''
if text.count(height_old) != 1:
    raise RuntimeError('debug overlay height anchor not found')
text = text.replace(height_old, height_new, 1)

meta_draw_old = '''    out.font = '500 ' + Math.max(10, Math.round(fontSize * .7)) + 'px monospace';
    out.fillStyle = '#d0d0d0';
    out.fillText(location.href, padding, y);
    y += Math.round(lineHeight * .85);
    out.fillText(new Date().toISOString(), padding, y);
'''
if text.count(meta_draw_old) != 1:
    raise RuntimeError('debug URL/timestamp drawing anchor not found')
text = text.replace(meta_draw_old, '', 1)

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
    debugToast.textContent = 'IMAGE COPIED — PASTE IT HERE';
'''
if text.count(clipboard_old) != 1:
    raise RuntimeError('debug mixed clipboard payload anchor not found')
text = text.replace(clipboard_old, clipboard_new, 1)

text = text.replace('COPY IMAGE + TEXT', 'COPY IMAGE')
text = text.replace('Your note is stamped directly onto the screenshot. Enter = copy · Esc = cancel.',
                    'Your note is drawn directly on the screenshot. Enter = copy image · Esc = cancel.')
text = text.replace('DEBUG CAPTURE COPIED — PASTE IT HERE', 'IMAGE COPIED — PASTE IT HERE')
text = text.replace('Capture the game with debug text stamped onto the image',
                    'Capture one game image with your debug note overlaid')

path.write_text(text)
print('Debug capture simplified: current screen + typed issue burned into one PNG; clipboard contains image only')
