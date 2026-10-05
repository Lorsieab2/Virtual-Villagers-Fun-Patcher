# Max-population research

This records the static evidence behind the exact-build manifest. Addresses are image virtual addresses; guarded file offsets and bytes are in `data/builds.json`.

## Slot pools and target maxima

| Game | Slots | Stock final cap | No Population Increase | Collection Progression | Immediate Fixed |
|---|---:|---:|---:|---:|---:|
| A New Home | 256 | 90 | 90 | 256 | 256 |
| The Lost Children | 256 | 115 | 115 | base 231 plus 0-25 collections | 256 |
| The Secret City | 150 | 125 | 125 | base 115 plus 0-25 collections and 0/10 magic | 150 |
| The Tree of Life | 150 | 115 | 115 | base 125 plus 0-25 collections | 150 |
| New Believers | 150 | 105 | 105 | base 135 plus 0-15 collections | 150 |

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

New Believers' stock `add esi, 0x5A` uses a sign-extended 8-bit immediate. A value above 127 cannot be substituted into that instruction: byte `0x87` means -121, not +135. The Collection Progression and Immediate Fixed cap modes therefore detour the complete add/compare/branch sequence at file offset `0x72C49` to guarded padding at `0x94500`; all three public modes still receive the separate physical-capacity safety rows. Progression performs `add esi, 0x00000087`, yielding 135, 140, 145, or 150 for collection bonuses 0, 5, 10, or 15. Fixed performs the stock `+90` after replacing the accumulator with 60, yielding 150.

No Population Increase leaves the stock cap and collection completion behavior
unchanged, but it still installs the game's automatic physical-capacity safety
edits. Collection Progression and Immediate Fixed retain their documented cap
and progression behavior and use the same safety layer. Across all three public
modes, safety clamps physical allocation only; it does not change the selected
mode's social cap or progression.

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

All three public modes therefore share guarded birth-selection detours. They
implement `delivered_babies = min(rolled_babies, slots - current_slot_demand)`
while the selected mode's original cap predicate guarantees at least one
remaining slot. For VV1 through VV4, slot demand is the ordinary population
aggregate. VV5 uses the physical-demand helper described above. This preserves
the original RNG and multiple-birth statistics whenever the rolled multiple
fits. A triplet is reduced to twins only with two spaces, and any multiple is
reduced to a singleton only with one space.

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

## Population notices and refusals follow the cap

The owner, with A New Home at 254 of 256: "I got a notification about max
population when I was at like 115 villagers." That was string 315,
"Congratulations! Your village reached its maximum sustainable population!",
queued by the world tick `0x42E900`. Its test at `0x42F1EE` was the stock
`cmp eax, 0x5A` (90), and the population modes patched only the growth
predicate `0x43A1A0`. The notice is one-shot: flag byte `+0x16C` lives in the
saved village block. It is cleared when the notice fires and re-armed only when
the 10-entry notice queue was full. So the notice fired at the first tick that
counted 90 or more. A village that grew past 90 while the game was closed
reaches that tick only after the load-time catch-up, at whatever population
the catch-up left it. Here that was about 115.

Every place the five stock executables compare a population against a limit
was found two ways:

- from the decompiled callers of each game's population counter: VV1
  `0x41CF90`, VV2 `0x425860`, VV3 `0x45E8F0`, VV4 `0x467610` and VV5
  `0x4713F0`;
- from an instruction scan of every function that calls a counter, for the
  stock base (0x59-0x5B), each game's stock final cap, and 150.

The 10/15/25/50 tiers are housing gates. Every mode keeps them, so they are not
caps.

| Game | Site | What the player sees | Stock test | Before this change | Now |
|---|---|---|---|---|---|
| VV1 | `0x42F1EE` in `0x42E900` | "reached its maximum sustainable population!" (315) | `< 90` | stock 90 in every mode (the owner's report) | 256 in Collection Progression and Immediate Fixed |
| VV1 | `0x43DE45` in `0x43DAD0` | a dragged pair's refusal reason: "There isn`t enough housing!" (28), "They're too hungry to think about this!" (22), "That didn`t go too well." (27) | `< 90` | silent from 90 to 255 | explained below 256 |
| VV1 | `0x43E740`, `0x43EA50` | "Worried about housing" (577) | predicate | follows the cap | unchanged |
| VV2 | `0x44FAF9` in `0x44F610` | the refusal reason (47, 52) | `< 90 && predicate` | silent from 90 up to the cap | explained whenever the predicate `0x44B310` allows growth (256 bound) |
| VV2 | `0x43C13E` in `0x43B690` | maximum notice (454) | `< 90 \|\| predicate` | follows the cap | unchanged |
| VV2 | `0x44FE82`, `0x4500A2` | "Worried about housing" (828) | `predicate \|\| >= 90` | follows the cap | unchanged |
| VV3 | `0x428D0B` in `0x428C60` | maximum notice (697) | `< 90 \|\| predicate` | follows the cap, including 256 Villagers | unchanged |
| VV3 | `0x445041`, `0x452D1D` | "Worried about housing" (1139) | `predicate \|\| >= 90` | follows the cap | unchanged |
| VV4 | `0x42063C` in `0x420330` | maximum notice (745) | `>= 90 && !predicate` | follows the cap, including 256 Villagers | unchanged |
| VV5 | `0x4261F5` in `0x425E30` | maximum notice (741) | `< 90 \|\| predicate` | follows the cap: the modes' predicate counts physical demand, so it also follows 256 Villagers | unchanged |

In VV3-VV5 the dragged-pair refusal asks the predicate itself (VV3 `0x45A2C0`,
VV4 `0x460C10`, VV5 its equivalent), so it already follows the cap. The Origins
Barrel O' Babies gates read the installed mode's bytes, including those of 256
Villagers:

- VV1 `POPULATION_FINAL_TIER`;
- VV2 `vv2_population_cap`;
- VV3 `vv3_barrel_has_room_for_three`;
- VV4 `0x468350`;
- VV5 `barrel_room`.

No site blocks growth at a stock number in an expanded mode. Every growth
decision goes through the patched predicate.

The rows use no new space:

- VV1's notice test becomes `test ah, ah; jz`, meaning a population below 256.
  The counter never reaches 65,536.
- Each refusal test becomes `cmp byte [esp+0x19], 0; jne`, meaning a counted
  population of 256 or more.
- Stock mode keeps the stock bytes.

`tests/test_population_notices_follow_caps.py` executes every notice, predicate
and refusal in the rendered bytes. It covers:

- each game and mode;
- each build: bare, every public patch, and 256 Villagers alone and with every
  public patch;
- each collection and Magic state.

It checks that a notice fires exactly at the cap the predicate enforces and
never below it.

Not changed, pending the owner's decision: in Immediate Fixed the collection
completion popups still say the population maximum "is increased by 5" (VV2
478-482, VV3 720-724, VV4 770-774, VV5 767-769). VV3's Faction of Magic text
still says Level 3 raises it. That mode ignores both bonuses. The texts state no
cap number, and VV4 and VV5 also override them from `Assets\sm.xml`.
