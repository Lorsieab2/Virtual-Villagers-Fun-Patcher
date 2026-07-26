# VV3 Origins-Exclusive Features Research

This document records the verified implementation map for porting **Enable
Origins-Exclusive Features** to the supported desktop build of *Virtual
Villagers - The Secret City*. It deliberately does not claim that the VV3
feature is implemented.

## Supported executable

- File: `Virtual Villagers - The Secret City.exe`
- Size: `831488` bytes
- SHA-256:
  `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`
- Image base: `0x400000`

All addresses below apply only to this exact executable identity.

## Intended VV2-parity behavior

The current VV2 Origins feature is the behavior baseline:

- Tech Upgrades:
  - Time Warp: 50,000 tech points
  - Island Event: 30,000 tech points
  - Barrel of Babies: 75,000 tech points
  - Tech Point Doubler: 500,000 tech points; removable
  - Food Point Doubler: 500,000 tech points; removable
- Villager Upgrades:
  - Grant Youth: 50,000 tech points; age cannot go below 5
  - Grant Full Mastery: 100,000 tech points
  - Grant Running: 40,000 tech points
  - Set Age to 18: 50,000 tech points
- Doubler ownership belongs only to the current save.
- Island Event awards are not doubled.
- Grant Running uses a normal Like slot, removes Running from Dislikes, does
  not change movement data, and refuses without charging if no Like slot is
  free.
- Barrel of Babies must use VV3's native event and reserve room for all three
  children before charging.
- The reusable menu companion is
  `assets/origins/VVFP Origins Icons.dll`, export
  `ShowOriginsUpgradeMenuState(owner, type, state)`.

## Persisted save-scoped ownership

Verified unused persisted storage:

- Runtime global: `0x5824D0`
- Save-manager mirror: manager `+0x51C`
- Reserved saved region: global `0x5824D0..0x582537`, corresponding to manager
  `+0x51C..+0x583`

The first dword is code-unreferenced in the stock executable, zero-initialized,
and copied by the stock save/load path. Proposed bits:

- Bit 0: Tech Point Doubler
- Bit 1: Food Point Doubler

The save manager is returned by `sub_428B60`; its singleton pointer is
`0x4B309C`, and its object size is `0x12FD4`.

## Central food and tech routes

### Food

- Function: `sub_4263F0`
- Address: `0x4263F0`
- Receiver: pointer to current food
- Argument: signed delta
- Current-food global: `0x582490`
- Positive awards also increment stock lifetime Food Gathered at `0x5824AC`.
- Negative deltas clamp current food to zero and do not increase the lifetime
  total.

### Tech points

- Function: `sub_427130`
- Address: `0x427130`
- Receiver: pointer to current tech points
- Argument: signed delta
- Current-tech global: `0x582644`
- Positive awards also increment stock lifetime Points Earned at `0x5824A4`.
- Negative deltas clamp current tech points to zero and do not increase the
  lifetime total.

A correct doubler hook must double only a positive incoming delta before the
stock function updates both current resources and lifetime statistics.

### Island Event exclusion

The exact Island Event outcome dispatcher occupies
`0x458DB0..0x45943E`. Its food and tech awards use the same central resource
functions. The doubler wrappers must compare their caller return address
against this range and leave those awards unchanged.

## Villager Detail selection and record fields

The Villager Detail screen's displayed villager is selected by ID, not by a
screen-owned copy of the record:

1. Read the ID from save manager `+0x12FC0` (decimal `77760`).
2. Validate it with `sub_45EE60(id)` at `0x45EE60`.
3. Resolve the live record with `sub_45C840(id)` at `0x45C840`.

Verified record fields:

| Field | Record offset |
| --- | ---: |
| Current/displayed age | `+0xDC4` |
| Gender | `+0xDC8` |
| Health | `+0xE78` |
| Sick flag | `+0xE89` |
| Pregnancy/baby state | `+0xE8C` |
| Farming skill | `+0xEAC` |
| Building skill | `+0xEB0` |
| Research skill | `+0xEB4` |
| Healing skill | `+0xEB8` |
| Parenting skill | `+0xEBC` |
| Preferred job | `+0xEC0` |
| Three Likes | `+0xFB4` |
| Three Dislikes | `+0xFC0` |

Age uses 20 internal units per displayed year. The five skills are 32-bit
integers. Likes and Dislikes are each exactly three 32-bit entries, with `-1`
representing an empty slot.

The Detail renderer calls `sub_455350(record + 0xFB4)` for Likes and
`sub_4547D0(record + 0xFC0)` for Dislikes. Both helpers traverse exactly three
dwords.

### Grant Running

- Running trait ID: `38`
- If Running is already present in Likes, the upgrade is already satisfied.
- Otherwise, place `38` in the first `-1` Like slot.
- If no Like slot is free, refuse and do not charge.
- Clear every `38` found in the three Dislike slots.
- Do not alter movement speed or any movement-related record field.

`sub_454890` and `sub_454780` demonstrate the stock trait behavior but rely on
implicit current-selection state. Injected code should modify the resolved
record's three-slot arrays directly.

## Native Barrel of Babies event

VV3 already contains the literal native event:

- Title: `Another One of Those Barrels `
- Title string address: `0x48E5E4`
- Description string address: `0x48E450`
- Title localization ID: `0x321` (`801`)
- Description localization ID: `0x322` (`802`)
- Title-ID method: `0x4152F0`
- Description-ID method: `0x415300`
- Vtable: `0x47EA00`
- Registry index: `57`
- Event object pointer: `0x4B3D5C`
- Native result method: vtable `+0x30`, `sub_415320`

The event registry is built by `sub_418630`. Its pointer array begins at
`0x4B3C78`; the Barrel event is the last registered entry, index 57.

`sub_415320` performs the native result:

1. It creates the first child through `sub_45FF50(..., 200)`.
2. It calls `sub_45FE30`.
3. If permitted, it creates the second child through the same native route.
4. It calls `sub_45FE30` again.
5. If permitted, it creates the third child.

The stock event scheduler `sub_419B30` can deliberately select index 57 in its
forced-positive-event branch. Its native presentation path constructs the
event dialog through `sub_4192F0(event_object)`, presents it through
`sub_401AF0(owner, 0)`, and records the event as seen in
`byte_4B3C3C[57]`.

The Origins upgrade must use this native event object and presentation/result
path. It must not directly fabricate three villagers or substitute another
reward.

### Required capacity preflight

The purchase must reserve space for all three children before deducting tech
points. This preflight is unresolved because the same Origins feature must
compose with:

- stock VV3's physical 150-record pool, and
- the experimental 256-record expansion.

Hardcoding `population <= 147` would be correct only for the stock physical
pool. Hardcoding `population <= 253` would be correct only for the expanded
pool. A builder must first prove a reliable runtime capacity discriminator or
a shared capacity helper used by both executable modes.

The current population helper is `sub_45E8F0(byte_59E110)`. The stock villager
pool begins at `0x59E110` with stride `0x1F8C`. The physical allocator is
`sub_45F0B0`, which scans 150 records in the stock executable and returns `-1`
when none is available.

## Island Event and Time Warp routes

- Island Event scheduler: `sub_4684D0`
- Ordinary event creation pipeline: `sub_419AC0` / `sub_419B30`
- Game-time function: `sub_403330`

The save manager's pause/speed field is at manager `+0x12F20` (decimal
`77600`). Stock code treats values at least `999` as paused and contains normal
branches for speeds `3`, `10`, and the remaining standard case.

The exact Time Warp write and its duration conversion still require a final
call-site proof before implementation. The address above is sufficient to
identify pause/speed state but is not, by itself, proof of the correct
time-warp mutation.

## UI construction map

### Tech screen

- Constructor: `sub_464F30`
- Constructor address: `0x464F30`
- Vtable: `0x49E834`
- Message handler: `sub_465640(this, message, id)`
- Message-handler address: `0x465640`
- The handler processes command message `8` and stock IDs through `14`.

An Origins button may use an otherwise-unused ID greater than 14 if the
injected handler intercepts it before stock range handling.

### Villager Detail

- Constructor: `sub_46CB50`
- Constructor address: `0x46CB50`
- Vtable: `0x49EAD0`
- Message handler: `sub_46E530(this, message, id)`
- Message-handler address: `0x46E530`

### Shared stock UI helpers

- Button allocator thunk: `0x46EC93`
- Image/resource lookup: `sub_42E8A0`
- Button constructor: `sub_4019F0`
- Child append: `sub_40C1F0`
- Localized `Technologies`: ID `0xF3`
- Localized `Villager Detail`: ID `0x177`
- Localized `Tech Points Available`: ID `0x62`

The Tech constructor's existing button sequence near
`0x465083..0x4650E4` and the Detail constructor's sequence near `0x46CDD9`
are the stock patterns to reproduce.

## Explicit unresolved implementation gates

No VV3 builder or manifest should be produced until all of these gates are
closed:

1. Identify exact constructor-epilogue overwrite windows for both the Tech and
   Villager Detail screens, including the complete displaced instructions and
   correct continuation state.
2. Prove a collision-free mapped payload cave large enough for the complete
   feature (the VV2 implementation uses approximately `0xC58` bytes).
3. Cross-check that cave against every currently composable VV3 patch,
   including statistics, mortality, food replenishment, rare collectible, and
   both experimental population modes.
4. Prove the runtime stock-versus-expanded physical-capacity discriminator
   used by the Barrel three-space preflight.
5. Prove the exact Time Warp mutation rather than inferring it from the
   pause/speed field.
6. Preserve the exact five-byte guards at every hook and recompute the PE
   checksum after rendering.
7. Validate the resulting executable with all selectable VV3 patches applied,
   using both stock and experimental saves, before exposing it in the patcher.

Until those gates are complete, the verified constants above are a research
handoff rather than a playable feature.
