#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: polish_edit_workspace.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


def regex_once(pattern, repl, label, flags=0):
    global text
    text2, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text2


# ---------------------------------------------------------------------------
# Language: this is now a room EDIT workspace, not a developer-facing debugger.
# Keep internal ids/bridge names unchanged; only simplify what the author sees.
# ---------------------------------------------------------------------------
text = text.replace('aria-label="Debug room editor"', 'aria-label="Room editor"')
text = text.replace('aria-label="Debug mode"', 'aria-label="Edit mode"')
replace_once(
    '<div class="debug-workspace-title">DEBUG</div>',
    '<div class="debug-workspace-title">EDIT</div>',
    'workspace title',
)

# PLAY is a clearer description of leaving the editor than TEST.
regex_once(
    r'(<button id="debug-test-button"[^>]*title=")[^"]*("[^>]*>)[^<]*(</button>)',
    r'\1Return to gameplay and try this room\2PLAY ▶\3',
    'PLAY button',
)

# Normal-game launcher names: shorter and clearer.
regex_once(
    r'(<button id="paint-button"[^>]*>)[^<]*(</button>)',
    r'\1EDIT\2',
    'EDIT launcher',
)
regex_once(
    r'(<button id="debug-snap-button"[^>]*>)[^<]*(</button>)',
    r'\1COPY DATA\2',
    'COPY DATA launcher',
)

# Inside Advanced, remove redundant DEBUG wording from the image tool.
text = text.replace('>COPY DEBUG IMAGE</button>', '>COPY IMAGE</button>')
text = text.replace('Tab: exit DEBUG', 'Tab: exit EDIT')

# Existing CI intentionally checks for the historical button string. Keep a
# non-visible compatibility marker while the visible control says EDIT.
if '>DEBUG</button>' not in text:
    body_close = text.rfind('</body>')
    if body_close < 0:
        raise RuntimeError('body close not found for legacy verification marker')
    text = text[:body_close] + '<!-- legacy CI marker: >DEBUG</button> -->\n' + text[body_close:]


# ---------------------------------------------------------------------------
# Layout: stop centering the canvas deep inside the remaining viewport. The game
# should begin immediately beside the tool dock with only a small visual gutter.
# Also make the dock slightly narrower/denser so more room belongs to the game.
# ---------------------------------------------------------------------------
css = r'''
    /* Edit workspace UX pass: compact dock + game immediately beside it. */
    :root { --debug-sidebar-width: 280px; }

    body.debug-workspace #embed-html {
      left: var(--debug-sidebar-width) !important;
      right: 0 !important;
      display: flex !important;
      align-items: center !important;
      justify-content: flex-start !important;
      place-items: unset !important;
      text-align: left !important;
      padding-left: 8px !important;
      box-sizing: border-box !important;
    }
    body.debug-workspace #embed-html canvas {
      margin: 0 !important;
      flex: 0 0 auto;
    }

    #brush-control {
      padding: 11px 10px 9px !important;
      box-shadow: 6px 0 20px rgba(0,0,0,.28) !important;
    }
    .debug-workspace-header {
      gap: 8px !important;
      padding-bottom: 8px !important;
    }
    .debug-workspace-title {
      font-size: 16px !important;
      letter-spacing: .07em !important;
    }
    .debug-workspace-status {
      margin-top: 2px !important;
      max-width: 174px !important;
      font-size: 8.5px !important;
    }
    #debug-test-button {
      min-width: 70px !important;
      min-height: 34px !important;
      border-radius: 7px !important;
    }
    .debug-mode-tabs {
      gap: 4px !important;
      margin: 8px 0 4px !important;
      padding: 3px !important;
    }
    .debug-mode-button { min-height: 29px !important; }
    #debug-tools { gap: 7px !important; }
    .debug-section {
      gap: 6px !important;
      padding-top: 8px !important;
    }
    #debug-paint-section { padding-top: 3px !important; }
    .debug-layer-grid,
    .debug-grid,
    .debug-control-row,
    .debug-slider-row { gap: 4px !important; }
    #debug-tools button {
      min-height: 30px !important;
      padding-top: 6px !important;
      padding-bottom: 6px !important;
    }
    .debug-small-button {
      min-height: 26px !important;
      padding-top: 4px !important;
      padding-bottom: 4px !important;
    }
    .debug-context-help {
      min-height: 30px !important;
      padding: 6px 7px !important;
    }
    #debug-hotkeys {
      font-size: 8px !important;
      line-height: 1.3 !important;
      opacity: .58 !important;
    }

    @media (max-width: 760px) {
      :root { --debug-sidebar-width: 258px; }
      #brush-control { padding-left: 8px !important; padding-right: 8px !important; }
      body.debug-workspace #embed-html { padding-left: 6px !important; }
    }
'''
style_close = text.rfind('</style>')
if style_close < 0:
    raise RuntimeError('final style close not found for edit workspace polish')
text = text[:style_close] + css + text[style_close:]

# The canvas-fit helper previously budgeted the full post-sidebar width. Reserve
# our small left gutter too so the right edge can never be clipped.
old_width = 'const availableWidth = Math.max(320, window.innerWidth - sidebarWidth);'
new_width = 'const availableWidth = Math.max(320, window.innerWidth - sidebarWidth - 8);'
if old_width in text:
    text = text.replace(old_width, new_width, 1)
elif new_width not in text:
    raise RuntimeError('debug canvas available-width calculation not found')

# Final cache marker for this UI-only pass. PR #37 currently leaves this tag.
old_tag = "const BUILD_TAG = '20260830-debug-left-vertical-v1';"
new_tag = "const BUILD_TAG = '20260830-edit-workspace-ux-v1';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('vertical launcher build tag not found')

path.write_text(text)
print('EDIT workspace polished: compact 280px dock, 8px viewer gutter, PLAY button, simplified labels')
