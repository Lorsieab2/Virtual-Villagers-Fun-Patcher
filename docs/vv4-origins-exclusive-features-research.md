# VV4 Origins-exclusive features research

This is an implementation handoff for the exact supported
`Virtual Villagers - The Tree of Life.exe`, SHA-256
`6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220`.
The exact-build assembler and manifest are now present. This report still
marks the feature as runtime-validation pending; no claim is made that every
native dialog and upgrade interaction has been player-tested.

## Current Origins menu route

The public VV4 route is the combined Origins-style Village-Wide Upgrades
patch. It owns both the Tech-screen Village-Wide menu and the Villager Details
upgrades menu; standalone Full Mastery and Full Heal records are historical
evidence only and are not catalog or release entries.

- Village-Wide and Details Full Mastery use the exact VV4 native skill writer
  at `0x46AD80`, passing a Float32 delta to exact `100.0` and the skill ordinal
  `0..4`, with postverification.
- Grant Running follows the shared fixed-array rule: an existing Running Like
  is a no-write/no-charge skip; otherwise the first physical empty Like is
  required before inserting Running once and clearing matching Dislikes.
- Full Heal/Cure All processes active living records, raises health below `80`
  to exact `100` through `0x46AF00`, clears sickness, and increments the
  VV4 People Cured statistic only after the sickness clear.
- The native VV4 UI factory/destructor and relocated Details handler are used;
  non-intercepted Tech and Details events fall through to `0x43E9F8` and
  `0x448618`. Runtime/player confirmation remains pending.

## Current shipping gate

The doubler audit's PROVENANCE remains incomplete for this exact build. Availability is not gated on it: both doublers are purchasable while unowned, and the `or eax, 0x1800` hold that forced rows 3 and 4 to **Unavailable** was lifted in v1.34.14; existing owned doublers remain removable for zero cost and
zero refund, and ownership is never cleared automatically. The listed return
addresses are historical candidates and are invalid for classifying E9 tail
jumps; incomplete dynamic/computed Island Event provenance and the lack of a
safe post-Food-Mastery hook/section prevent shipping.

## Proven save and resource routes

- Save-scoped doubler bits can use the otherwise-unused first dword of the
  serialized statistics reserve: global `0x4D6E10`, GameState `+0x880`.
  `sub_41D9D0` zeroes the block and `sub_41DA00` / `sub_41DA20` restore/save it.
- Central tech adjustment: `sub_41E300`.
- Central food adjustment: `sub_41D920`; the final post-Food-Mastery delta is
  in `ESI` at `0x41D94F`.
- Historical candidate positive Island Event tech caller returns:
  `0x414A2D`, `0x4156FD`, `0x415874`, `0x415A86`, `0x415B4B`,
  `0x415D91`, and `0x41673A`.
- Historical candidate positive Island Event food caller returns:
  `0x41494E` and `0x415213`.
- Duplicate-collectible awards in `sub_414410` are not Island Event awards and
  should remain eligible for doubling.

## Time, events, and population

- Simulation clock base: qword `0x4B8230`.
- Game speed: GameState `+94480`; stock values are 3, 6, 10, and paused 999.
- Island Event scheduling field: GameState `+94432`. Making it due must continue
  through stock scheduler `sub_43F750`.
- Current population: `sub_467610`.
- Native Daredevil Barrel event vtable: `0x48CA44`.
- Native barrel result: `sub_414D90`. It uses `sub_467D10` for child creation
  and checks `sub_468350` before the second and third child.

The assembler uses the verified native event path and shared Origins icon
dialog route. The final event-registry presentation and clean native dialog
behavior still require player validation.

## UI and selected villager

- Tech message handler: `sub_43E9F0`; stock uses IDs 0 through 12, leaving 13
  available.
- Selected index: GameState `+94640`.
- Selected-index validator: `sub_467980`.
- Record resolver: `sub_466040`.
- Record fields:
  - displayed age `+7052` in 20 units per displayed year;
  - health `+7232`;
  - five float skills `+7260`, `+7264`, `+7268`, `+7272`, `+7276`;
  - preferred skill `+7280`;
  - three Likes dwords at `+7776`;
  - three Dislikes dwords at `+7788`.

The exact Running item ID, Tech constructor epilogue, Detail button insertion,
click handler, and age-state fields are resolved in the current manifest and
static tests. Runtime/player validation remains pending.

## Payload and composability

The `.text` zero run begins at file/VA `0x89173` / `0x489173`, immediately
after the Experimental-256 stock-save loader. The shared statistics feature
uses `0x89173..0x89372`; the Origins payload begins at file `0x89373` and
uses the validated `0xA00`-byte cave without overlapping the current
stock-mode payload boundaries.

The manifest is emitted only after the exact supported stock guards and payload
fit pass. The doubler remains STOP pending safe hook placement and complete
Island Event provenance. UI, native Barrel presentation, Running behavior,
age-state behavior, and all-mode runtime checks remain explicit
player-validation items.

## Expanded-256 VV4 save and current-Origins relocation contract

The VV4 Expanded-256 static contract is
`data/vv4_expanded_256_contract.json`. It is bound to the exact stock
fingerprint above and remains publication-disabled/fail-closed. The guarded
loader hook at raw `0x1FC19` retries the exact stock payload size when the
expanded-size request is rejected. Its raw `0x8910D` conversion cave accepts
that stock layout, moves the saved-state tail, and clears the 106 inserted
compact villager records before native validation/conversion continues. The
four current-Origins absolute `.shr` operands at raw `0x20902`, `0x20916`,
`0x2092B`, and `0x2B036` are explicitly guarded from `0x728000` to
`0x85A000`; they are not established by a raw byte sweep.

The four absolute operands inside the existing current Origins payload are
separately guarded at `0xCC182`, `0xCC18E`, `0xCC19A`, and `0xCC1A6`, targeting
the expanded header addresses `0x85A220`, `0x85A224`, `0x85A228`, and
`0x85A230`. The four previously stale all-feature operands are separately
owned and guarded at `0x89546`, `0xCC1AF`, `0xCC1B8`, and `0xCC1C1`, targeting
`0x85A220`, `0x85A234`, `0x85A238`, and `0x85A23C`. Static tests cover exact
guards, explicit relocation application, stock-mode no-op behavior, malformed
guards, and fail-closed publication metadata.
Fresh player-authorized stock import, expanded save/reload, catch-up,
conversion continuity, current-Origins behavior after relocation, packaging,
and runtime/player confirmation remain unresolved gates.
