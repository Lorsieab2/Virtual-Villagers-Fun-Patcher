# VV3 Expanded-256 stabilization gate

This additive gate binds the current VV3 evidence contracts into one deterministic static check. It does not authenticate a stock executable, invent native operands, open a game folder, access saves, launch a game, or turn any runtime/publication flag on.

The contract preserves the corrected VV3 full-capacity geometry: record size 0x11C, body offset 0x7864, logical records 0..255, padding 256..259, tail 0x19464, body 0x1A4B4, and file 0x1A4C0. The VV3 relocation manifest is bound to exactly 1,263 declared and physical rows. Stored-index widths and sentinels, serializer/reader ABI, full-capacity save behavior, runtime capture, and decoded relocation completeness remain explicit STOP gaps until authenticated exporter rows, a complete folder, and real runtime/player receipts exist.

The foreign_preservation block is an integration invariant only. It records the authoritative containment-side VV4/VV5 relocation ledgers (13 and 66 rows) and the corrected VV5 0xDB1A4 rel32 row. It is deliberately pending_containment_integration; those values are not substituted for VV3 evidence and the older foreign files in this specialist worktree are not rewritten.

Validate the checked-in contract with:

    python scripts/validate_vv3_expanded_256_stabilization_gate.py

Successful validation means only that the disabled contract is internally consistent. It reports STOP; it is not a native, runtime, player, or publication GO.
