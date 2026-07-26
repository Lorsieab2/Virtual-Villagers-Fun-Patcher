# Village Statistics text-export research

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
matching VV1-style fields. The patch restores the omitted mutation sites while
leaving the existing counters intact, so existing saves retain all history
that stock already recorded.

The block range `+0x30..+0x97` has no direct stock code references in any of the
three games. It is still zeroed, serialized, and restored, but the current
implementation does not need to consume that reserve.

VV4 and VV5's threshold-limited achievement trackers are not used as
substitutes for these uncapped lifetime totals.

### Restored omitted writers

| Game | Statistic | Exact stock route patched |
|---|---|---|
| VV3 | Villagers Buried | delayed corpse-record retirement at `0x45F45B`; guard `88 1E E9 B8 01 00 00`; resumes the stock loop tail at `0x45F61A` |
| VV4 | Food Gathered | final central food delta at `0x41D987`; guard `01 37 8B 07 79 0B` |
| VV4 | Villagers Buried | delayed corpse-record release at `0x4664DC`; guard `88 5E FD 38 5E FD` |
| VV5 | Food Gathered | final central food delta at `0x41EBA7`; guard `01 37 8B 07 79 0B` |
| VV5 | Villagers Buried | delayed corpse-record release at `0x46FF12`; guard `88 9E D4 1C 00 00` |

The food detours count only positive final deltas and reproduce the stock
negative-underflow branch. The burial detours run at the one-time occupied
record release after 240 simulated minutes. VV3 does not create a tombstone at
that instruction, so its route is described precisely as record retirement.

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
