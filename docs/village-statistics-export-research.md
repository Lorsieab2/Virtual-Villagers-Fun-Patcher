# Village Statistics text-export research

## Cross-game Villagers Buried and Oldest Villager boundary

Exact-build audit `7fe0a047706693d69c9b504f7a7b0b014280dee3`
supersedes the earlier burial-hook interpretation below.

In all five games, stock **Oldest Villager** exports the persisted lifetime
maximum. It does not rescan living villagers, dead or skeleton records,
graves, mausoleums, the VV3 Roster of the Dead, or another current memorial
collection. Stock-layout export is proved; expanded-256 walker coverage
remains ON HOLD.

The future **Villagers Buried** counter must increment exactly once at the
earliest successful skeleton pickup, regardless of later graveyard or
mausoleum capacity, completion, occupancy, or burial success. Known delayed
grave/removal/record-retirement sites are downstream and insufficient.

The former VV3/VV4/VV5 burial detours at raw `0x5F45B`, `0x664DC`, and
`0x6FF12` are withdrawn and absent from the statistics generators and
manifests. Those exact stock guard bytes are preserved; no wrapper or payload
owns them. Memorial migration and any replacement burial hook remain **ON
HOLD** until an earliest-successful-pickup route and atomic save migration are
proved. Oldest Villager exporters and unrelated food/conversion hooks remain
active where independently certified.

A retroactive retained-memorial count may initialize a one-time lower-bound
baseline only with a dedicated, atomic, save-scoped initialized marker.
Initialization stores the baseline and marker together; later successful
pickups increment the saved counter. Export must never repeatedly add current
memorial counts. VV2 `state+0x2E514` is **Village Elders** and is forbidden
for buried migration, ownership, or initialization state. Exact pickup hooks
and safe migration storage remain ON HOLD.

## Confirmed local lifetime statistics

### A New Home

VV1's reachable local Statistics screen is `sub_431B30`. Its persisted manager
fields are:

| Statistic | Manager offset |
|---|---:|
| Points Earned | `+0x9E20` |
| Babies Made | `+0x9E24` |
| Food Gathered | `+0x9E28` |
| People Cured | `+0x9E2C` |
| Mushrooms Found | `+0x9E30` |
| Maximum Population | `+0x9E34` |
| Villagers Buried | `+0x9E38` |
| Oldest Villager | `+0x9E3C` |
| Island Events Seen | `+0x9E40` |
| Twins Birthed | `+0x9E44` |
| Triplets Birthed | `+0x9E48` |

Real Hours Played is calculated by `sub_41D0E0(manager)`. Puzzles Solved is
calculated from the sixteen persisted puzzle flags.

The block at `+0x9EEC` through `+0x9F1C` belongs to the separate Internet
statistics display and is not a substitute for the local values.

### The Lost Children

VV2 retains the corresponding local lifetime counters:

| Statistic | Manager offset |
|---|---:|
| Points Earned | `+0x2E4FC` |
| Babies Made | `+0x2E500` |
| Food Gathered | `+0x2E504` |
| People Cured | `+0x2E508` |
| Mushrooms Found | `+0x2E50C` |
| Highest Population | `+0x2E510` |
| Village Elders | `+0x2E514` |
| Oldest Villager | `+0x2E518` |
| Island Events Seen | `+0x2E51C` |
| Special Stews Found | `+0x2E520` |
| Triplets Birthed | `+0x2E524` |

Real Hours Played is calculated by `sub_425A90(manager)`. Puzzles Solved is
calculated from the sixteen persisted completion bytes at `+0x2E768`,
`+0x2E770`, `+0x2E778`, `+0x2E780`, `+0x2E788`, `+0x2E790`, `+0x2E798`,
`+0x2E7A0`, `+0x2E7A8`, `+0x2E7B0`, `+0x2E7B8`, `+0x2E7C0`, `+0x2E7C8`,
`+0x2E7D8`, `+0x2E7E0`, and `+0x2E7E8`.

## The later games retain the inherited lifetime block

The initial UI-led inspection was incomplete. VV3 through VV5 do not expose the
old local Statistics screen, but all three still initialize, serialize, and
restore its inherited `0x98`-byte per-save block:

| Game | Runtime block | Saved manager copy |
|---|---:|---:|
| The Secret City | `0x5824A0` | `+0x4EC` |
| The Tree of Life | `0x4D6DE0` | `+0x850` |
| New Believers | `0x51D358` | `+0x7B4` |

The common layout is:

| Offset | Statistic |
|---:|---|
| `+0x00` | save/session creation-time anchor |
| `+0x04` | Points Earned |
| `+0x08` | Babies Made |
| `+0x0C` | Food Gathered |
| `+0x10` | People Cured |
| `+0x14` | Mushrooms Found in VV3/VV5; Collectibles Found in VV4 |
| `+0x18` | Highest Population |
| `+0x1C` | Villagers Buried |
| `+0x20` | Oldest Villager |
| `+0x24` | Island Events Seen |
| `+0x28` | Twins Birthed |
| `+0x2C` | Triplets Birthed |

Stock VV3 maintains every counter except Villagers Buried. Stock VV4 and VV5
maintain every counter except Food Gathered and Villagers Buried. Those fields
are not guesses: they are the unchanged inherited slots between otherwise
matching VV1-style fields. Historical manifests proposed omitted mutation
sites, but their Villagers Buried hooks are downstream of the required
successful-pickup event and are not certified. Existing saves retain stock
history; retroactive initialization requires the atomic migration above.

The block range `+0x30..+0x97` has no direct stock code references in any of the
three games. It is still zeroed, serialized, and restored, but the current
implementation uses one proven field in that reserve for VV5:

- `runtime 0x51D38C`, statistics `+0x34`, saved manager `+0x7E8` stores the
  patch-added **Heathens Converted** lifetime total.
- The exact successful-conversion entry is `sub_4668B0`. Its original first
  six bytes are `83 EC 10 56 8B F1`.
- At function entry, the original Heathen tag is still present at villager
  record `+0x1CFC`. Tag `17` is the Heathen Mommy, so that conversion adds two;
  every other successful conversion adds one. Stock subsequently clears most
  tags, so the test must happen before the original conversion body resumes.
- The first reserve dword at runtime `0x51D388` remains exclusively owned by
  the Origins feature's saved bit flags. The conversion total uses the next
  dword and does not overlap it.
- Existing saves begin this new total at zero. The counter is not retroactive.

VV4 and VV5's threshold-limited achievement trackers are not used as
substitutes for these uncapped lifetime totals.

### Historical proposed writers and current status

| Game | Statistic | Exact stock route patched |
|---|---|---|
| VV3 | Villagers Buried | **insufficient downstream site**: delayed corpse-record retirement at `0x45F45B`, not the required successful-pickup hook |
| VV4 | Food Gathered | final central food delta at `0x41D987`; guard `01 37 8B 07 79 0B` |
| VV4 | Villagers Buried | **insufficient downstream site**: delayed corpse-record release at `0x4664DC`, not the required successful-pickup hook |
| VV5 | Food Gathered | final central food delta at `0x41EBA7`; guard `01 37 8B 07 79 0B` |
| VV5 | Villagers Buried | **insufficient downstream site**: delayed corpse-record release at `0x46FF12`, not the required successful-pickup hook |
| VV5 | Heathens Converted | successful conversion entry at `0x4668B0`; guard `83 EC 10 56 8B F1`; tag 17 adds two and all other tags add one |

The food detours count only positive final deltas and reproduce the stock
negative-underflow branch. Historical burial detours run at delayed
record-release/retirement sites and cannot satisfy the required
earliest-successful-skeleton-pickup contract.

### Later-game puzzle counts

- VV3 stores the sixteen story-puzzle progress values at
  `manager+0x11ED8+8*id`, IDs 0 through 15. The thresholds at RVA `0x9D230`
  are `1, 1, 5, 700, 1, 1, 1800, 1400, 2, 1, 1, 6, 1, 1, 1, 1`.
- VV4 calls predicate RVA `0x38960` with puzzle manager RVA `0xD8BF8`, IDs
  0 through 15.
- VV5 stores progress at `manager+0x16D20+8*id`, with thresholds at RVA
  `0x11DF30`. Stock counts IDs 1 through 16. When the Heathen Parent patch
  marker at RVA `0x8F16` is active, the exporter counts ID 17 and reports a
  denominator of 17.

## Safe update points

The text file should be refreshed after each successful full-save call. This
includes a normal close-time save without depending on an unproven
process-termination route, and it avoids exporting state from a failed or
partially normalized save.

| Game | Full-save wrapper | Wrapped call | Resume |
|---|---:|---:|---:|
| The Secret City | `sub_427C60` | `sub_403530(this, this+8, 77596, slot)` | after successful call |
| The Tree of Life | `sub_41F030` | call at `0x41F13A` to `sub_4039B0` | `0x41F13F` |
| New Believers | `sub_4244F0` | call at `0x4245FA` to `sub_403940` | `0x4245FF` |

For VV4 and VV5, a detour must replace the five-byte full-save call itself and
return to the existing post-call instruction. The wrapper must preserve the
writer's Boolean result and export only after success. Slot-zero uses a
separate path and must not trigger a village-statistics export.

## Fields still blocked on exact evidence

The following requested totals were not added in this pass because no exact,
uncapped lifetime storage field and mutation route have yet been proven:

- Village Elders where the inherited statistics block does not already expose
  it.
- Villagers Died at the moment of death. The currently restored later-game
  counter is precisely **Villagers Buried** and increments only when a corpse
  record is retired after its delay; it must not be relabeled as immediate
  deaths.
- Total Stews Made in VV2 through VV4.
- Tribal Chiefs Robed in VV3.
- Debris Cleared in VV4.

Threshold-limited achievement counters are not accepted as substitutes for
these uncapped lifetime totals.
