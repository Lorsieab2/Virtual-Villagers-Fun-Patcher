# VV3 Expanded-256 save/serializer ABI evidence gate

This additive gate is a disabled evidence specification. It does not patch, emit, package, launch, discover saves, or read save contents. Passing JSON Schema is never sufficient: the manual validator also checks canonical JSON, exact repository bindings, authenticated no-follow files, stable identity across read, complete row order, xref uniqueness, and the permanent STOP decision.

The gate binds the exact VV3 stock/prototype fingerprints, authenticated-exporter contract from `8444df9`, complete-folder and pending receipt contracts/harness from `0940bb5`, and stored-index gate from `37b06b1`. Text dependency hashes use canonical Git LF content so the same committed bytes validate in a CRLF checkout and a clean archive. Every native observation must be tied to the complete authenticated game-folder inventory and exporter artifacts. Checked-in native observations are deliberately empty.

## Native ABI gaps

| Row | Address/offset | Required evidence | Current state |
|---|---|---|---|
| Loader entry | EA `0x428949`, file `0x28949` | exact function bounds, calling convention, arguments, registers/stack, branches, failure semantics, bytes, complete xrefs | absent |
| Loader cave | EA `0x47B3B1`, file `0x7B3B1` | same, including cave ownership and control-flow edges | absent |
| Loader post-copy | EA `0x428961`, file `0x28961` | same, including success/failure destinations | absent |
| Save count | EA `0x428810` | exact bounds/ABI/bytes/xrefs and record-count meaning | absent |
| Writers | EAs `0x45C860`, `0x45C8D0`, `0x45EF80` | exact bounds/ABI/bytes/xrefs and writer roles | absent |

The historical loader hang is not satisfied by narrative notes. A future authenticated receipt must identify the exact faulting instruction and raw bytes plus caller/callee, stack, registers, arguments, return address, branch history, manager identity, and pool identity.

## Remaining gap matrix

Evidence is absent for exact stock/expanded sizes and layouts; record count/size/base/tail/gap and serializer bounds; checksum/encryption/compression; stock-import conversion; rotation/temp/atomic replacement; failed-load nonmutation; offline-catch-up order; records 149/150/254/255; padding 256–259 unreachable and non-saveable; current Origins behavior; and explicit player receipts. The runtime receipt stages remain unsigned and pending. Consequently `gate_ready`, `runtime_go`, `player_go`, `publication_ready`, and native emission remain false.

Validate the checked-in STOP contract with:

`python scripts/validate_vv3_save_serializer_abi_gate.py`

A future candidate additionally requires `--candidate` and an explicit `--catalog-root`; the v1 tool still exits nonzero and reports STOP even when structural/authentication checks succeed.
