# VV2 Full Mastery repaired candidate (pending recertification)

This disabled, catalog-hidden stock-only candidate is generated from the C134 D129 native transaction repair. It remains unavailable pending independent recertification; no player package is produced by this task.

- Section SHA-256: `C1DA8ED6D809FFE240A85E14D2D541CC89F3ED5DB11DDAFD303FC88A9EF86297`
- Companion SHA-256: `05798EA051F7D9FE0EB65C3C40719E7A37683E2F3C446CF53BF0489C28A0876F`
- Entry SHA-256: `EC14EEE56222B0345A5610C4ADCB347BA8E9E3442B9804C0941A9E8F984A170C`
- Walker SHA-256: `E67F5F34AEB66A953B5B2A77FD6A5EA00B907D26B61A25A0C132F62C713C98DD`
- Confirmation SHA-256: `8868C87F2B66AD9D69F1DC7A08A469E5C5C478727955A5E1E4F6DA4EEB306B2C`

The candidate appends `.vv2fm`; it never uses or changes `.shr`. It adds command 7 only, with commands 6/8, ownership, Remove, Gong, and Island Event interception absent. The five native skill IDs are Farming=3, Building=2, Research=1, Healing=5, and Parenting=4; the walker uses real stack locals, preserves EBX/ESI/EDI, and keeps the 256-record bound stable across every native call. A zeroed snapshot records 0 unchanged, 1 newly changed from unmarked, and 2 newly changed from marked. Both menu and result exports are preflighted before any confirmation or mutation. The transaction performs a complete 256-record dry run before funds/confirmation, reacquires manager/state at every pointer-sensitive phase, post-verifies exact 100, calls sub_44D4C0 once, refreshes telemetry, then calls sub_426290 once for the single deduction. Cancel and every failure report `No tech points have been deducted.` Expanded-256 modes are rejected before output. The raw manifest and complete map are under `data/candidates/`. If a native writer succeeds and a later postverify fails, the candidate reports no-charge failure without an unproved rollback of already-applied native changes.
