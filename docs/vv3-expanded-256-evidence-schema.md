# VV3 Expanded-256 evidence bundle

This schema is a future-input contract for the read-only IDA exporter and
`reconcile_expanded_256_gate_refs.py`. It does not read a stock executable,
save, DLL, or game folder. It does not produce a patch and cannot enable the
Expanded-256 publication gate.

The validator is `scripts/validate_vv3_expanded_evidence.py`, with its logic in
`src/vv3_expanded_256_evidence.py`. A bundle is accepted only when all of the
following are present and exact:

- the reviewed VV3 source and prototype SHA-256 values, stock size, image base,
  and reconciler guard/overlap/unmatched-reference summaries;
- complete, non-synthetic, non-ambiguous loader ABI and branch claims;
- all ten stored-index paths with an explicit width and sentinel decision;
- selectors, planner/action queue, callbacks, statistics, and serializer claims;
- construction, selection, serialization, population-counting, and statistics
  proof that indices 256–259 are unreachable;
- every reviewed loader/bound operand with exact file offset, EA, raw stock
  bytes, and at least one distinct xref.

Duplicate claims, duplicate observations, absent fields, unresolved status,
synthetic/incomplete provenance, mismatched hashes, mismatched raw bytes,
missing xrefs, and reconciler omissions all fail closed. Runtime gates are a
separate required section: load-hang resolution, stock-import/expanded-save
reload, offline catch-up, failed-load nonmutation, late-record coverage, and
player runtime validation. The runtime-evidence catalog must contain each
cited ID as a non-synthetic, non-ambiguous, complete, hashed capture with a
portable relative path and byte size. Catalog paths reject absolute, traversal,
drive/stream, reserved, separator-ambiguous, and reparse-like forms. Catalog
artifact paths and SHA-256 values are unique, and one artifact hash cannot be
reused by multiple gates. Unknown keys, duplicate JSON object keys, and boolean
values in integer fields fail closed. `load_evidence` accepts only canonical
UTF-8 JSON (sorted keys, compact separators); `inventory_evidence_file` rejects
reparse points and detects file identity or metadata changes during hashing.
`validate_evidence_file` binds the inventory, read, and post-validation bytes so
an evidence-file mutation cannot publish. Each gate must be independently
verified and cite IDs from that catalog.

The current static contract deliberately remains publication-false. Therefore
even a future structurally valid bundle cannot return publication-ready until
the existing contract gate is independently changed and all runtime gates are
actually verified.

The command exits nonzero for incomplete evidence and prints a JSON result:

```text
python scripts/validate_vv3_expanded_evidence.py path\to\evidence.json
```

Unit tests use only in-memory JSON objects, temporary evidence fixtures, and
contract bytes; they never need the stock executable, saves, or a game folder.
