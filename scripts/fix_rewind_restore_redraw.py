#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_rewind_restore_redraw.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
commands = root / 'core/src/main/java/com/agifans/agile/Commands.java'
text = commands.read_text()

old = '''    public boolean restoreRewindState(int slot) {
        return savedGames.restoreRewindState(slot);
    }
'''

new = '''    public boolean restoreRewindState(int slot) {
        if (!savedGames.restoreRewindState(slot)) return false;

        // A normal AGI restore.game does more than deserialize state. It resets
        // sound/menu state, replays the room script events, redraws the picture,
        // and refreshes the status line. Rewind must do the same or the modern
        // replacement background's alpha-mask backing buffer is left stale,
        // producing the black/cut-out screen seen after Shift+Left.
        soundPlayer.reset();
        menu.enableAllMenus();
        replayScriptEvents();
        showPicture(false);
        textGraphics.updateStatusLine();
        return true;
    }
'''

if text.count(old) != 1:
    raise RuntimeError(
        'Commands restoreRewindState anchor expected once, found %d' % text.count(old)
    )

commands.write_text(text.replace(old, new, 1))
print('Rewind restore fixed: full AGI post-restore replay/redraw path now runs')
