#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: instrument_phase1d_certification_replay.py /path/to/certification-agile-gdx')

root = Path(sys.argv[1]).resolve()


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    return text.replace(old, new, 1)

# Both certification lanes need the same bounded-RNG hook. The edited lane may
# already contain it because it is copied from the normal Phase -1D PLAY build.
p = root / 'core/src/main/java/com/agifans/agile/GameState.java'
t = p.read_text()
if 'interface RandomEventSink' not in t:
    t = one(t,
'''    public Random random = new Random();
''',
'''    public Random random = new Random();

    /** Optional bounded-RNG observer/replay hook. */
    public interface RandomEventSink {
        void onRandom(int bound, int value, int totalTick);
    }

    private RandomEventSink randomEventSink;

    public void setRandomEventSink(RandomEventSink sink) {
        randomEventSink = sink;
    }

    public int nextRandomInt(int bound) {
        int value = random.nextInt(bound);
        if (randomEventSink != null) randomEventSink.onRandom(bound, value, getTotalTicks());
        return value;
    }
''', 'cert GameState random hook')
p.write_text(t)

for rel, replacements in [
    ('core/src/main/java/com/agifans/agile/AnimatedObject.java', [
        ('state.random.nextInt(9)', 'state.nextRandomInt(9)', 'cert wander direction RNG'),
        ('state.random.nextInt((Defines.MAXDIST - Defines.MINDIST))',
         'state.nextRandomInt((Defines.MAXDIST - Defines.MINDIST))', 'cert wander distance RNG'),
    ]),
    ('core/src/main/java/com/agifans/agile/Commands.java', [
        ('state.random.nextInt(255)', 'state.nextRandomInt(255)', 'cert AGI random command RNG'),
    ]),
]:
    p = root / rel
    t = p.read_text()
    for old, new, label in replacements:
        if old in t:
            t = one(t, old, new, label)
        elif new not in t:
            raise RuntimeError(f'{label}: neither original nor instrumented call found')
    p.write_text(t)

# Recorded values replace Random.nextInt(bound) without changing the rest of the
# interpreter. A mismatch is a replay-contract failure, not a silently invented RNG.
replay_java = root / 'core/src/main/java/com/agifans/agile/CertificationReplayRandom.java'
replay_java.write_text(r'''package com.agifans.agile;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/** Exact bounded random stream captured from normal PLAY for Phase -1D replay. */
public class CertificationReplayRandom extends Random {
    private static final long serialVersionUID = 1L;

    private final List<Integer> bounds = new ArrayList<Integer>();
    private final List<Integer> values = new ArrayList<Integer>();
    private int index;

    public CertificationReplayRandom(String spec) {
        super(0L);
        if (spec == null || !spec.startsWith("v1|")) {
            throw new IllegalArgumentException("Invalid Phase -1D random replay stream");
        }
        String body = spec.substring(3);
        if (body.length() == 0) return;
        String[] entries = body.split(";");
        for (String entry : entries) {
            String[] parts = entry.split(":");
            if (parts.length != 2) throw new IllegalArgumentException("Invalid random replay entry: " + entry);
            int bound = Integer.parseInt(parts[0]);
            int value = Integer.parseInt(parts[1]);
            if (bound <= 0 || value < 0 || value >= bound) {
                throw new IllegalArgumentException("Invalid random replay value " + value + " for bound " + bound);
            }
            bounds.add(bound);
            values.add(value);
        }
    }

    @Override
    public int nextInt(int bound) {
        if (index >= values.size()) {
            throw new IllegalStateException("Phase -1D random replay exhausted at draw " + index + " (bound " + bound + ")");
        }
        int expectedBound = bounds.get(index);
        int value = values.get(index);
        if (expectedBound != bound) {
            throw new IllegalStateException("Phase -1D random replay bound mismatch at draw " + index
                    + ": expected " + expectedBound + " got " + bound);
        }
        index++;
        return value;
    }

    public int getDrawCount() {
        return index;
    }

    public int getExpectedDrawCount() {
        return values.size();
    }
}
''')

p = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
t = p.read_text()
old = '''    public void configureCertification(int seed) {
        state.random = new CertificationRandom(((long)seed) & 0xFFFFFFFFL);
    }

    public int getCertificationRandomDrawCount() {
        return (state.random instanceof CertificationRandom)
                ? ((CertificationRandom)state.random).getDrawCount() : -1;
    }
'''
new = '''    public void configureCertification(int seed) {
        configureCertification(seed, "");
    }

    public void configureCertification(int seed, String replaySpec) {
        if (replaySpec != null && replaySpec.startsWith("v1|")) {
            state.random = new CertificationReplayRandom(replaySpec);
        } else {
            state.random = new CertificationRandom(((long)seed) & 0xFFFFFFFFL);
        }
    }

    public int getCertificationRandomDrawCount() {
        if (state.random instanceof CertificationReplayRandom)
            return ((CertificationReplayRandom)state.random).getDrawCount();
        return (state.random instanceof CertificationRandom)
                ? ((CertificationRandom)state.random).getDrawCount() : -1;
    }
'''
if old not in t:
    if 'configureCertification(int seed, String replaySpec)' not in t:
        raise RuntimeError('Phase -1B configureCertification block not found')
else:
    t = one(t, old, new, 'Interpreter replay RNG configuration')
p.write_text(t)

p = root / 'html/src/main/java/com/agifans/agile/worker/AgileWebWorker.java'
t = p.read_text()
if 'private String certificationRandomReplay;' not in t:
    t = one(t,
'''    private boolean certificationMode;
    private int certificationSeed;
''',
'''    private boolean certificationMode;
    private int certificationSeed;
    private String certificationRandomReplay;
''', 'worker replay field')
if 'certificationRandomReplay = getOptionalNestedString' not in t:
    t = one(t,
'''                certificationMode = getOptionalNestedBoolean(eventObject, "certificationMode");
                certificationSeed = getOptionalNestedInt(eventObject, "certificationSeed");
''',
'''                certificationMode = getOptionalNestedBoolean(eventObject, "certificationMode");
                certificationSeed = getOptionalNestedInt(eventObject, "certificationSeed");
                certificationRandomReplay = getOptionalNestedString(eventObject, "certificationRandomReplay");
''', 'worker replay initialise')
if 'interpreter.configureCertification(certificationSeed, certificationRandomReplay);' not in t:
    t = one(t,
            '                    interpreter.configureCertification(certificationSeed);\n',
            '                    interpreter.configureCertification(certificationSeed, certificationRandomReplay);\n',
            'worker replay configure call')
if 'private native String getOptionalNestedString' not in t:
    marker = '''    private native int getOptionalNestedInt(JavaScriptObject obj, String fieldName)/*-{
        var value = (obj && obj.object) ? obj.object[fieldName] : 0;
        return (typeof value === 'number') ? (value | 0) : 0;
    }-*/;
'''
    helper = marker + r'''

    private native String getOptionalNestedString(JavaScriptObject obj, String fieldName)/*-{
        var value = (obj && obj.object) ? obj.object[fieldName] : '';
        return (typeof value === 'string') ? value : '';
    }-*/;
'''
    if t.count(marker) != 1:
        raise RuntimeError('worker optional-int accessor not found')
    t = t.replace(marker, helper, 1)

# Edited certification sources contain the normal PLAY observer. It must not emit
# recording messages during certification; the replay stream is authoritative.
observer = '''                interpreter.setRandomEventSink(new GameState.RandomEventSink() {
                    @Override
                    public void onRandom(int bound, int value, int totalTick) {
                        postObject("RecordingRandomDraw", createRecordingRandomDraw(bound, value, totalTick));
                    }
                });
'''
if observer in t:
    t = t.replace(observer, '''                if (!certificationMode) {
                    interpreter.setRandomEventSink(new GameState.RandomEventSink() {
                        @Override
                        public void onRandom(int bound, int value, int totalTick) {
                            postObject("RecordingRandomDraw", createRecordingRandomDraw(bound, value, totalTick));
                        }
                    });
                }
''', 1)
p.write_text(t)

print('Phase -1D certification random replay installed')
