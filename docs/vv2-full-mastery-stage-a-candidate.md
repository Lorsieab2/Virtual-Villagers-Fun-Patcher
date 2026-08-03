# VV2 Full Mastery repaired candidate (pending recertification)

This disabled, catalog-hidden stock-only candidate is generated from the C132 native ABI repair. It remains unavailable pending independent recertification; no player package is produced by this task.

- Section SHA-256: `50E28082858BA3C413223109EF25408884C1B7165128ED98B4C24EB913B45070`
- Companion SHA-256: `B91FEA9860B247120ADB8E6A477AE4F179AE30761A28061336FD4EA49AE7BCF9`
- Entry SHA-256: `48B02CAF6C1E99BF477DA0CBA76F89A9D4371679739EF404FB60BF1EBBD3E1E4`
- Walker SHA-256: `9D0F75C1A2E27CEB96DB777E43F333140A3F639F98E2455A0D706B5F48D6C98F`
- Confirmation SHA-256: `8868C87F2B66AD9D69F1DC7A08A469E5C5C478727955A5E1E4F6DA4EEB306B2C`

The candidate appends `.vv2fm`; it never uses or changes `.shr`. It adds command 7 only, with commands 6/8, ownership, Remove, Gong, and Island Event interception absent. The transaction performs a complete 256-record dry run before funds/confirmation, reacquires the manager, uses only sub_445430 for changed skills, post-verifies exact 100, calls sub_44D4C0 once, then sub_426290 once for the single deduction. Expanded-256 modes are rejected before output. The raw manifest and complete map are under `data/candidates/`. If a native writer succeeds and a later postverify fails, the candidate reports no-charge failure without an unproved rollback of already-applied native changes.
