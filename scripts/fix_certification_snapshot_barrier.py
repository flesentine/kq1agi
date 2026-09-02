#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_certification_snapshot_barrier.py /path/to/instrumented-agile-gdx')

root = Path(sys.argv[1]).resolve()
worker = root / 'html/src/main/java/com/agifans/agile/worker/AgileWebWorker.java'
interpreter = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
if not worker.exists():
    raise RuntimeError(f'missing generated certification worker: {worker}')
if not interpreter.exists():
    raise RuntimeError(f'missing generated certification interpreter: {interpreter}')

text = worker.read_text()

# The host needs two extra Uint32 slots for a request/ack epoch handshake.
old_size = '                if (certificationDigestBytes >= 32 && (certificationDigestBytes & 3) == 0)\n'
new_size = '                if (certificationDigestBytes >= 40 && (certificationDigestBytes & 3) == 0)\n'
if text.count(old_size) != 1:
    raise RuntimeError(f'certification digest size gate: expected 1 match, found {text.count(old_size)}')
text = text.replace(old_size, new_size, 1)

# While idle, the worker cannot service normal postMessage callbacks because AGILE's
# worker deliberately busy-waits on the shared IN_TICK flag. Poll the snapshot request
# from the shared digest instead, republish at that common barrier, then post an ack.
pattern = re.compile(r'(while \(variableData\.getInTick\(\) == false\) \{\n)')
text, count = pattern.subn(r'\1                publishCertificationSnapshotIfRequested();\n', text, count=1)
if count != 1:
    raise RuntimeError(f'certification idle snapshot poll: expected 1 match, found {count}')

anchor = '''    private void publishDiagnosticTrace() {\n'''
method = r'''    private void publishCertificationSnapshotIfRequested() {
        if (!certificationMode || certificationDigest == null || interpreter == null) return;
        int request = certificationDigest.get(8);
        int acknowledgement = certificationDigest.get(9);
        if (request == 0 || request == acknowledgement) return;

        // Republish only after both hosts have reached the same idle barrier. The
        // shared logical clock may have advanced after this lane finished its cycle.
        publishDiagnosticTrace();
        certificationDigest.set(9, request);

        // postMessage ordering guarantees any earlier sound events from this worker
        // are delivered before the host observes this barrier acknowledgement.
        postObject("CertificationSnapshotReady", createCertificationSnapshotReadyObject(request));
    }

    private native JavaScriptObject createCertificationSnapshotReadyObject(int epoch)/*-{
        return { epoch: epoch >>> 0 };
    }-*/;

'''
if text.count(anchor) != 1:
    raise RuntimeError(f'certification snapshot method insertion: expected 1 anchor, found {text.count(anchor)}')
text = text.replace(anchor, method + anchor, 1)
worker.write_text(text)

# HashMap iteration order is not semantic state. Canonicalize controller mappings by
# key so two lanes with the same mappings cannot false-diverge merely because entries
# were inserted in a different order.
itext = interpreter.read_text()
old_map_digest = r'''                hash = certificationMix(hash, state.keyToControllerMap.size());
                for (java.util.Map.Entry<Integer, Integer> entry : state.keyToControllerMap.entrySet()) {
                    hash = certificationMix(hash, entry.getKey());
                    hash = certificationMix(hash, entry.getValue());
                }
'''
new_map_digest = r'''                hash = certificationMix(hash, state.keyToControllerMap.size());
                java.util.ArrayList<Integer> certificationControllerKeys = new java.util.ArrayList<Integer>();
                certificationControllerKeys.addAll(state.keyToControllerMap.keySet());
                java.util.Collections.sort(certificationControllerKeys);
                for (Integer key : certificationControllerKeys) {
                    hash = certificationMix(hash, key);
                    hash = certificationMix(hash, state.keyToControllerMap.get(key));
                }
'''
if itext.count(old_map_digest) != 1:
    raise RuntimeError(f'certification controller-map digest: expected 1 match, found {itext.count(old_map_digest)}')
itext = itext.replace(old_map_digest, new_map_digest, 1)
interpreter.write_text(itext)

print('Certification snapshot barrier installed: common-clock republish + ordered acknowledgement + canonical map digest')