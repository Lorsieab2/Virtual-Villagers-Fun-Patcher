# V28 retrofit: harm review (for the owner's approval)

The owner's rule (2026-11-14): only VV2 totems are always protected. Nursing mothers, babies, the Golden Child and the
VV3 Chief may be harmed only where the event's own risk makes sense, with `protected: "allow"` on that role, and every
such case is listed here: the event, the outcome, the villager, the exact text and why. VV5 story villagers (the
chief, the Retired Chief, the puzzles' Heathens) stay unharmable whatever a file says.

`python scripts/collection_check.py --allow-report` lists every `allow` on a harm-capable role for checking against
this file.

## Part A

Range: `original/`, `universal/`, `v6/`, `vv5_isolan/`, `v8/`, `v9/`, `v10/`, `v11/` (51 events).

**No entries.** The Part A retrofit adds no `protected: "allow"` and no harm to a nursing parent, a baby, the Golden
Child or the VV3 Chief.

- The one harmful effect added in Part A is the serious-injury `health_change` on The Doctors' Dilemma's patient
  (outcome "lasting effects", L1609-1610). That role keeps the default `protected: "auto"`, so nursing parents, the
  Golden Child and the VV3 Chief are never cast as the patient.
- The special villagers this range already casts take only harmless effects: The Last Song Before Sunset's nursing
  parent gains a little Parenting (no `allow` needed for a gain); The Lullaby, The Child of Legend, The Chief's
  Monumental Speech, The Chief and the Pearl and The Little Things They Remember are unchanged.
