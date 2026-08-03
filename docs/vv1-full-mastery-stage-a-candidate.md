# VV1 Full Mastery stock-mode candidate

The exact stock-only candidate is catalog-enabled for `collection_progression` and `immediate_fixed` after the C76/D82/C83 static recertification gate against source commit `2f22a8b435918bf01b95aa4b9a6e6f4287d0ac94`. Runtime/player confirmation is still pending; no Expanded-256 output is accepted.

- Section SHA-256: `85DE335D905D0AF99FBDD0388A004D69C393AA7C0771DFB36B15A4A94062BA92`
- Companion SHA-256: `4736E5EFB8F680E3B1F124D1920A9390D9F6427260E60743039FA80F8646CCB3`
- Entry SHA-256: `DB742B8C696A5D197D4985E49DE636C4E3E584BBC1B7E65132611E2FC4B42A31`
- Walker SHA-256: `948C1B9E968FB5A8F957E33F6C344A1FF0DC25805BB97DB2D959129A4E2B8C9E`
- Confirmation SHA-256: `39FBB3CA5B2C32C5566EA918C249D77718F2872AF871511EA23147C48AE6E779`

The candidate appends `.vv1fm`; it does not reuse the overlapping old Origins payload. It adds command 7 only, with commands 6/8, ownership, Remove, Gong, and Island Event interception absent. The result export is resolved and validated before any charge or native writer call, then retained through commit. The physical pool is reacquired from `state=[Tech+0x0C]` and `pool=[state+0xADE8]` with null fail-closed guards, preserving 256 records at stride `0x3D8`. A complete mode-0 dry run and no-change test precede the unsigned funds check and explicit 1,000,000-point confirmation. Mode 1 performs the complete native write pass, then reacquires the pool and performs a second read-only pass over all 256 records with identical eligibility/range checks and exact-100 requirements before the single deduction; there is no mode-2 entry walk. A process interruption or failed verification cannot safely roll back partial native writes, so no charge is made. Collection Progression and Immediate Fixed are the only allowed modes; Expanded-256 is rejected before output creation. The C76 recertification bundle emits the active Origins/Cure base, combined Origins/Cure plus Full Mastery audit identity, Full Mastery uninstall identity, and a proof manifest whose uninstall hash equals the active base hash. The raw manifest and complete map are under `data/candidates/`.
