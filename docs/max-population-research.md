# Max-population research

This document records the static evidence used by the exact-build manifest. Addresses are image virtual addresses for the five supplied 32-bit Windows executables. File offsets and guarded bytes are in `data/builds.json`.

## Slot pools

- **A New Home:** 256 records. Full-pool loops advance by record size `0x3D8` until byte span `0x3D800`, and the free-slot loop compares its index with `0x100`.
- **The Lost Children:** 256 records. The free-slot routine at `0x44B400` advances by `0xE48C` and compares its index with `0x100`.
- **The Secret City:** 150 records. Manager loops use record size `0x1F8C` and an exclusive `0x96` bound.
- **The Tree of Life:** 150 records. `CVillagerManager` construction at `0x467CE0` constructs indices `0x95` through zero at stride `0x2E3C`; other loops use exclusive bound `0x96`.
- **New Believers:** 150 records. `CVillagerManager` construction at `0x471DF0` constructs indices `0x95` through zero at stride `0x2F44`; other loops use exclusive bound `0x96`.

## Enforcement predicates

### A New Home

The population predicate starts at `0x43A1A0`. It calls the aggregate population counter at `0x41CF90`, rejects population `>= 90`, then retains staged housing checks at 50, 25, and 15. The patch changes only the first comparison to 256 by jumping into ten existing NOP bytes at `0x43A226`, then returns to the original conditional branch. File layout and size do not change.

### The Lost Children

The predicate at `0x44B310` calls the aggregate population counter at `0x425860`. Four completed collections contribute five each; all four convert 20 to 25. The stock base is 90, producing a final 115. Three original housing gates remain at 50, 25, and 15. The patch uses base 231, so the original maximum 25 collection bonus produces 256. The expanded arithmetic and displaced comparison use existing NOP padding at `0x44B3F2`.

### The Secret City

The predicate at `0x45FE30` calls population counter `0x45E8F0`. Four completed collections contribute a maximum 25, and level-3 magic adds another 10, for a maximum bonus of 35 above base 90; three housing gates remain at 35, 17, and 10. Base 90 becomes 115, producing 150 after all collections and level-3 magic.

### The Tree of Life

The predicate at `0x468350` calls population counter `0x467610`. It has the same maximum 25 collection bonus above base 90 and housing gates at 35, 17, and 10. Base 90 becomes 125, producing 150 after all collections.

### New Believers

The predicate at `0x472BD0` calls population counter `0x4713F0`. Two completed collections contribute five each, and completion of both converts 10 to 15. Housing gates remain at 35, 17, and 10. Base 90 becomes 135, producing 150 after both collections.

## Build identities

| Game | Size | SHA-256 |
|---|---:|---|
| A New Home | 581,632 | `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D` |
| The Lost Children | 724,992 | `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677` |
| The Secret City | 831,488 | `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503` |
| The Tree of Life | 929,792 | `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` |
| New Believers | 991,232 | `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D` |

Static verification proves exact build identity, instruction/slot relationships, guarded edits, PE integrity, and output readback. It does not claim a played save was grown to every new limit.
