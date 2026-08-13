# VV3-VV5 native statistics mutation evidence gate

`data/native_statistics_mutation_evidence.json` is a disabled evidence bundle
for future native mutation work. It is deliberately separate from
`data/statistics_features.json`, whose existing VV3-VV5 behavior remains a
post-save text export plus its already-reviewed unrelated counter hooks.

The validator has three independent decisions:

- `schema_valid`: the contract has the expected top-level shape and exact
  game/fingerprint guard structure;
- `evidence_complete`: every required native proof is verified, fresh,
  fingerprinted, non-synthetic, non-overlapping, and internally consistent;
- `publication_allowed`: both evidence completeness and an explicit enabled
  flag would be required. The checked-in contract has `enabled: false`, so
  this decision remains false even after a future evidence bundle is complete.

Each VV3-VV5 record must eventually carry the exact stock executable and
complete-folder fingerprints, an ABI at the earliest successful skeleton
pickup, exactly-once and duplicate/no-op semantics, persisted lifetime-max
Oldest updater evidence, a dedicated baseline and initialized marker, atomic
save/load serializer ownership, reload/offline-catch-up idempotence, failed
load nonmutation, Expanded-256 round-trip evidence, hook/cave composition,
and runtime/player receipts.

The validator rejects synthetic or stale receipts, missing or duplicate
receipt IDs, wrong source hashes, overlapping hook/cave regions, any use of
the withdrawn delayed corpse-retirement offsets (`0x5F45B`, `0x664DC`,
`0x6FF12`), and any use of protected Origins reserve words. It also rejects
reuse of the VV5 Heathens Converted field for memorial state.

Run:

```text
python -B scripts/validate_native_statistics_mutation_evidence.py
```

The checked-in result is expected to be a non-zero STOP because the native
mutation evidence is not present and the contract is disabled.

