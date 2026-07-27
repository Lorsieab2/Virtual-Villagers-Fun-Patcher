# VV4 Origins-exclusive features research

This is an implementation handoff for the exact supported
`Virtual Villagers - The Tree of Life.exe`, SHA-256
`6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220`.
The exact-build assembler and manifest are now present. This report still
marks the feature as runtime-validation pending; no claim is made that every
native dialog and upgrade interaction has been player-tested.

## Proven save and resource routes

- Save-scoped doubler bits can use the otherwise-unused first dword of the
  serialized statistics reserve: global `0x4D6E10`, GameState `+0x880`.
  `sub_41D9D0` zeroes the block and `sub_41DA00` / `sub_41DA20` restore/save it.
- Central tech adjustment: `sub_41E300`.
- Central food adjustment: `sub_41D920`; the final post-Food-Mastery delta is
  in `ESI` at `0x41D94F`.
- Positive Island Event tech caller returns to exclude from doubling:
  `0x414A2D`, `0x4156FD`, `0x415874`, `0x415A86`, `0x415B4B`,
  `0x415D91`, and `0x41673A`.
- Positive Island Event food caller returns to exclude:
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

The exact Running item ID, Tech constructor epilogue, Detail button insertion
and click handler, and any secondary age/pregnancy state required by Grant
Youth or Age to 18 remain unresolved.

## Payload and composability

The `.text` zero run begins at file/VA `0x89173` / `0x489173`, immediately
after the Experimental-256 stock-save loader. The shared statistics feature
uses `0x89173..0x89372`; the Origins payload begins at file `0x89373` and
fits within its validated `0xC8D`-byte cave without overlapping the expanded
VV4 patches.

The manifest is emitted only after the exact supported stock guards and payload
fit pass. UI, native Barrel presentation, Running behavior, age-state behavior,
and all-mode runtime checks remain explicit player-validation items.
