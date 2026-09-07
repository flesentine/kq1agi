# Truth Engine — Phase -1I Checkpoint-Started Replay

Phase -1I begins consuming the exact fresh-worker checkpoint/restore substrate merged in Phase -1H.

This first slice is deliberately narrow. It does **not** accelerate Phase -1E/-1F/-1G minimization yet. It adds a replay-session cursor that can pause at an authoritative recorded boundary, capture a Phase -1H checkpoint, restore that checkpoint into fresh workers, and consume only the remaining authenticated suffix.

## Safety boundary

A Phase -1H checkpoint is exact interpreter state, but exact state alone does not prove where a replay driver may resume its transport schedule.

Phase -1I.0 therefore permits checkpoint capture only immediately **before a recorded cycle-release tick**:

1. the frozen Phase -1D recording says the previous interpreter cycle completed before release tick `T`;
2. replay settles and compares that completed cycle at logical tick `T-1`;
3. no release or transport for tick `T` has been applied yet;
4. the replay returns `REPLAY_PAUSED`; and
5. the caller may invoke `captureCheckpointProbe()` at that exact state.

A restored checkpoint is accepted as a replay cursor only when `checkpoint.logicalTick + 1` is a recorded release tick in the same authenticated recording.

A second cold-browser review exposed an additional hidden-state requirement: after a valid Phase -1H restore, AGILE could leave `currentPicture` absent even though semantic-v1 and the visible framebuffer were exact. That made the resumed worker unable to capture a second checkpoint. The Phase -1I hardening therefore upgrades the worker payload to KQ1H v2 and preserves the exact current-picture visual/priority drawing context and pen/colour state. Restored replay sessions must remain checkpointable again.

This avoids inventing an arbitrary idle state, avoids replaying same-tick transport twice, and preserves checkpoint chaining.

## Replay API

`runCertificationReplaySession(host, recording, options)` remains from-start by default.

Phase -1I.0 adds two opt-in options:

- `pauseBeforeTick`: pause only before a recorded release tick after the prior cycle has been authoritatively settled;
- `checkpoint`: restore a Phase -1H checkpoint first, verify `CHECKPOINT_ROUNDTRIP_MATCH`, verify the replay cursor boundary, and then consume only ticks after `checkpoint.logicalTick`.

A successful suffix replay reports:

- `replayStartTick`;
- `skippedPrefixTicks`; and
- `consumedTicks` for work actually executed after restore.

From-start callers continue to report a replay start tick of zero.

## Phase -1H remains authoritative

Phase -1I does not bypass or weaken Phase -1H authentication.

Before any suffix pulse:

- the full Phase -1D recording hash is verified;
- the ReplayCertificationHost still binds the actual GAMEFILES identity, EditConfig hash, recording hash, exact RNG replay spec, and recorded-external-timing mode;
- `restoreCheckpointProbe()` verifies the checkpoint SHA-256 and frozen context;
- restore must return `CHECKPOINT_ROUNDTRIP_MATCH`; and
- the restored logical tick must equal the checkpoint tick.

Hash mismatch, context mismatch, inexact restore, invalid checkpoint tick, or invalid resume boundary returns `REPLAY_CONTRACT_MISS` before the suffix is consumed.

## Why minimizers are not wired yet

Phase -1E prefix candidates and Phase -1F input candidates receive new recording hashes. Phase -1G candidates also receive new EditConfig hashes.

A checkpoint captured under the original replay context is therefore **supposed** to reject those candidates today.

The next Phase -1I slice must define a dependency-safe checkpoint rebinding rule. It may only rebind a checkpoint to a candidate after proving that every candidate-visible change occurs strictly after the checkpoint and therefore cannot alter the captured prefix state. Phase -1G requires additional care because an EditConfig change can affect execution from game start.

Until that proof exists, minimizer candidate runners stay on the full replay oracle.

## Acceptance criteria

- Existing from-start replay behavior remains the default.
- Pause is accepted only before a recorded release tick.
- The pause happens after the prior cycle is settled and before the target tick release/transport is applied.
- A restored checkpoint must pass the complete Phase -1H hash/context/exactness gate.
- A restored checkpoint must resume immediately before a recorded release tick.
- Events at `checkpoint.logicalTick` are not applied again.
- Rejected checkpoint restore or cursor validation consumes zero suffix pulses.
- A checkpoint-started replay reaches the same final state/result as the equivalent full replay.
- A resumed replay can pause at a later recorded release boundary, capture a second checkpoint, restore that second checkpoint into fresh workers, and still reproduce the same final state.
- Replay summaries expose skipped-prefix and consumed-suffix tick counts.
- Phase -1E/-1F/-1G candidate execution remains unchanged in this slice.

## Next slice

Add an explicit candidate/checkpoint compatibility proof and authenticated checkpoint-context rebinding for recording-only changes that are provably after the checkpoint. Gate every accelerated candidate against the existing full-from-start replay oracle before allowing minimizers to use the shortcut by default.


## Phase -1I.1 — candidate compatibility and authenticated rebinding

Phase -1I.1 adds the proof layer required before minimizers may reuse a checkpoint captured under another recording hash.

A checkpoint is eligible for a recording-only candidate only when all of the following hold:

1. the source checkpoint SHA-256 is valid;
2. the source and candidate Phase -1D recording hashes are independently valid;
3. the checkpoint context names the exact source recording and source RNG replay specification;
4. GAMEFILES hash/byte length are unchanged;
5. EditConfig hash is unchanged;
6. both recordings still begin at logical tick 1 and are not overflowed;
7. the checkpoint was captured under recorded-external-timing mode;
8. both source and candidate continue past the checkpoint;
9. `checkpoint.logicalTick + 1` remains a recorded cycle-release boundary; and
10. the canonical replay authority through `checkpoint.logicalTick` is exactly equal:
   - all release ticks through the checkpoint,
   - all transport events through the checkpoint, including seq/tick/phase/payload,
   - all RNG observations through the checkpoint, and
   - the frozen game/EditConfig identity fields; and
11. the checkpoint's authenticated truth/edited RNG draw counts agree, and the first N source/candidate RNG observations are exactly equal, where N is that consumed draw count.

Only after that proof may the checkpoint context be rebound. Rebinding is deliberately narrow:

- `recordingHash` changes to the candidate recording hash;
- `randomReplaySpec` changes to the candidate's full authenticated RNG stream;
- seed, GAMEFILES identity, EditConfig identity, and recorded-external-timing mode remain exactly frozen; and
- the complete checkpoint is SHA-256 authenticated again after the context change.

This permits suffix-only recording changes, including a shorter Phase -1E prefix or Phase -1F input removal after the checkpoint, while refusing any change that could have affected the captured state.

Phase -1G is still ineligible. A different EditConfig hash can alter execution from tick 1, so Phase -1I.1 never rebinds EditConfig identity.

The compatibility proof also emits a deterministic `compatibilityKey` containing the original checkpoint hash, candidate recording hash, and checkpoint tick. This is the minimum identity future accelerated-candidate caches must include.

### Phase -1I.1 acceptance criteria

- A suffix-only input change after the checkpoint is compatible.
- A suffix-only RNG-stream change after the checkpoint is compatible and rebinds the full candidate RNG replay specification.
- RNG compatibility is additionally bound to the checkpoint's authenticated consumed-draw count; changing any of the first N consumed draws is rejected even if tick metadata is misleading.
- Any transport or RNG change through the checkpoint is rejected.
- Removing the checkpoint's next release boundary is rejected.
- A source or candidate ending at or before the checkpoint is rejected.
- A checkpoint not captured under recorded-external-timing mode is rejected.
- GAMEFILES changes are rejected.
- EditConfig changes are rejected.
- A tampered checkpoint is rejected before compatibility reasoning.
- A checkpoint whose context does not name the exact source recording/RNG stream is rejected.
- Successful rebinding changes only recording/RNG identity and produces a new valid checkpoint SHA-256.

Minimizer execution remains on the from-start oracle until the next slice adds candidate-level equivalence gating around this proof.


## Phase -1I.2 — shadow oracle-gated candidate replay

Phase -1I.2 adds a reusable shadow runner around the Phase -1I.1 compatibility/rebinding proof.

The full from-start replay remains authoritative in every case. The checkpoint path is experimental evidence only.

For each candidate:

1. run the candidate from logical tick 1 using the existing replay oracle, require its authenticated evidence context to name the candidate recording, and require replayStartTick = 0;
2. if that full replay does not end in a trusted terminal classification (`REPLAY_MATCH`, `DIVERGED`, or `COMPLETE`), return the full result without trying acceleration;
3. prove checkpoint/candidate compatibility with Phase -1I.1;
4. if incompatible, return the full result without trying acceleration;
5. re-authenticate the compatible checkpoint to the candidate recording/RNG identity;
6. run the candidate again from the rebound checkpoint, require its evidence context to name the same candidate recording, and require replayStartTick = checkpoint.logicalTick;
7. canonicalize both replay decisions while excluding non-semantic telemetry such as consumed-tick counts, replay-start tick, certified-barrier count, skipped-prefix count, and snapshot epoch;
8. require the canonical decisions to be exactly equal;
9. require exact terminal evidence equality for:
   - logical tick, cycle, and compared cycle,
   - ORIGINAL and EDITED diagnostic traces,
   - semantic-v1 digests including RNG draw position,
   - key queue, keys, old keys, and the complete shared variable transport,
   - framebuffer pixels,
   - exact per-lane KQ1H v2 serialized worker payloads, covering hidden reconstruction state such as current-picture drawing context,
   - quit/error state,
   - pending sound requests/completions, and
   - pending external divergence state; and
10. only then return `CHECKPOINT_ORACLE_EQUIVALENT`.

If the checkpoint path throws, omits evidence, disagrees on the replay decision, or differs in any terminal evidence field, the result is not trusted. The full replay classification remains authoritative and the runner reports either `CHECKPOINT_ORACLE_FULL_ONLY` or `CHECKPOINT_ORACLE_MISMATCH`.

The runner reports full and checkpoint consumed-tick telemetry plus `savedTicks`, but those values are explicitly excluded from semantic equivalence.

### Phase -1I.2 acceptance criteria

- Compatible full/checkpoint runs with the same semantic outcome and exact terminal evidence return `CHECKPOINT_ORACLE_EQUIVALENT`.
- Different replay-start tick, consumed ticks, certified-barrier count, skipped-prefix count, and snapshot epoch do not create false mismatches.
- Full evidence bound to the wrong recording or a full replay that did not start at tick 0 is rejected as an oracle wiring error.
- A checkpoint run bound to the wrong recording or starting anywhere except the proven checkpoint tick is never trusted.
- A decision mismatch is rejected even if terminal evidence is otherwise equal.
- An evidence mismatch is rejected even if the replay decision is equal.
- Missing or incomplete full evidence prevents any checkpoint attempt and returns the full result only.
- Missing or incomplete checkpoint evidence is rejected.
- Oracle evidence capture must include both exact worker payloads; if either lane cannot serialize hidden state, acceleration is not trusted.
- A checkpoint replay exception falls back to the full result.
- A Phase -1I.1-incompatible candidate never attempts checkpoint replay.
- Full `REPLAY_CONTRACT_MISS`, `REPLAY_TIMING_MISS`, or `STOPPED` results remain full-only.
- The full replay result remains the authoritative candidate classification in every branch.
- Phase -1E/-1F/-1G minimizer call sites remain unchanged in this slice.

The next slice may wire Phase -1E/-1F candidate execution through this shadow runner to collect real minimizer-level equivalence evidence. It must not skip the full replay until a later policy freeze explicitly permits that optimization.


## Phase -1I.3 — minimizer-level shadow evidence

Phase -1I.3 wires the recording-only Phase -1E and Phase -1F candidate call sites through the Phase -1I.2 oracle in **shadow mode**.

This is still not an acceleration-policy change. Every minimizer candidate runs from logical tick 1 first, and that full replay remains the only classification returned to the minimizer. A checkpoint replay may add evidence and telemetry, but it cannot make a candidate reproduce, fail to reproduce, or otherwise change the reduction decision.

### Checkpoint selection and capture

Each minimizer stage captures at most one experimental source checkpoint:

1. take the stage's immutable source recording and exact target divergence tick;
2. consider only recorded release ticks from 2 through the target tick;
3. translate each release tick `T` to the authoritative pre-release checkpoint at `T-1`;
4. choose the candidate closest to the midpoint of the target tick, preferring the later checkpoint on an exact tie;
5. replay the exact source from start and pause at that recorded boundary; and
6. capture a normal Phase -1H checkpoint only if the source lanes are exact there.

The midpoint choice is deterministic. It deliberately balances skipped-prefix evidence against Phase -1F eligibility: removing an input before the checkpoint must make that candidate incompatible, while suffix-only removals can still exercise the checkpoint path.

Checkpoint capture is best-effort. No usable recorded boundary, a pause/capture failure, or a user stop leaves the minimizer on its existing full-replay path.

### Candidate execution

When a source checkpoint is available, each Phase -1E/-1F candidate does the following:

1. run the complete candidate from logical tick 1 and capture Phase -1I.2 terminal evidence;
2. pass that full run to `runCheckpointCandidateOracleV1`;
3. if Phase -1I.1 says the candidate prefix is compatible, rebind and run the checkpoint suffix in a fresh replay host;
4. compare decision and terminal evidence exactly under the Phase -1I.2 rules; and
5. return **only `oracle.authoritativeSummary`** to the minimizer.

The UI reports aggregate shadow evidence after the reduction: equivalent, full-only, and mismatch counts; checkpoint attempts and trusted checkpoints; measured saved ticks; and reason counts.

A `CHECKPOINT_ORACLE_MISMATCH` is therefore scientific evidence against a future shortcut policy, not a minimizer failure and never a replacement for the full result.

### Scope boundary

Phase -1G remains intentionally unchanged and full-replay-only. Its candidates change the EditConfig hash, which can change execution from logical tick 1 and is outside the recording-only Phase -1I.1 rebinding proof.

### Phase -1I.3 acceptance criteria

- Phase -1E and Phase -1F each capture at most one deterministic checkpoint from their own immutable source recording.
- Checkpoints are captured only at a recorded pre-release boundary before or at the target divergence.
- Every candidate still runs the full from-start replay first.
- The minimizer receives the full replay's authoritative summary even when the checkpoint shadow disagrees.
- A compatible candidate reaches `CHECKPOINT_ORACLE_EQUIVALENT` only after exact Phase -1I.2 decision and terminal-evidence equality.
- Prefix-changing Phase -1F candidates remain full-only and do not attempt a checkpoint suffix.
- Missing terminal evidence or unavailable checkpoint capture falls back to the full result without blocking reduction.
- Shadow telemetry is reported but is not semantic input to the minimizer.
- Phase -1G has no checkpoint capture, rebinding, or shadow-run call site.
- No policy is allowed to skip the full replay in this slice.

## Phase -1I.3 transition

The next slice is evidence collection, not policy activation. Full replay remains mandatory while the compatible population is measured and audited.

## Phase -1I.4 — compact minimizer evidence ledger

Phase -1I.4 turns the Phase -1I.3 shadow observations into an auditable evidence population without changing replay authority or enabling acceleration.

The scientific problem in Phase -1I.3 is that a useful shadow run naturally produces two large terminal snapshots for every compatible minimizer candidate: the full-run evidence and the checkpoint-run evidence. Retaining every raw oracle result for the lifetime of a long minimization can unnecessarily retain many copies of KQ1H v2 worker payloads. Phase -1I.4 therefore compacts each candidate immediately after the oracle comparison.

### Compact observation

For each Phase -1E/-1F candidate that enters the shadow oracle, the UI now derives a `kq1agi-minimizer-checkpoint-observation-v1` record before the next candidate starts. The observation keeps:

- the candidate recording hash;
- oracle status/reason and checkpoint attempted/trusted flags;
- full/checkpoint consumed-tick telemetry and measured saved ticks;
- compact checkpoint-compatibility identity;
- mismatch category plus the first differing evidence/decision path and reason;
- the authoritative result status/tick;
- SHA-256 fingerprints of the canonical full/checkpoint decisions; and
- SHA-256 fingerprints plus validation status for the full/checkpoint terminal evidence.

The raw `fullRun` / `acceleratedRun` evidence objects, including hidden worker payload arrays, are not retained in the minimizer evidence ledger. An exact Phase -1I.2 equivalence therefore leaves matching full/checkpoint decision and evidence fingerprints; a mismatch preserves the differing fingerprints and forensic difference path without keeping the large payloads alive.

This compaction is evidence-only. `shadow.summary` is still returned to the minimizer before the raw oracle result becomes unreachable, and that summary is still the full from-start authoritative result. Fingerprint/report generation is best-effort: a compaction failure records the affected candidate hash as a collection gap, and a report-generation failure disables that new report rather than changing the minimizer's replay classification.

### Stage and population identity

Each completed Phase -1E or Phase -1F execution produces a deterministic `kq1agi-minimizer-checkpoint-stage-evidence-v1` record containing:

- source recording/game/EditConfig identity and source sizes;
- exact target divergence tick;
- checkpoint selection/capture identity;
- stage outcome and attempt count;
- compact candidate observations; and
- the existing aggregate equivalent/full-only/mismatch telemetry.

A deterministic stage key is derived from stage name, source recording hash, target tick, and checkpoint identity. The exported report uses `stageKey + candidateRecordingHash` as the population sample identity. Re-running the same candidate under the same source/checkpoint therefore does not silently inflate the number of unique samples.

The report separately exposes:

- total observations;
- unique samples;
- duplicate observations and repeated samples; and
- **inconsistent repeated samples**, where the same sample identity produced different semantic fingerprints on different executions.

An inconsistent repeated sample is strong evidence against any later shortcut policy and must not be hidden by aggregate success counts.

### Exported evidence report

The certification panel exposes **EXPORT EVIDENCE** once at least one Phase -1E/-1F stage record exists. The deterministic JSON report uses schema `kq1agi-minimizer-checkpoint-evidence-report-v1`, carries its own SHA-256 hash, and is also published in-page as `globalThis.__kq1agiCheckpointShadowEvidenceReport` for browser automation/audit inspection.

The report deliberately declares:

- `policy: full-replay-authoritative`;
- `policyFrozen: false`; and
- `policyDecision: EVIDENCE_ONLY`.

No candidate can skip its full replay in Phase -1I.4. The report is an evidence collection surface, not an acceleration gate.

### Phase -1I.4 acceptance criteria

- Phase -1E and Phase -1F remain the only minimizer stages entering the recording-only checkpoint shadow path.
- Every shadow candidate still runs the full replay first and the minimizer still receives only the full authoritative summary.
- Raw oracle terminal worker payloads are not retained in the cross-candidate evidence array.
- Compact observations preserve deterministic SHA-256 decision/evidence fingerprints and mismatch paths.
- Evidence compaction/report failures cannot replace or block the minimizer's full authoritative result; collection gaps are surfaced separately.
- Exact equivalent observations have equal full/checkpoint semantic fingerprints at the decision/evidence level.
- Stage and report hashes are deterministic and contain no wall-clock/random identity.
- Repeated identical stage/candidate samples are counted separately as observations but only once as a unique population sample.
- Conflicting repeated outcomes are surfaced as inconsistent samples.
- Exported JSON contains no raw hidden worker payload arrays.
- Phase -1G remains full-replay-only and is excluded from the Phase -1I.4 checkpoint population.
- The evidence report explicitly states that no acceleration policy has been frozen.

## Phase -1I.5 — cross-session evidence corpus

Phase -1I.5 makes Phase -1I.4 evidence composable across independent browser sessions without turning evidence into policy.

A later Phase -1I.4 export can contain stage executions that appeared in an earlier export from the same browser session. Naively concatenating those files would therefore count the same execution more than once. Phase -1I.5 introduces a deterministic corpus format that validates the imported evidence chain, removes exact duplicate stage executions, preserves independent repeated executions, and recomputes the population from the validated stages.

### Import validation

The certification panel accepts one or more Phase -1I.4 report JSON files or previously exported Phase -1I.5 corpus files.

Before imported evidence enters the corpus, Phase -1I.5 verifies:

- the evidence-only policy declaration is still exactly `full-replay-authoritative`, `policyFrozen=false`, `policyDecision=EVIDENCE_ONLY`;
- every compact observation uses the expected schema and oracle status;
- equivalent observations are attempted/trusted and have matching full/checkpoint decision and evidence SHA-256 fingerprints;
- mismatch observations are attempted/untrusted and retain a failed comparison;
- every compact observation's semantic fingerprint recomputes exactly;
- every stage aggregate recomputes from its observations;
- every stage key recomputes from stage/source/target/checkpoint identity;
- every stage SHA-256 recomputes exactly;
- every report population recomputes from its stages; and
- the top-level report/corpus SHA-256 recomputes exactly.

The importer is intentionally bounded: individual files above 16 MiB are rejected and the corpus module places deterministic limits on stage/observation counts.

These SHA-256 checks provide deterministic integrity and corruption detection for exported evidence. They are not a signature or claim that an arbitrary third-party file is externally authenticated.

### Deduplication and repeated evidence

The corpus uses the complete stage SHA-256 as the identity of a single stage evidence record.

- If the exact same stage evidence record appears in multiple imported reports/corpora, it is stored and counted once.
- If two independent executions share the same deterministic `stageKey` but have different stage hashes, both remain in the corpus.
- Candidate population identity remains `stageKey + candidateRecordingHash`.

That distinction matters scientifically: overlapping exports must not inflate the evidence population. Because Phase -1I.4 intentionally has no random/session execution nonce, a truly independent rerun that produces a byte-identical stage record cannot be distinguished from an overlapping duplicate export and is conservatively counted once. Repeat consistency is measured only when independently collected stage records are distinguishable by their deterministic contents.

For each unique sample identity, the corpus reports whether observations repeat, whether their semantic fingerprints disagree, whether any mismatch occurred, and whether the sample is a clean exact-equivalent observation.

### Corpus summary

The deterministic `kq1agi-minimizer-checkpoint-evidence-corpus-v1` summary includes:

- unique stage records;
- total observations and unique candidate samples;
- duplicate observations caused by repeated sample identities;
- repeated and inconsistent samples;
- unique samples that actually attempted a checkpoint;
- clean equivalent samples;
- samples with any mismatch;
- full-only samples;
- evidence-compaction collection gaps;
- distinct GAMEFILES, EditConfig, and source-recording identities; and
- saved-tick distribution over clean, consistent unique equivalent samples: count, minimum, median, p90, maximum, and average.

The corpus also exposes explicit review flags for any mismatch, inconsistent repeat, collection gap, mixed GAMEFILES identity, or mixed EditConfig identity. These are evidence-review signals only; there is still no automatic acceleration decision.

### Browser workflow

The certification panel now exposes:

- **EXPORT EVIDENCE** — the current Phase -1I.4 browser-session report;
- **IMPORT EVIDENCE** — one or more hash-valid Phase -1I.4 reports / Phase -1I.5 corpora; and
- **EXPORT CORPUS** — the deduplicated cross-session corpus.

Imported evidence can be combined with new evidence collected in the current browser session. The same validated corpus is exposed as `globalThis.__kq1agiCheckpointEvidenceCorpus` for browser automation and audit inspection.

Import/review state is outside replay semantics. A rejected or malformed evidence file cannot change a minimizer result, and Phase -1E/-1F still return the mandatory full replay result exactly as before.

### Phase -1I.5 acceptance criteria

- Valid Phase -1I.4 reports import only after observation/stage/report integrity recomputation succeeds.
- Valid Phase -1I.5 corpora can be imported and combined incrementally with later reports.
- Import order does not change the final corpus hash.
- Re-importing an identical report/corpus does not inflate the corpus.
- Overlapping exports deduplicate exact stage executions by stage hash.
- Independent runs with the same stage key remain separate only when their stage records differ. A byte-identical independent rerun is intentionally indistinguishable from an overlapping duplicate export under the deterministic Phase -1I.4 format and is therefore counted once; this conservative undercount prevents unsupported evidence inflation.
- Tampered observation fingerprints, stage keys, stage hashes, populations, or top-level hashes are rejected.
- Mixed GAMEFILES/EditConfig evidence is surfaced explicitly rather than silently pooled.
- Saved-tick statistics use unique clean equivalent samples rather than duplicate observations.
- Imported evidence does not enable checkpoint acceleration or alter minimizer classification.
- Phase -1G remains full-replay-only and outside the checkpoint evidence population.
- Corpus policy remains `full-replay-authoritative`, `policyFrozen=false`, `policyDecision=EVIDENCE_ONLY`.

## Phase -1I.6 — deterministic evidence review record

Phase -1I.6 turns one hash-valid Phase -1I.5 corpus into a deterministic review artifact. It answers a narrower question than an acceleration policy: **does the currently collected evidence contain an obvious scientific blocker, and what exactly is still unset?**

The review record never authorizes checkpoint acceleration. It always declares:

- `policy: full-replay-authoritative`;
- `policyFrozen: false`;
- `policyDecision: EVIDENCE_ONLY`; and
- `accelerationAllowed: false`.

### Review states

A validated corpus receives exactly one evidence-review status:

- `NO_COMPATIBLE_SAMPLES` — there are no unique samples that actually attempted a checkpoint;
- `BLOCKED_BY_EVIDENCE` — one or more explicit evidence blockers are present; or
- `CLEAN_EVIDENCE_THRESHOLD_UNSET` — none of the current evidence blockers are present, but no minimum evidence threshold has been defined.

The third state is deliberately **not** equivalent to “ready to accelerate.” It means only that the current corpus has no known blocker under this review schema.

### Evidence blockers

The review emits a deterministic ordered blocker list. Current blocker codes are:

- `NO_CHECKPOINT_ATTEMPTS`;
- `CHECKPOINT_MISMATCH`;
- `INCONSISTENT_REPEAT`;
- `COLLECTION_GAP`;
- `MIXED_GAME_IDENTITY`; and
- `MIXED_EDIT_CONFIG_IDENTITY`.

A full-only candidate does not by itself block a corpus that also contains clean compatible checkpoint evidence. Full-only samples are still reported, but they represent candidates outside the recording-only checkpoint compatibility proof rather than a failed checkpoint equivalence attempt.

Mixed GAMEFILES/EditConfig identity is treated as a blocker for one global policy review. The corpus remains valid; the signal means evidence from those identities should not be silently pooled into one acceleration decision.

### Threshold remains intentionally unset

The review contains an explicit `thresholdPolicy` object with:

- `status: UNSET`;
- `minimumUniqueCheckpointAttemptedSamples: null`;
- `minimumDistinctSourceRecordings: null`; and
- `minimumSavedTickBenefit: null`.

Phase -1I.6 therefore freezes **no** sample-count threshold, diversity threshold, or performance-benefit threshold.

The evidence counts, identity hashes, and saved-tick distribution are copied from the independently validated corpus so a later policy-review PR can state its threshold against a fixed review artifact rather than silently changing the evidence population.

### Conservative corpus caveats

The review carries the Phase -1I.5 scientific caveats forward explicitly:

- byte-identical stage records are deduplicated;
- Phase -1I.4 contains no execution nonce, so an independently repeated byte-identical execution is indistinguishable from an overlapping export; and
- full replay remains mandatory.

These caveats are part of the hashed review record.

### Browser workflow

Whenever a valid Phase -1I.5 corpus exists, the certification panel derives the Phase -1I.6 review in best-effort evidence-only state and exposes it as `globalThis.__kq1agiCheckpointEvidenceReview`.

The panel also exposes **EXPORT REVIEW**, which downloads the deterministic `kq1agi-minimizer-checkpoint-evidence-review-v1` JSON artifact.

Review-generation failure can disable review export, but it cannot alter the validated corpus and cannot affect replay/minimizer classification.

### Phase -1I.6 acceptance criteria

- Review generation first requires a fully validated Phase -1I.5 corpus.
- Review hash is deterministic for the same corpus.
- The review always declares `accelerationAllowed=false`.
- The threshold policy remains explicitly `UNSET` with null numeric thresholds.
- No checkpoint attempts yields `NO_COMPATIBLE_SAMPLES`.
- Any checkpoint mismatch, inconsistent repeat, collection gap, mixed GAMEFILES identity, or mixed EditConfig identity appears in the blocker list.
- A clean corpus with compatible exact-equivalent samples yields `CLEAN_EVIDENCE_THRESHOLD_UNSET`, never an acceleration approval.
- Full-only samples may coexist with clean equivalent evidence without becoming an equivalence failure.
- The review retains only compact hashes/counts/identity metadata and never raw worker payloads.
- Phase -1G remains full-replay-only and has no review/corpus execution path.
- Full replay remains mandatory in every minimizer candidate.

## Phase -1I.7 — identity-scoped cohort review

Phase -1I.7 preserves the Phase -1I.6 global review while adding a deterministic way to inspect mixed evidence by the exact identity boundary that can affect execution from game start.

The cohort identity is exactly:

- GAMEFILES SHA-256; plus
- EditConfig SHA-256.

Source recording identity is **not** part of the cohort key. Multiple independent source recordings for the same GAMEFILES/EditConfig pair therefore contribute to the same identity-scoped population and remain visible through the existing distinct-source-recording count.

### Why cohorting is separate from the global review

A Phase -1I.6 review intentionally blocks a mixed GAMEFILES or mixed EditConfig corpus. That remains correct for any single global acceleration-policy discussion.

Phase -1I.7 does not remove or reinterpret that blocker. Instead, it derives a second artifact from the same validated parent corpus:

1. validate the complete Phase -1I.5 corpus;
2. group its already validated stage records by exact GAMEFILES + EditConfig hash;
3. build a normal Phase -1I.4 report and Phase -1I.5 child corpus for each group;
4. run the existing Phase -1I.6 review unchanged on each child corpus; and
5. export the resulting ordered cohort summaries as one deterministic bundle.

Because every child goes back through the existing corpus and review validators, cohorting does not create a weaker alternate review path.

### Cohort review bundle

The deterministic schema is `kq1agi-minimizer-checkpoint-evidence-cohort-review-v1`.

Each cohort records:

- deterministic cohort key;
- exact GAMEFILES hash;
- exact EditConfig hash;
- sorted stage hashes belonging to that cohort;
- sorted source-recording hashes contributing to that cohort;
- child corpus hash;
- Phase -1I.6 review hash/status/blockers;
- compact evidence counts;
- saved-tick distribution;
- `accelerationAllowed=false`; and
- the same explicitly `UNSET` numeric threshold policy.

The bundle also records the parent corpus hash, cohort count, and deterministic counts of each review status.

Every parent stage record belongs to exactly one cohort. A different source recording under the same GAMEFILES/EditConfig identity remains in the same cohort.

### What cohorting may and may not change

Cohorting can remove only the *global mixing condition* by considering one exact identity at a time.

It must **not** remove evidence blockers intrinsic to that identity. For example:

- a checkpoint mismatch remains `CHECKPOINT_MISMATCH`;
- an inconsistent repeated sample remains `INCONSISTENT_REPEAT`;
- a collection gap remains `COLLECTION_GAP`; and
- a cohort with no checkpoint attempts remains `NO_COMPATIBLE_SAMPLES`.

A globally mixed corpus may therefore be `BLOCKED_BY_EVIDENCE` while two individual identity cohorts are each `CLEAN_EVIDENCE_THRESHOLD_UNSET`. This does not approve acceleration; it only shows that the global blocker came from identity pooling rather than an equivalence failure inside either cohort.

### Browser workflow

Whenever a valid Phase -1I.5 corpus exists, the certification panel derives both:

- the global Phase -1I.6 review; and
- the Phase -1I.7 identity cohort bundle.

The global review remains exposed as `globalThis.__kq1agiCheckpointEvidenceReview`.

The cohort bundle is exposed separately as `globalThis.__kq1agiCheckpointEvidenceCohortReview` and can be downloaded with **EXPORT COHORTS**.

Failure to derive cohorts disables only the cohort export. It cannot rewrite the global review, corpus, replay result, or minimizer classification.

### Phase -1I.7 acceptance criteria

- Cohort generation requires a fully validated Phase -1I.5 parent corpus.
- Cohort identity is exactly GAMEFILES hash + EditConfig hash.
- Different source recordings with the same GAMEFILES/EditConfig identity remain in one cohort.
- Every parent stage hash appears in exactly one cohort.
- Cohort ordering and bundle hash are deterministic.
- Each cohort is rebuilt through the normal Phase -1I.4 report, Phase -1I.5 corpus, and Phase -1I.6 review functions.
- A globally mixed identity corpus remains globally blocked under Phase -1I.6.
- Per-cohort review may be clean only when that child corpus has no non-identity evidence blocker.
- Mismatch, inconsistency, collection-gap, and no-attempt blockers survive cohorting.
- Every cohort and the top-level bundle declare `accelerationAllowed=false`.
- Threshold policy remains `UNSET` with null numeric thresholds.
- Raw worker payloads are never included.
- Phase -1G remains full-replay-only and outside cohort/review execution.
- Full replay remains mandatory for every candidate.

## Next slice

Collect real Phase -1E/-1F evidence and use the Phase -1I.7 cohort bundle to inspect each exact GAMEFILES/EditConfig identity separately. Only after a real identity-scoped population is clean should a later, separately reviewed PR propose a numeric evidence threshold or acceleration policy. Phase -1I.7 itself changes no replay authority.
