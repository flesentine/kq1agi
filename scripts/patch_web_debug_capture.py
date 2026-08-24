#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_debug_capture.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()

css_anchor = '''  </style>
'''
css = '''    #debug-capture {
      position: fixed; inset: 0; z-index: 20000; display: none;
      background: rgba(0,0,0,.72); align-items: center; justify-content: center;
      padding: 24px; box-sizing: border-box;
      font: 14px system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    }
    #debug-card {
      width: min(980px, 94vw); max-height: 94vh; overflow: auto;
      background: #121212; color: #fff; border: 1px solid #555; border-radius: 12px;
      box-shadow: 0 18px 60px rgba(0,0,0,.65); padding: 14px;
    }
    #debug-preview { width: 100%; max-height: 68vh; object-fit: contain; background: #000; display: block; }
    #debug-issue {
      width: 100%; margin-top: 12px; padding: 12px 14px; box-sizing: border-box;
      border: 2px solid #888; border-radius: 8px; outline: none;
      background: #080808; color: #fff; font: 16px system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    }
    #debug-issue:focus { border-color: #fff; }
    #debug-help { margin-top: 8px; color: #bbb; }
    #debug-toast {
      position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%);
      z-index: 20001; display: none; padding: 10px 14px; border-radius: 8px;
      background: rgba(0,0,0,.9); color: #fff; border: 1px solid #777;
      font: 700 14px system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    }
  </style>
'''
if text.count(css_anchor) != 1:
    raise RuntimeError('index style close anchor not found')
text = text.replace(css_anchor, css, 1)

html_anchor = '''<div id="boot-message"><div id="boot-text">Preparing King's Quest…</div></div>
'''
html = '''<div id="boot-message"><div id="boot-text">Preparing King's Quest…</div></div>
<div id="debug-capture">
  <div id="debug-card">
    <img id="debug-preview" alt="Debug screenshot preview">
    <input id="debug-issue" type="text" autocomplete="off" spellcheck="true"
           placeholder="Type the issue quickly, then press Enter">
    <div id="debug-help">Enter = copy screenshot + issue to clipboard · Esc = cancel</div>
  </div>
</div>
<div id="debug-toast">DEBUG CAPTURE COPIED — PASTE IT HERE</div>
'''
if text.count(html_anchor) != 1:
    raise RuntimeError('index boot-message anchor not found')
text = text.replace(html_anchor, html, 1)

const_anchor = '''  const exportBgButton = document.getElementById('export-bg-button');
'''
const_repl = '''  const exportBgButton = document.getElementById('export-bg-button');
  const debugCapture = document.getElementById('debug-capture');
  const debugPreview = document.getElementById('debug-preview');
  const debugIssue = document.getElementById('debug-issue');
  const debugToast = document.getElementById('debug-toast');
  let debugSnapshot = null;
'''
if text.count(const_anchor) != 1:
    raise RuntimeError('index export button const anchor not found')
text = text.replace(const_anchor, const_repl, 1)

function_anchor = '''  function setMessage(text) {
'''
functions = r'''  function captureGameCanvas() {
    const source = document.querySelector('#embed-html canvas, canvas');
    if (!source || !source.width || !source.height) return null;
    const snap = document.createElement('canvas');
    snap.width = source.width;
    snap.height = source.height;
    const ctx = snap.getContext('2d', { alpha: false });
    ctx.drawImage(source, 0, 0, snap.width, snap.height);
    return snap;
  }

  function openDebugCapture() {
    const snap = captureGameCanvas();
    if (!snap) {
      alert('The game screen is not ready to capture yet.');
      return;
    }
    debugSnapshot = snap;
    debugPreview.src = snap.toDataURL('image/png');
    debugIssue.value = '';
    debugCapture.style.display = 'flex';
    requestAnimationFrame(() => debugIssue.focus());
  }

  function closeDebugCapture() {
    debugCapture.style.display = 'none';
    debugPreview.removeAttribute('src');
    debugSnapshot = null;
    const canvas = document.querySelector('#embed-html canvas, canvas');
    if (canvas) canvas.focus();
  }

  function wrapDebugText(ctx, text, maxWidth) {
    const words = text.split(/\s+/).filter(Boolean);
    const lines = [];
    let line = '';
    for (const word of words) {
      const next = line ? line + ' ' + word : word;
      if (line && ctx.measureText(next).width > maxWidth) {
        lines.push(line);
        line = word;
      } else {
        line = next;
      }
    }
    if (line) lines.push(line);
    return lines.length ? lines : ['(no issue text)'];
  }

  function canvasToBlob(canvas) {
    return new Promise((resolve, reject) => {
      canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('PNG capture failed')), 'image/png');
    });
  }

  async function copyDebugCapture() {
    if (!debugSnapshot) return;
    const issue = debugIssue.value.trim() || '(no issue text)';
    const meta = 'KQ1 DEBUG — ' + issue + '\n' + location.href + '\n' + new Date().toISOString();

    const output = document.createElement('canvas');
    const ctx = output.getContext('2d', { alpha: false });
    const fontSize = Math.max(18, Math.round(debugSnapshot.width / 48));
    ctx.font = '600 ' + fontSize + 'px system-ui, -apple-system, BlinkMacSystemFont, sans-serif';
    const padding = Math.max(16, Math.round(fontSize * .8));
    const lineHeight = Math.round(fontSize * 1.35);
    const lines = wrapDebugText(ctx, issue, debugSnapshot.width - padding * 2);
    const footerHeight = padding * 2 + lineHeight * (lines.length + 2);

    output.width = debugSnapshot.width;
    output.height = debugSnapshot.height + footerHeight;
    const out = output.getContext('2d', { alpha: false });
    out.drawImage(debugSnapshot, 0, 0);
    out.fillStyle = '#080808';
    out.fillRect(0, debugSnapshot.height, output.width, footerHeight);
    out.font = '700 ' + fontSize + 'px system-ui, -apple-system, BlinkMacSystemFont, sans-serif';
    out.fillStyle = '#ffffff';
    let y = debugSnapshot.height + padding + fontSize;
    out.fillText('ISSUE:', padding, y);
    y += lineHeight;
    out.font = '600 ' + fontSize + 'px system-ui, -apple-system, BlinkMacSystemFont, sans-serif';
    for (const line of lines) {
      out.fillText(line, padding, y);
      y += lineHeight;
    }
    out.font = '500 ' + Math.max(12, Math.round(fontSize * .7)) + 'px monospace';
    out.fillStyle = '#bdbdbd';
    out.fillText(location.href, padding, y);
    y += Math.round(lineHeight * .85);
    out.fillText(new Date().toISOString(), padding, y);

    const png = await canvasToBlob(output);
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

    closeDebugCapture();
    debugToast.style.display = 'block';
    clearTimeout(debugToast._timer);
    debugToast._timer = setTimeout(() => { debugToast.style.display = 'none'; }, 2200);
  }

  function setMessage(text) {
'''
if text.count(function_anchor) != 1:
    raise RuntimeError('index setMessage function anchor not found')
text = text.replace(function_anchor, functions, 1)

listener_anchor = '''  // MacBook-friendly shortcut. Tab is not a printable AGI parser character, so
'''
listener = r'''  // Fast debug capture: backtick, or Cmd/Ctrl+Shift+D. The event is consumed
  // before AGI sees it. Type one quick issue and press Enter; the clipboard gets
  // a screenshot with the issue visibly stamped underneath it.
  window.addEventListener('keydown', event => {
    if (debugCapture.style.display === 'flex') {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopImmediatePropagation();
        closeDebugCapture();
      } else if (event.key === 'Enter' && document.activeElement === debugIssue) {
        event.preventDefault();
        event.stopImmediatePropagation();
        copyDebugCapture().catch(error => {
          console.error(error);
          alert('Could not copy the debug capture: ' + error.message);
        });
      }
      return;
    }

    const backtick = event.key === '`' && !event.metaKey && !event.ctrlKey && !event.altKey;
    const chord = (event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 'd';
    if ((!backtick && !chord) || event.repeat) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openDebugCapture();
  }, true);

  debugCapture.addEventListener('mousedown', event => {
    if (event.target === debugCapture) {
      event.preventDefault();
      closeDebugCapture();
    }
  });
  debugIssue.addEventListener('keydown', event => event.stopPropagation());
  debugIssue.addEventListener('keyup', event => event.stopPropagation());

  // MacBook-friendly shortcut. Tab is not a printable AGI parser character, so
'''
if text.count(listener_anchor) != 1:
    raise RuntimeError('index Tab shortcut anchor not found')
text = text.replace(listener_anchor, listener, 1)

path.write_text(text)
print('Browser debug capture installed: ` or Cmd/Ctrl+Shift+D, Enter copies screenshot + stamped issue')
