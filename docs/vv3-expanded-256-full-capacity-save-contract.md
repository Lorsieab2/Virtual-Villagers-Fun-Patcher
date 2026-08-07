# VV3 Expanded-256 full-capacity save contract

This is a disabled evidence/reference contract for D350/D351. It emits no native bytes and authorizes no patch, package, launch, save access, runtime claim, or publication. The D350/D351 findings remain explicitly unverified until authenticated exact-build exporter evidence supplies function bounds, raw bytes, complete xrefs, save callers, and full-folder provenance.

The fixed geometry is record size `0x11C`, record body offset `0x7864`, logical indices 0–255, tail offset `0x19464`, expanded body size `0x1A4B4`, and expanded file size `0x1A4C0`. Indices 256–259 are padding and must be unreachable and non-saveable.

Required writer semantics are: count is 0–256; serialize only logical records; emit a terminator only when count is below 256; at count 256 preserve the tail without a terminator write. The reader must accept an earlier terminator, but at exactly 256 records stop successfully without reading the tail and reject any 257th record. Failure must preserve manager/pool identity and live state.

Atomic publication is a separate gate: create an owned sibling temporary file, write exactly `0x1A4C0`, flush/close, reopen no-follow, verify size and the authenticated integrity transform, atomically replace only after verification, preserve the prior destination on every failure, and clean only the owned temporary artifact. The runtime fault matrix keeps all twelve success/failure scenarios pending.

Checked-in function references are `0x45EF80`, `0x45C860`, `0x428810`, and `0x45C8D0`. Their bounds, bytes, xrefs, caller rows, emitted section, hook, and final bytes are all null/empty. JSON Schema acceptance alone is not evidence; the manual validator pins dependencies, canonical digest, exact geometry, empty native rows, required semantics, and every STOP flag.

Run `python scripts/validate_vv3_full_capacity_save_contract.py`. A successful invocation validates only the disabled contract and prints `status: STOP`.
