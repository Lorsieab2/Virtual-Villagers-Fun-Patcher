# VV4/VV5 Expanded-256 stored-index evidence gate

This is a disabled, fail-closed evidence gate. The canonical contract is
`data/expanded_256_stored_index_evidence.json`, its structural schema is
`data/schemas/expanded_256_stored_index_evidence.schema.json`, and the static
validator is `scripts/validate_expanded_stored_index_evidence.py`. Expanded-256
publication remains `false` regardless of this gate; runtime/player approval
must remain separate.

## Why this gate is STOP

An exclusive bound of 256 makes record indices `0..255` available, but that
does not prove every place that stores or transports an index can represent
255. In particular, a byte `0xFF` cannot simultaneously mean valid record 255
and no-record. A bound edit or record-255 endpoint is candidate evidence only
until the surrounding stored width, sentinel, function, instruction, operand,
and callers are exact.

For both games the contract enumerates all eleven path categories:

1. selection;
2. roster;
3. Detail;
4. queue/actions;
5. pairing/pregnancy;
6. birth/death;
7. skeleton/memorial;
8. Events/puzzles;
9. statistics;
10. callbacks; and
11. serializer/load/catch-up.

Every observed row must bind one game-scoped path ID to an exact function name
and function EA, instruction EA, operand file offset, operand width, stored
width, explicit sentinel (including an explicit no-sentinel declaration),
nonempty xrefs, record-255 acceptance proof, indices-256-through-259
unreachable/non-saveable proof, exact source hashes, and authenticated runtime
receipt references. Missing or duplicate categories, paths, xrefs, or
candidate references are STOP.

An `observed_complete` category must also declare its exact expected path count
and a canonical SHA-256 over the complete ordered row ledger. One sample row
cannot stand in for an unbounded or unenumerated category.

The current contract has zero complete categories for VV4 and zero for VV5.
Known manifest edits are pinned by canonical row digest but marked
`qualifying_evidence: false`. They prevent stale static inputs from being
silently accepted; they do not close the stored-index audit.

## Exact identities and composition bindings

| Game | Exact stock identity | Stored-index/save candidate edits | Current Origins relocation binding |
|---|---|---:|---:|
| VV4 The Tree of Life | 929,792 bytes; `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` | 13 | 13 rows; `CEE01F4AEC59CB1CEE0F42E3DDDB3A24615261E628ED0629C1BFAABF421A897D` |
| VV5 New Believers | 991,232 bytes; `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D` | 15 | 66 rows; `A5DF4E109D32E2BC9FDE36E2BA3139230B6E6CD89DE4C3FF784846F4CE803740` |

The 13-row VV4 and 66-row VV5 relocation ledgers remain independently pinned
and recomputed from their current Origins manifests. Relocation completeness
does not establish index-width completeness.

The full-folder fingerprint for each game is currently absent. A future row
cannot complete a category until the no-follow capture harness supplies an
exact nine-role artifact inventory, complete-folder canonical digest, and an
independently authenticated runtime-capture packet bound to runtime contract
digest
`C70F0BD0CDDFF921B215FA178D725A57EC2AEE380C575FFD1D56D8F282562B60`.
Unsigned capture candidates remain evidence inputs only, never GO.

## VV4 boundary

VV4 has 256 logical and 256 physical records with no VV3-style padding
reservation. Record 255 is allocated in the static layout. Indices 256-259 are
outside the allocated record pool, but the complete path-by-path proof that
they cannot be selected, queued, constructed, serialized, counted, or reached
through callbacks is absent.

The current manifest pins eleven selection/lookup/picker edits and two
stock-import/load-mover edits. Their exact function boundaries, instruction
heads, operand widths, stored widths, sentinel semantics, and full xref sets
are not committed as qualifying evidence. VV4 is not inferred from VV5; its
stored index width and sentinel remain independently unknown and therefore
STOP.

## VV5 boundary

VV5 likewise has 256 logical and 256 physical records with no extra padding.
The cited static source identifies these limited fragments:

- `sub_46F950` (`0x46F950`) is the unsigned record lookup candidate whose bound
  was changed to accept 255;
- `sub_4708F0` (`0x4708F0`) is cited as using DWORD `0xFFFFFFFF` (`-1`) for no
  selection while allowing a candidate index of 255; and
- the pending-record list is cited as DWORD storage, but its exact function,
  instruction, sentinel, and xrefs remain missing.

VV5 DWORD/`-1` evidence is path-scoped. It is not generalized to other VV5
rosters, queues, callbacks, serializers, or caches, and VV4 is not inferred
from VV5. Those citations remain `partial_static_stop` until exact instruction
and xref evidence plus player/runtime receipts are attached.

## Adversarial rules

The validator fails closed on:

- a byte `0xFF` no-record sentinel where record 255 is claimed valid;
- missing, duplicate, extra, or reordered path categories;
- missing/duplicate candidate edits or stale manifest-row digests;
- missing functions, EAs, operand widths, stored widths, sentinels, xrefs,
  record-255 proof, or indices-256-through-259 proof;
- duplicate path IDs or runtime receipt references;
- stale source, schema, stock, full-folder, runtime-contract, harness, or
  relocation hashes;
- synthetic evidence, manual field injection, or developer-only inference;
- a claim that record 255 or indices 256-259 are proven without exact
  full-folder and authenticated runtime capture evidence; and
- any attempt to generalize the limited VV5 DWORD/`-1` citations to VV4 or
  unenumerated paths.

## Current disposition

VV4: **STOP**. VV5: **STOP**. Full-folder fingerprints and authenticated
runtime receipts are absent; all eleven categories remain incomplete. No game
was launched and no real save was accessed while creating or validating this
contract. No package was built, no save was written, and no publication or GO
flag was enabled.
