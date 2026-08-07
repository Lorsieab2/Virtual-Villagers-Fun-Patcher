# VV4 full-256 serializer evidence contract

Status: **STOP / disabled**. Runtime, player, eligibility, and publication remain false.

This additive contract records D350/D351 static reference evidence for stock functions `0x4660A0` and `0x466110`. It does not emit native code or establish runtime safety. The current immediate-only changes at raw `0x660AC` and `0x66119` are explicitly insufficient: the writer still places an unconditional terminator into the relocated tail at full capacity, while the reader remains sentinel-driven without a proved 256-record bound.

Qualifying behavior requires a conditional terminator only when `packed_count < 256`, successful decoding of exactly 256 unterminated records, a hard reader bound of exactly 256, and byte-for-byte preservation of the tail beginning at body offset `0x1CC60`. The expanded body/file sizes are `0x1DCB4`/`0x1DCCC` with a 24-byte header.

The new-section placement, hook targets, replacement bytes, and final hashes are unknown and null. Writer atomicity is a separate six-gate requirement: sibling temporary file, checked writes, flush/checked close, reopen verification, atomic replacement preserving the prior save, and directory synchronization where supported. All fault-matrix receipts are absent.

The validator pins the unchanged VV4 13-row ledger digest and records the C342 VV5 66-row integration digest. It never interprets either relocation ledger as save proof. After transplant onto C342, run this validator and its tests against the final tree; do not rewrite either ledger.

Validation:

```powershell
python scripts/validate_vv4_full256_serializer_evidence.py
python -m unittest tests.test_vv4_full256_serializer_evidence
```
