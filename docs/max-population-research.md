# Max-population research

This records the static evidence behind the exact-build manifest. Addresses are image virtual addresses; guarded file offsets and bytes are in `data/builds.json`.

## Slot pools and target maxima

| Game | Slots | Stock final cap | Collection Progression | Immediate Fixed |
|---|---:|---:|---:|---:|
| A New Home | 256 | 90 | 256 | 256 |
| The Lost Children | 256 | 115 | base 231 plus 0-25 collections | 256 |
| The Secret City | 150 | 125 | base 115 plus 0-25 collections and 0/10 magic | 150 |
| The Tree of Life | 150 | 115 | base 125 plus 0-25 collections | 150 |
| New Believers | 150 | 105 | base 135 plus 0-15 collections | 150 |

Slot evidence:

- A New Home uses 256 records at stride `0x3D8`; its free-slot loop has an exclusive `0x100` bound.
- The Lost Children uses 256 records at stride `0xE48C`; `0x44B400` has an exclusive `0x100` bound.
- The Secret City uses 150 records at stride `0x1F8C`; manager loops use exclusive bound `0x96`.
- The Tree of Life constructs 150 records, indices `0x95` through zero, at `0x467CE0`.
- New Believers constructs 150 records, indices `0x95` through zero, at `0x471DF0`.

## Population predicates

- A New Home: `0x43A1A0`. The patch compares against 256 while retaining stock housing gates.
- The Lost Children: `0x44B310`. Progression changes base 90 to 231 and preserves the 0-25 collection accumulator. Fixed overwrites the accumulator with 166 before the stock +90, producing 256 at every collection state.
- The Secret City: `0x45FE30`. Progression changes base 90 to 115 and preserves 0-25 collections plus the level-3 magic bonus of 10. Fixed sets the accumulator to 60 before stock +90, producing 150 at every collection and magic state.
- The Tree of Life: `0x468350`. Progression changes base 90 to 125 and preserves the 0-25 collection accumulator. Fixed sets it to 60 before stock +90.
- New Believers: `0x472BD0`. Progression changes base 90 to 135 and preserves the 0-15 collection accumulator. Fixed sets it to 60 before stock +90.

New Believers' stock `add esi, 0x5A` uses a sign-extended 8-bit immediate. A value above 127 cannot be substituted into that instruction: byte `0x87` means -121, not +135. Both modes therefore detour the complete add/compare/branch sequence at file offset `0x72C49` to guarded padding at `0x94500`. Progression performs `add esi, 0x00000087`, yielding 135, 140, 145, or 150 for collection bonuses 0, 5, 10, or 15. Fixed performs the stock `+90` after replacing the accumulator with 60, yielding 150.

Collection completion itself is never modified.

## New Believers faction conversion and shared slots

New Believers constructs one shared pool of 150 records. `sub_46FB80` creates a Heathen by finding an inactive record in that pool and calling the faction setter `sub_466880(..., 1)`. The retained conversion routine `sub_4668B0` calls the same setter with zero on that existing record. Conversion therefore changes faction in place and does not allocate a second record.

The displayed/cap population helper `sub_4713F0` deliberately counts only living, active non-Heathens, plus nursing babies stored on those records. A flat 150 comparison against that believer-only result would permit births to reserve more records than exist while unconverted Heathens or unreleased corpse records remain.

The VV5 patch therefore installs a guarded physical-demand helper at file offset `0x944C0`. It scans all 150 records, counts every active record regardless of faction or corpse state, and adds each active mother's stored baby count while the babies still await separate records. Both cap modes compare this demand against their current collection-dependent or fixed ceiling. The twin and triplet guards call the same helper. Conversion remains possible at the ceiling because it reuses its current record and does not increase physical demand.

## Twins and triplets at maximum minus one

The birth routines in all five games call the population predicate once and decide the number of babies afterward:

| Game | Cap call in birth routine | Baby-count/population behavior |
|---|---:|---|
| A New Home | `0x43BBC3` | Singleton increments the aggregate first; each accepted extra baby increments it again. |
| The Lost Children | `0x44B983` | Same incremental behavior; count becomes 2 or 3 after the one cap check. |
| The Secret City | `0x455AB8` | Count is set to 1, 2, or 3, then the whole count is added at `0x455BF3`. |
| The Tree of Life | `0x45E7C1` | Count is set after the cap check, then added at `0x45E91C`. |
| New Believers | `0x465E11` | Count is set after the cap check, then added at `0x465F3E`. |

Therefore, stock logic evaluated at cap minus one yields cap for a singleton, cap plus one for twins, and cap plus two for triplets.

This is unsafe when a patch moves the cap to the physical pool ceiling. A New Home's child materializer at `0x43C840` and The Lost Children's at `0x44CEC0` scan for the next unused record without a terminal pool check; their weaning paths call the materializer again for the second and third babies. The later games also have only 150 physical records, so an aggregate of 151 or 152 cannot map to unique villagers.

Both modes therefore share guarded birth-selection detours. They implement `delivered_babies = min(rolled_babies, slots - current_slot_demand)` while the original cap predicate guarantees at least one remaining slot. For VV1 through VV4, slot demand is the ordinary population aggregate. VV5 uses the physical-demand helper described above. This preserves the original RNG and multiple-birth statistics whenever the rolled multiple fits. A triplet is reduced to twins only with two spaces, and any multiple is reduced to a singleton only with one space.

The detours use verified zero-filled executable padding inside the existing `.text` section. Section layout and file size do not change.

## Build identities

| Game | Size | SHA-256 |
|---|---:|---|
| A New Home | 581,632 | `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D` |
| The Lost Children | 724,992 | `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677` |
| The Secret City | 831,488 | `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503` |
| The Tree of Life | 929,792 | `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` |
| New Believers | 991,232 | `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D` |

Static verification proves exact build identity, guarded instruction edits, slot bounds, fixed/progression arithmetic, PE integrity, and output readback. It does not claim a played save has been grown to every new maximum.
