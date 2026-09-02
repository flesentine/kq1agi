#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_certification.py /path/to/index.html')

path = Path(sys.argv[1])
html = path.read_text()

if 'id="certify-button"' in html or 'certification/certification-panel.mjs' in html:
    raise RuntimeError('CERTIFY browser integration is already present')

for anchor, label in [
    ('</style>', 'style close'),
    ('<div id="boot-message">', 'boot message'),
    ('</body>', 'body close'),
]:
    if html.count(anchor) != 1:
        raise RuntimeError(f'CERTIFY {label}: expected exactly one anchor, found {html.count(anchor)}')

css = r'''
    #certify-button {
      position: fixed; top: 14px; left: 14px; z-index: 10003; display: none;
      padding: 9px 13px; border: 2px solid #7fffb0; border-radius: 8px;
      background: rgba(7, 28, 18, .92); color: #b8ffd0;
      font: 800 13px system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      letter-spacing: .05em; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,.45);
    }
    #certify-button:hover { background: rgba(17, 58, 36, .96); }
    #certify-panel {
      position: fixed; top: 58px; left: 14px; z-index: 10004; width: min(430px, calc(100vw - 28px));
      max-height: calc(100vh - 72px); overflow: auto; box-sizing: border-box;
      padding: 14px; border: 1px solid rgba(127,255,176,.65); border-radius: 10px;
      background: rgba(5, 10, 8, .96); color: #e7ffee;
      font: 13px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      box-shadow: 0 8px 30px rgba(0,0,0,.6);
    }
    #certify-panel[aria-hidden="true"] { display: none; }
    #certify-panel header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
    #certify-panel h2 { margin: 0; flex: 1; font: 800 14px system-ui, sans-serif; letter-spacing: .06em; }
    #certify-panel button, #certify-panel select, #certify-panel input {
      box-sizing: border-box; border: 1px solid #456252; border-radius: 6px;
      background: #0f1813; color: #effff4; font: inherit; padding: 7px 8px;
    }
    #certify-panel button { cursor: pointer; font-weight: 700; }
    #certify-panel button:disabled { opacity: .45; cursor: default; }
    #certify-panel label { display: grid; gap: 4px; margin: 8px 0; color: #b8c9be; }
    #certify-actions { display: flex; gap: 7px; flex-wrap: wrap; margin: 10px 0; }
    #certify-status { display: inline-block; margin: 4px 0 8px; padding: 5px 8px; border-radius: 999px; background: #1a211d; font-weight: 800; }
    #certify-status[data-state="MATCH"], #certify-status[data-state="READY"] { background: #103a22; color: #9dffbd; }
    #certify-status[data-state="DIVERGED"], #certify-status[data-state="ERROR"] { background: #4a1717; color: #ffb3b3; }
    #certify-status[data-state="BUSY"], #certify-status[data-state="WAITING"] { background: #43350e; color: #ffe59a; }
    #certify-progress { color: #b8c9be; margin-bottom: 8px; }
    #certify-detail { margin: 0; padding: 9px; white-space: pre-wrap; overflow-wrap: anywhere; background: #070b09; border-radius: 6px; color: #d7e7dc; }
    #certify-privacy { color: #8fa99a; font: 11px/1.35 system-ui, sans-serif; margin: 8px 0 0; }
'''
html = html.replace('</style>', css + '</style>', 1)

panel = r'''<button id="certify-button" type="button" title="Open deterministic ORIGINAL-vs-EDITED certification">CERTIFY</button>
<aside id="certify-panel" aria-hidden="true" aria-label="Truth engine certification">
  <header>
    <h2>ORIGINAL vs EDITED · CERTIFY</h2>
    <button id="certify-close-button" type="button" title="Close certification panel">×</button>
  </header>
  <label>Local imported game
    <select id="certify-game-select"><option>Scanning…</option></select>
  </label>
  <label>Shared barriers to certify
    <input id="certify-barrier-count" type="number" min="1" max="1000" step="1" value="60">
  </label>
  <div id="certify-actions">
    <button id="certify-refresh-button" type="button">REFRESH</button>
    <button id="certify-run-button" type="button">RUN</button>
    <button id="certify-stop-button" type="button" disabled>STOP</button>
  </div>
  <div id="certify-status" data-state="IDLE">IDLE</div>
  <div id="certify-progress">0 certified barriers</div>
  <pre id="certify-detail">Open CERTIFY after your own King’s Quest import has launched.</pre>
  <p id="certify-privacy">Local-only: reads AGILE’s same-origin OPFS GAMEFILES.DAT and copies it into isolated truth/edited workers. No game data is uploaded.</p>
</aside>
'''
html = html.replace('<div id="boot-message">', panel + '<div id="boot-message">', 1)
html = html.replace('</body>', '<script type="module" src="certification/certification-panel.mjs"></script>\n</body>', 1)

for marker in [
    '#certify-button {',
    'id="certify-button"',
    'id="certify-panel"',
    'certification/certification-panel.mjs',
]:
    if marker not in html:
        raise RuntimeError(f'CERTIFY injection failed to produce marker: {marker}')

path.write_text(html)
print('Phase -1C CERTIFY panel injected')
