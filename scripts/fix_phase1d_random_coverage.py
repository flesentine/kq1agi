#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_phase1d_random_coverage.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
animated = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
commands = root / 'core/src/main/java/com/agifans/agile/Commands.java'

if not animated.exists() or not commands.exists():
    raise RuntimeError('AGILE source tree is incomplete')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f'{label}: expected 1 original call, found {count}')
        return text.replace(old, new, 1)
    if new not in text:
        raise RuntimeError(f'{label}: neither original nor instrumented call found')
    return text


text = animated.read_text()
for old, new, label in [
    ('state.random.nextInt(8)', 'state.nextRandomInt(8)', 'follow direction RNG'),
    ('state.random.nextInt((maxDist - this.stepSize))',
     'state.nextRandomInt((maxDist - this.stepSize))', 'follow distance RNG'),
]:
    text = replace_once(text, old, new, label)
animated.write_text(text)

# The pinned AGILE runtime has four bounded random call sites in AnimatedObject
# (two wander + two follow) and one AGI random command call in Commands. Phase -1D
# must observe/replay every one of them; an uncovered call would make the captured
# random stream incomplete while still looking deterministic.
animated_text = animated.read_text()
commands_text = commands.read_text()
if 'state.random.nextInt(' in animated_text or 'state.random.nextInt(' in commands_text:
    raise RuntimeError('Phase -1D RNG coverage incomplete: direct state.random.nextInt call remains')
if animated_text.count('state.nextRandomInt(') != 4:
    raise RuntimeError(
        f'Phase -1D AnimatedObject RNG coverage: expected 4 wrapped calls, found '
        f'{animated_text.count("state.nextRandomInt(")}'
    )
if commands_text.count('state.nextRandomInt(255)') != 1:
    raise RuntimeError('Phase -1D Commands RNG coverage: expected exactly one wrapped random command')

print('Phase -1D bounded RNG coverage verified: 5/5 runtime call sites wrapped')
