# VV3 Expanded-256 stored-index and padding evidence gate

This is a strictly disabled evidence contract, not a conclusion about VV3's
native index representation. The canonical contract is
`data/vv3_expanded_256_stored_index_gate.json`; its declarative shape is
`data/vv3_expanded_256_stored_index_gate.schema.json`; and its validator is
`scripts/validate_vv3_stored_index_evidence_gate.py`.
Future candidate shape is separately pinned by
`data/vv3_expanded_256_stored_index_evidence.schema.json`; schema acceptance
does not authenticate its cited files or make the gate ready.

The current result is `STOP`. Publication, runtime GO, player GO, and
eligibility are all false. No stock executable, game folder, DLL, save, native
emission, package, or launch is required or permitted by this tooling.

## Exact path boundary

The contract preserves the ten-path order already defined by the authenticated
VV3 evidence and runtime-receipt harness:

1. `selection`
2. `sorted_roster`
3. `detail_navigation`
4. `planner_action_queue`
5. `pairing_pregnancy`
6. `birth_death`
7. `skeleton_memorial`
8. `event_puzzle`
9. `statistics`
10. `callbacks`

`serializer` is an additional required consumer binding, not an invented
eleventh stored-index path. A future candidate must prove its exact record-255
and padding behavior with its own complete observations and xrefs.

## Evidence required before review

For every path, a future candidate must provide all of the following:

- one explicit width of 8, 16, 32, or 64 bits;
- an explicit sentinel decision, including width, signedness, integer value and
  raw bytes when a value sentinel exists, or explicit `none` with no invented
  value/bytes;
- VV3-only derivation marked non-inferred and with no cross-game source;
- authenticated observation references;
- exact EAs, file offsets, uppercase raw bytes, and complete canonical xref
  tuples for every observation;
- observed acceptance and saveability of logical record 255.

Serializer evidence must independently show record 255 saved and padding not
saved. Padding records 256, 257, 258, and 259 must each be proved unreachable
and non-saveable across construction, selection, serialization,
population-counting, and statistics paths. The candidate must also bind the
`padding_unreachable_records` and `stored_index_sentinel_paths` stages from the
0940 runtime-receipt schema and include explicit player confirmation.

## No inferred sentinel or borrowed representation

Repository-owned evidence does not currently pin the exact VV3 widths,
sentinels, EAs, or complete xref sets. The canonical expectation fields
therefore remain null/empty and status `absent`. In particular:

- byte `0xFF` is not treated as a VV3 sentinel merely because record 255 is a
  boundary value;
- VV5 DWORD/`-1` behavior is not imported into VV3;
- no width or sentinel from any other game is accepted as VV3 evidence.

The candidate validator can reject malformed, incomplete, synthetic,
cross-game, noncanonical, xref-incomplete, or unauthenticated submissions. Even
a structurally complete candidate remains `gate_ready: false` while the
repository-owned `reviewed_expectations.status` is `absent`. Populating those
expectations requires a separate review/change after real authenticated VV3
native evidence exists.

## Provenance binding

The contract pins authenticated-evidence commit
`8444df9c314f8ee9a6a29930a9d1be1e70e6adb7`, runtime-capture commit
`0940bb5328217aee7a08963ce22c7dddc3ca4503`, the exact VV3 stock/prototype
identities, and SHA-256 values for both prior schemas and validators. Candidate
validation requires an explicitly supplied canonical evidence bundle and
catalog root that pass `validate_evidence_file`; declared producer/hash metadata
alone is not authenticated provenance.

Validate the canonical disabled contract:

```text
python scripts/validate_vv3_stored_index_evidence_gate.py
```

A future candidate invocation requires all three explicit inputs and always
returns a nonzero STOP in this contract version:

```text
python scripts/validate_vv3_stored_index_evidence_gate.py --candidate path\candidate.json --authenticated-evidence-json path\evidence.json --catalog-root path\catalog
```
