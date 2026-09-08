# Truth Engine Phase -1I.14 — Collection-set manifest

Phase -1I.14 adds a deterministic archive manifest over one or more validated Phase -1I.13 live collection packages.

## Purpose

Phase -1I.13 made one live browser collection snapshot self-contained. Phase -1I.14 makes a set of those packages reproducibly addressable without changing evidence authority.

The manifest:

- validates every Phase -1I.13 package before inclusion;
- collapses exact duplicate package hashes idempotently;
- sorts package hashes deterministically;
- records package/run identities and compact package summaries;
- rebuilds the canonical Phase -1I.10 provenance census over the package set;
- rebuilds Phase -1I.11 exact-identity coverage from that same population;
- rebuilds Phase -1I.12 session topology from that same population;
- binds all three derived hashes into one manifest hash;
- leaves same-run prefix/conflict semantics to the already-qualified Phase -1I.10 rules.

## Scientific boundary

The manifest is archive/descriptive infrastructure only.

It always declares:

- `policy=full-replay-authoritative`
- `policyFrozen=false`
- `policyDecision=EVIDENCE_ONLY`
- `accelerationAllowed=false`
- `manifestDecision=COLLECTION_SET_ARCHIVE_ONLY`

It does not:

- change Phase -1I.5 corpus counts;
- define an evidence sufficiency threshold;
- claim collection-run identity proves physical or human independence;
- permit any Phase -1E/-1F candidate to skip full replay;
- alter Phase -1G.

## Determinism and reconciliation

Exact duplicate package hashes contribute once to the manifest. Distinct snapshots from one collection run may both remain listed as archived package identities, while the derived Phase -1I.10 population selects only the longest consistent snapshot for that run. Conflicting same-run histories continue to reject through the Phase -1I.10 validation chain.

This distinction is intentional: the manifest describes the archived package set, while I.10-I.12 describe the reconciled provenance population derived from that set.
