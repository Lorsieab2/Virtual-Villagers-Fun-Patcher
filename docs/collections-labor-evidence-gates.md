# Complete All Collections and Equal Division evidence gates

Both contracts are disabled evidence-only records for absent VV3/VV4/VV5
features. They do not add catalog entries, emit native bytes, package files,
launch games, or access saves. `publication_allowed` always remains false.

## Complete All Collections

The gate requires an exact per-game collection table, entry count and order,
missing-entry predicate, and native add/complete writer. It separately proves
duplicate behavior, rewards, trophies, statistics, notifications, dry-run,
IDOK confirmation, identity reacquisition, postverification, and either one
verified charge or explicit zero-cost semantics. Save/reload/offline catch-up
must be idempotent, and hook/cave regions must compose without overlap.

A population bonus or an award/trophy dispatcher is not a collection
completion route. Evidence that proves only either role is rejected.

## Equal Division

The gate pins the reviewed preference-selector order without claiming that it
is a complete native current-action/job enum:

- VV3: Farming, Building, Research, Healing, Parenting;
- VV4: Farming, Parenting, Healing, Research, Building;
- VV5: Healing, Parenting, Farming, Research, Building, Devotion.

Future evidence must prove the sex field and encoding, physical record order,
active/living/status/current-faction eligibility, deterministic cycle,
remainder/tie/unknown-sex behavior, Parenting and Devotion policy, native
setter/readback effects, action queue, notification, statistic, persistence,
repeat/no-op behavior, transaction order, and rollback truth. VV5 must check
current faction first. The unproved `+0x1CE1` byte is excluded. VV3 must state
whether Tribal Chiefs are excluded or supply native proof for inclusion.

Composition must cover Full Mastery, Grant Running, and Full Heal. VV5 nursery
divisor parity at `0x425FDF` is unrelated and is explicitly rejected.

Run the validators with the bundled Python runtime:

```text
python -B scripts/validate_complete_all_collections_evidence.py
python -B scripts/validate_equal_division_evidence.py
```

The checked-in results are expected STOPs: their schemas are structurally
valid, but exact full-folder fingerprints and native/runtime/player receipts
are absent.
