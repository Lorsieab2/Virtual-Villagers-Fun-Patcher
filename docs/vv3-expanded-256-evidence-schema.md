# VV3 Expanded-256 evidence bundle

This schema is a future-input contract for the read-only IDA exporter and
`reconcile_expanded_256_gate_refs.py`. It does not read a stock executable,
save, DLL, or game folder. It does not produce a patch and cannot enable the
Expanded-256 publication gate.

The validator is `scripts/validate_vv3_expanded_evidence.py`, with its logic in
`src/vv3_expanded_256_evidence.py`. A bundle is only statically authenticated
by `validate_evidence_file`; direct in-memory validation is structural
diagnostics and can never report `static_valid`. An authenticated bundle must
contain all of the following:

- the reviewed VV3 source and prototype SHA-256 values, stock size, image base,
  and reconciler guard/overlap/unmatched-reference summaries;
- complete, non-synthetic, non-ambiguous loader ABI and branch claims;
- all ten stored-index paths with an explicit width and sentinel decision;
- selectors, planner/action queue, callbacks, statistics, and serializer claims;
- construction, selection, serialization, population-counting, and statistics
  proof that indices 256-259 are unreachable;
- a root-relative exporter-manifest catalog record whose file is canonical,
  stable, size/hash-bound, and contains the exact reviewed operand EA and
  complete ordered `(xref address, kind)` tuples;
- provenance whose producer, run ID, manifest digest, and manifest-file digest
  match that verified exporter manifest.

Synthetic/incomplete provenance, mismatched hashes, mismatched raw bytes,
missing xrefs, reordered or substituted operand evidence, and reconciler
omissions all fail closed. Runtime gates are a separate required section:
load-hang resolution, stock-import/expanded-save reload, offline catch-up,
failed-load nonmutation, late-record coverage, and player runtime validation.
Runtime catalog paths are portable relative paths; every cited artifact is
opened under the explicit catalog root with no-follow checks, inventoried and
hashed, then inventoried again after validation. Declared path, size, and
canonical uppercase SHA-256 must equal the stable inventory. Missing files,
symlinks, reparse traversal, substitution, and mutation fail closed. Each gate
must be independently verified and cite IDs from that catalog.

`data/vv3_expanded_256_exporter_manifest.schema.json` describes the canonical
manifest file. Its `manifest_sha256` is the uppercase SHA-256 of its canonical
JSON body with that digest field removed. The manifest binds the exact VV3
source SHA-256, source size, prototype SHA-256, exporter/run identity, and the
complete reviewed operand/xref set. Declared metadata is not called
authenticated until the manifest and every catalog artifact have passed these
file-bound checks.

Unknown keys, duplicate JSON object keys, non-canonical JSON, duplicate or
reordered xrefs, duplicate catalog entries, and boolean values in integer fields
fail closed. `inventory_evidence_file` rejects reparse points and detects file
identity or metadata changes during hashing. `validate_evidence_file` also
re-reads the manifest, every runtime artifact, and the evidence bundle after
validation; it is not an ongoing file lock and cannot attest to later changes.

The JSON Schema mirrors manually checked object shapes, strict scalar types,
reviewed VV3 fingerprints, and conservative catalog-path syntax where JSON
Schema can express them. Schema-only acceptance is not sufficient: JSON Schema
cannot reject duplicate JSON object keys, enforce uniqueness or ordering across
arrays, authenticate a digest against file bytes, or inspect filesystem
identity, symlinks, junctions, and reparse points. The canonical loader and
Python validator remain mandatory.

The current static contract deliberately remains publication-false. Therefore
even a future structurally valid and authenticated bundle cannot return
publication-ready until the existing contract gate is independently changed and
all runtime gates are actually verified.

The command exits nonzero for incomplete evidence and prints a JSON result:

```text
python scripts/validate_vv3_expanded_evidence.py path\to\evidence.json --catalog-root path\to\catalog-root
```

Unit tests use only temporary canonical manifests, runtime-artifact fixtures,
in-memory negative cases, and contract bytes; they never need the stock
executable, saves, DLLs, or a game folder. The static contract and publication
gate deliberately remain false, and unresolved native/runtime gates remain
required.
