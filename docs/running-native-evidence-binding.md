# Running native-evidence binding

`src/running_native_evidence.py` is a read-only, fail-closed preflight for a
future VV3/VV4/VV5 Grant Running evidence adapter.  It accepts only a copied
game folder beneath a caller-declared workspace root and an already-produced
`vvfp.authenticated-native-export.v1` JSON file.  It rejects links/reparse
points, outside paths, unstable files, wrong stock executable name/size/hash,
partial or reordered query rows, synthetic/manual exports, stale inventory
bindings, source-byte mismatches, and incomplete ABI-shaped rows.

The copied input is bound to the exact stock executable fingerprint already
declared in the per-game Running manifest.  The export must contain the ten
canonical native query rows, including the identity/account-relevant rows:

- `selected_index_and_world_resolver`
- `funds_getter`
- `funds_deduction_setter`
- `preference_setter_readback_queue`
- `confirmation_result_abi`
- `postverify_fault_boundary`

This generic export is necessary evidence input, not sufficient Running proof.
It does not prove selected-index resolution, resolved record-pointer identity,
world identity, preference semantics, same-account balance readback, rollback,
runtime behavior, or player behavior.  Consequently a valid export still
returns `status: STOP`, `enabled: false`, `catalog_enabled: false`,
`catalog_hidden: true`, `native_output: false`, and false runtime/player flags.

VV1/VV2 remain STOP because the copied authenticated export schema currently
covers VV3–VV5 only.  No native export, executable, save, or package is created
by this binding.
