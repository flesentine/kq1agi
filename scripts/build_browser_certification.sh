#!/usr/bin/env bash
set -euo pipefail

PINNED_AGILE_SHA="81c42ba63b3b7f5fb260d282592681c097d46da9"
PRODUCTION_TREE="${1:-agile-gdx}"
TRUTH_TREE="agile-gdx-cert-truth"
EDITED_TREE="agile-gdx-cert-edited"
OUT="certification-browser-artifact"

if [[ ! -d "$PRODUCTION_TREE/.git" ]]; then
  echo "ERROR: patched production AGILE tree not found: $PRODUCTION_TREE" >&2
  exit 1
fi

rm -rf "$TRUTH_TREE" "$EDITED_TREE" "$OUT"

node scripts/test_certification_host.mjs
node scripts/test_certification_panel.mjs
node scripts/test_certification_edit_config.mjs

git clone --quiet https://github.com/lanceewing/agile-gdx.git "$TRUTH_TREE"
git -C "$TRUTH_TREE" checkout --quiet "$PINNED_AGILE_SHA"
test "$(git -C "$TRUTH_TREE" rev-parse HEAD)" = "$PINNED_AGILE_SHA"

# The edited certification lane starts from the exact already-patched source tree
# used by this Pages build, before certification-only instrumentation is applied.
cp -a "$PRODUCTION_TREE" "$EDITED_TREE"

for dir in "$TRUTH_TREE" "$EDITED_TREE"; do
  python3 scripts/instrument_truth_worker.py "$dir"
  python3 scripts/instrument_certification_runtime.py "$dir"
  python3 scripts/fix_certification_gwt_compat.py "$dir"
  python3 scripts/fix_certification_snapshot_barrier.py "$dir"
  python3 scripts/fix_certification_browser_worker_path.py "$dir"
  git -C "$dir" diff --check
  chmod +x "$dir/gradlew"
done

mkdir -p "$OUT"
python3 scripts/check_certification_runtime.py "$TRUTH_TREE" "$EDITED_TREE" "$OUT/certification-runtime-report.json"

(
  cd "$TRUTH_TREE"
  ./gradlew html:dist --no-daemon
)
(
  cd "$EDITED_TREE"
  ./gradlew html:dist --no-daemon
)

for dir in "$TRUTH_TREE" "$EDITED_TREE"; do
  test -f "$dir/html/build/dist/worker/worker.nocache.js"
  test -f "$dir/html/build/dist/opfs-saved-games.js"
  grep -R -q 'diagnosticTraceSAB' "$dir/html/build/dist/worker"
  grep -R -q 'certificationDigestSAB' "$dir/html/build/dist/worker"
  grep -R -q 'CertificationReady' "$dir/html/build/dist/worker"
  grep -R -q 'CertificationSnapshotReady' "$dir/html/build/dist/worker"
  grep -R -q "importScripts(\['../opfs-saved-games.js'\])" "$dir/html/build/dist/worker"
done
cmp "$TRUTH_TREE/html/build/dist/opfs-saved-games.js" "$EDITED_TREE/html/build/dist/opfs-saved-games.js"

mkdir -p "$OUT/truth-worker" "$OUT/edited-worker"
cp -R "$TRUTH_TREE/html/build/dist/worker/." "$OUT/truth-worker/"
cp -R "$EDITED_TREE/html/build/dist/worker/." "$OUT/edited-worker/"
cp "$TRUTH_TREE/html/build/dist/opfs-saved-games.js" "$OUT/opfs-saved-games.js"
cp web/certification-host.mjs "$OUT/certification-host.mjs"
cp web/certification-panel.mjs "$OUT/certification-panel.mjs"
cp web/certification-edit-config.mjs "$OUT/certification-edit-config.mjs"
cp docs/TRUTH_ENGINE_PHASE_1C.md "$OUT/README.md"

printf '%s\n' \
  'Phase -1C browser bundle. No AGI game resources are included.' \
  'EditConfig v1 freezes persisted editor state plus the live current-room snapshot and applies it only to the edited lane.' \
  'The user-selected GAMEFILES.DAT is read later from same-origin OPFS in the browser.' \
  > "$OUT/ARTIFACT.txt"

find "$OUT" -maxdepth 2 -type f | sort
